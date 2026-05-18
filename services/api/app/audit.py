import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(
    db: Session,
    *,
    action: str,
    status: str = "success",
    risk_level: str = "low",
    user_id: uuid.UUID | None = None,
    agent_id: str | None = None,
    details: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            action=action,
            status=status,
            risk_level=risk_level,
            user_id=user_id,
            agent_id=agent_id,
            details=details or {},
        )
    )
    db.commit()
