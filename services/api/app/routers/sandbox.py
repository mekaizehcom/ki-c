"""Admin endpoints for the sandbox-host SSH configuration."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit
from app.channels import ssh as ssh_channel
from app.db import get_db
from app.deps import require_role
from app.models import User

router = APIRouter(prefix="/api/admin/sandbox", tags=["sandbox"])


class SandboxConfig(BaseModel):
    host: str
    user: str = "ubuntu"
    port: int = 22
    private_key: str  # PEM, only stored encrypted; never returned


@router.get("")
def status_(
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict:
    return ssh_channel.public_info(db)


@router.put("")
def configure(
    body: SandboxConfig,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        public = ssh_channel.configure(
            db, host=body.host, user=body.user, port=body.port,
            private_key=body.private_key,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    audit(db, action="sandbox.configured", risk_level="critical",
          user_id=admin.id,
          details={"host": body.host, "user": body.user, "port": body.port})
    return public


@router.post("/test")
def test(
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict:
    r = ssh_channel.test_connection(db)
    audit(db, action="sandbox.tested", user_id=admin.id,
          risk_level="low",
          status="success" if r["exit_code"] == 0 else "failed",
          details={"exit_code": r["exit_code"],
                   "host": r.get("host"),
                   "stderr_tail": (r.get("stderr") or "")[-300:]})
    return r


@router.delete("")
def forget(
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
) -> dict:
    ssh_channel.forget(db)
    audit(db, action="sandbox.forgotten", risk_level="high", user_id=admin.id)
    return {"status": "forgotten"}
