from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.db import get_db
from app.deps import require_role
from app.models import AuditLog, User
from app.schemas import CreateUserRequest, UserOut
from app.security import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_ROLES = {"restricted", "user", "developer", "admin", "superadmin"}


@router.get("/users", response_model=list[UserOut])
def list_users(
    _: User = Depends(require_role("admin")), db: Session = Depends(get_db)
) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in db.scalars(select(User).order_by(User.username))]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: CreateUserRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserOut:
    if body.role not in VALID_ROLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
    if body.role == "superadmin" and admin.role != "superadmin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only superadmin may create superadmin")
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")

    user = User(
        username=body.username,
        display_name=body.display_name or body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        allowed_channels=body.allowed_channels,
    )
    db.add(user)
    db.commit()
    audit(db, action="admin.user_created", risk_level="medium", user_id=admin.id,
          details={"new_user": body.username, "role": body.role})
    return UserOut.model_validate(user)


@router.get("/audit")
def list_audit(
    limit: int = 100,
    _: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.scalars(
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(min(limit, 500))
    )
    return [
        {
            "id": str(r.id),
            "timestamp": r.timestamp.isoformat(),
            "user_id": str(r.user_id) if r.user_id else None,
            "agent_id": r.agent_id,
            "action": r.action,
            "risk_level": r.risk_level,
            "status": r.status,
            "details": r.details,
        }
        for r in rows
    ]
