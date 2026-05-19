"""Admin endpoints for SSH execution targets (labeled multi-host)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import audit
from app.channels import ssh as ssh_channel
from app.db import get_db
from app.deps import require_role
from app.models import User

router = APIRouter(prefix="/api/admin/sandbox", tags=["sandbox"])


class SshHostIn(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    user: str = "ubuntu"
    port: int = 22
    private_key: str  # PEM, only stored encrypted; never returned
    description: str = ""


@router.get("/hosts")
def list_hosts(
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[dict]:
    return ssh_channel.list_hosts(db)


@router.get("/hosts/{label}")
def get_host(
    label: str,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict:
    h = ssh_channel.get_host(db, label)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return h


@router.put("/hosts/{label}")
def upsert_host(
    label: str,
    body: SshHostIn,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
) -> dict:
    try:
        public = ssh_channel.upsert_host(
            db, label=label, host=body.host, user=body.user, port=body.port,
            private_key=body.private_key, description=body.description,
            created_by=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    audit(db, action="sandbox.host_upserted", risk_level="critical",
          user_id=admin.id,
          details={"label": public["label"], "host": public["host"],
                   "user": public["user"], "port": public["port"]})
    return public


@router.post("/hosts/{label}/test")
def test_host(
    label: str,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict:
    r = ssh_channel.test_connection(db, label)
    audit(db, action="sandbox.host_tested", user_id=admin.id,
          risk_level="low",
          status="success" if r["exit_code"] == 0 else "failed",
          details={"label": r.get("label") or label,
                   "exit_code": r["exit_code"],
                   "host": r.get("host"),
                   "stderr_tail": (r.get("stderr") or "")[-300:]})
    return r


@router.delete("/hosts/{label}")
def forget_host(
    label: str,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
) -> dict:
    if not ssh_channel.forget_host(db, label):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    audit(db, action="sandbox.host_forgotten", risk_level="high",
          user_id=admin.id, details={"label": label})
    return {"status": "forgotten", "label": label}
