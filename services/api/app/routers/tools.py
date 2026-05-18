import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.approvals import create_approval, finalize_approval
from app.audit import audit
from app.config import settings
from app.db import get_db
from app.deps import get_current_user, require_role
from app.models import Approval, User
from app.tools.engine import decide
from app.tools.executor import run
from app.tools.registry import REGISTRY, build_argv

router = APIRouter(prefix="/api", tags=["tools"])


class ExecuteRequest(BaseModel):
    agent: str
    command: str
    target: str | None = None
    workspace: str | None = None


class DecisionRequest(BaseModel):
    totp_code: str | None = None


@router.get("/tools")
def list_tools(_: User = Depends(get_current_user)) -> list[dict]:
    return [
        {"name": c.name, "tool": c.tool, "risk": c.risk,
         "approval_required": c.approval_required, "description": c.description,
         "takes_target": c.arg_pattern is not None}
        for c in REGISTRY.values()
    ]


@router.post("/tools/execute")
def execute(
    body: ExecuteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    ws = body.workspace or settings.default_workspace
    d = decide(db, user, ws, body.agent, body.command)
    audit(db, action="tool.request", user_id=user.id, agent_id=body.agent,
          risk_level=d.risk, status="denied" if not d.allowed else "pending",
          details={"command": body.command, "target": body.target,
                   "reason": d.reason})

    if not d.allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, d.reason)

    if d.proposed:
        try:
            argv = build_argv(d.command, body.target)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        return {"status": "proposed", "reason": d.reason, "would_run": argv}

    if d.execute_now:
        try:
            argv = build_argv(d.command, body.target)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
        result = run(argv)
        audit(db, action="tool.executed", user_id=user.id, agent_id=body.agent,
              risk_level=d.risk,
              status="success" if result["exit_code"] == 0 else "failed",
              details={"command": body.command, "target": body.target,
                       "exit_code": result["exit_code"]})
        return {"status": "executed", "reason": d.reason, "result": result}

    # approval required — validate target now so we fail fast
    try:
        build_argv(d.command, body.target)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    ap = create_approval(db, user, ws, body.agent, body.command, body.target, d)
    return {
        "status": "pending_approval",
        "approval_id": str(ap.id),
        "risk": d.risk,
        "approver_role": d.approver_role,
        "totp_reconfirm": d.totp_reconfirm,
        "reason": d.reason,
    }


@router.get("/approvals")
def list_approvals(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    q = select(Approval).order_by(Approval.created_at.desc()).limit(100)
    rows = list(db.scalars(q))
    is_approver = user.role in ("developer", "admin", "superadmin")
    out = []
    for a in rows:
        if not is_approver and a.requested_by != user.id:
            continue
        out.append({
            "id": str(a.id), "agent": a.agent_id, "tool": a.tool_name,
            "action": a.action_name, "risk": a.risk_level,
            "status": a.status, "payload": a.request_payload,
            "created_at": a.created_at.isoformat(),
        })
    return out


@router.post("/approvals/{aid}/approve")
def approve(
    aid: str, body: DecisionRequest,
    user: User = Depends(require_role("developer")),
    db: Session = Depends(get_db),
) -> dict:
    ap = db.get(Approval, uuid.UUID(aid))
    if not ap:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return finalize_approval(db, ap, user, approve=True, totp_code=body.totp_code)


@router.post("/approvals/{aid}/deny")
def deny(
    aid: str,
    user: User = Depends(require_role("developer")),
    db: Session = Depends(get_db),
) -> dict:
    ap = db.get(Approval, uuid.UUID(aid))
    if not ap:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return finalize_approval(db, ap, user, approve=False)
