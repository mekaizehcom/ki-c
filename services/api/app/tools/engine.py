"""Tool Permission Engine (§20).

Decision pipeline for every tool request:
  user role -> agent usable -> agent permits tool -> command known ->
  risk classification -> autonomy level -> approval / TOTP requirement.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Agent, User, Workspace
from app.tools.registry import Command, get

ROLE_RANK = {"restricted": 10, "user": 20, "developer": 30,
             "admin": 40, "superadmin": 50}

# Minimum role to drive a given agent (admin-editable later in Phase 6).
AGENT_MIN_ROLE = {
    "devops": "developer",
    "tessa-admin": "admin",
    "code-reviewer": "user",
    "document-agent": "user",
    "main": "user",
}

# AGENTS.md words -> §19 autonomy enum.
AUTONOMY_MAP = {
    "none": "none", "low": "approve_required", "medium": "approve_required",
    "high": "scoped_auto", "admin-configurable": "approve_required",
    "propose": "propose", "approve_required": "approve_required",
    "scoped_auto": "scoped_auto", "full_auto": "full_auto",
}

# Risk -> minimum approver role + TOTP reconfirm (§18).
APPROVER_ROLE = {"medium": "developer", "high": "admin", "critical": "superadmin"}
TOTP_RECONFIRM_RISK = {"high", "critical"}


@dataclass
class Decision:
    allowed: bool
    execute_now: bool          # run immediately (auto / low-risk)
    approval_required: bool
    proposed: bool             # autonomy=propose -> suggest only
    risk: str
    approver_role: str | None
    totp_reconfirm: bool
    reason: str
    command: Command | None = None
    agent_row: Agent | None = None


def _agent_row(db: Session, workspace_slug: str, agent_name: str) -> Agent | None:
    ws = db.scalar(select(Workspace).where(Workspace.slug == workspace_slug))
    if not ws:
        return None
    return db.scalar(
        select(Agent).where(Agent.workspace_id == ws.id, Agent.name == agent_name)
    )


def decide(
    db: Session, user: User, workspace_slug: str, agent_name: str,
    command_name: str,
) -> Decision:
    def deny(reason: str) -> Decision:
        return Decision(False, False, False, False, "low", None, False, reason)

    cmd = get(command_name)
    if not cmd:
        return deny(f"Unknown command '{command_name}' (not in registry)")

    if ROLE_RANK.get(user.role, 0) < ROLE_RANK.get(
        AGENT_MIN_ROLE.get(agent_name, "user"), 20
    ):
        return deny(f"Role '{user.role}' may not use agent '{agent_name}'")

    agent = _agent_row(db, workspace_slug, agent_name)
    if not agent:
        return deny(f"Agent '{agent_name}' not found in workspace")
    if cmd.tool not in (agent.tools or []):
        return deny(f"Agent '{agent_name}' is not granted tool '{cmd.tool}'")

    risk = cmd.risk
    autonomy = AUTONOMY_MAP.get((agent.autonomy or "").strip().lower(),
                                "approve_required")
    needs_approval = cmd.approval_required or risk in ("high", "critical")
    approver = APPROVER_ROLE.get(risk) if needs_approval else None
    totp = risk in TOTP_RECONFIRM_RISK

    # Autonomy gates.
    if autonomy == "none":
        return Decision(False, False, False, False, risk, approver, totp,
                        "Agent autonomy=none (analysis only)", cmd, agent)
    if autonomy == "propose":
        return Decision(True, False, False, True, risk, approver, totp,
                        "Agent autonomy=propose (suggest only)", cmd, agent)

    if not needs_approval:
        return Decision(True, True, False, False, risk, None, False,
                        "Low-risk, no approval required", cmd, agent)

    if autonomy == "scoped_auto" and command_name in (agent.allowed_auto_actions or []):
        if risk == "critical":  # critical always needs explicit approval (§18)
            return Decision(True, False, True, False, risk, "superadmin", True,
                            "Critical action always requires approval", cmd, agent)
        return Decision(True, True, False, False, risk, None, False,
                        f"scoped_auto: '{command_name}' in allowed_auto_actions",
                        cmd, agent)
    if autonomy == "full_auto":
        if risk == "critical":
            return Decision(True, False, True, False, risk, "superadmin", True,
                            "Critical action always requires approval", cmd, agent)
        return Decision(True, True, False, False, risk, None, False,
                        "Agent autonomy=full_auto", cmd, agent)

    return Decision(True, False, True, False, risk, approver, totp,
                    f"{risk}-risk action requires {approver} approval",
                    cmd, agent)
