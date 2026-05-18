"""Approval Engine (§18): create pending approvals, finalize (execute/deny)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit import audit
from app.models import Approval, TotpSecret, User
from app.security import decrypt, verify_totp
from app.tools.engine import APPROVER_ROLE, ROLE_RANK, TOTP_RECONFIRM_RISK, Decision
from app.tools.executor import run
from app.tools.registry import build_argv, get


def create_approval(
    db: Session, user: User, workspace: str, agent: str,
    command_name: str, target: str | None, decision: Decision,
) -> Approval:
    ap = Approval(
        requested_by=user.id,
        agent_id=agent,
        tool_name=decision.command.tool if decision.command else "",
        action_name=command_name,
        risk_level=decision.risk,
        status="pending",
        request_payload={"workspace": workspace, "agent": agent,
                         "command": command_name, "target": target,
                         "totp_reconfirm": decision.totp_reconfirm,
                         "approver_role": decision.approver_role},
    )
    db.add(ap)
    db.commit()
    audit(db, action="approval.requested", user_id=user.id, agent_id=agent,
          risk_level=decision.risk, status="pending_approval",
          details={"approval": str(ap.id), "command": command_name,
                   "target": target})
    return ap


def finalize_approval(
    db: Session, ap: Approval, approver: User, approve: bool,
    totp_code: str | None = None,
) -> dict:
    if ap.status != "pending":
        return {"status": ap.status, "detail": "Already finalized"}

    min_role = APPROVER_ROLE.get(ap.risk_level, "admin")
    if ROLE_RANK.get(approver.role, 0) < ROLE_RANK.get(min_role, 40):
        return {"status": "denied", "detail":
                f"Requires {min_role} to decide a {ap.risk_level} action"}

    if approve and ap.risk_level in TOTP_RECONFIRM_RISK:
        ts = db.get(TotpSecret, approver.id)
        if not ts or not verify_totp(decrypt(ts.secret), totp_code or ""):
            audit(db, action="approval.totp_failed", user_id=approver.id,
                  risk_level=ap.risk_level, status="denied",
                  details={"approval": str(ap.id)})
            return {"status": "totp_required",
                    "detail": "TOTP re-confirmation required/failed"}

    ap.approved_by = approver.id
    ap.approved_at = datetime.now(timezone.utc)

    if not approve:
        ap.status = "denied"
        db.commit()
        audit(db, action="approval.denied", user_id=approver.id,
              agent_id=ap.agent_id, risk_level=ap.risk_level, status="denied",
              details={"approval": str(ap.id), "command": ap.action_name})
        return {"status": "denied"}

    ap.status = "approved"
    db.commit()
    payload = ap.request_payload or {}
    cmd = get(ap.action_name)
    result: dict
    if not cmd:
        result = {"exit_code": 1, "stdout": "", "stderr": "command gone"}
    else:
        try:
            argv = build_argv(cmd, payload.get("target"))
            result = run(argv)
        except ValueError as exc:
            result = {"exit_code": 1, "stdout": "", "stderr": str(exc)}
    ap.status = "executed" if result["exit_code"] == 0 else "executed_error"
    db.commit()
    audit(db, action="approval.approved", user_id=approver.id,
          agent_id=ap.agent_id, risk_level=ap.risk_level,
          status="success" if result["exit_code"] == 0 else "failed",
          details={"approval": str(ap.id), "command": ap.action_name,
                   "target": payload.get("target"),
                   "exit_code": result["exit_code"]})
    return {"status": ap.status, "result": result}
