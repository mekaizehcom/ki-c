from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.db import get_db
from app.deps import require_role
from app.models import (
    Agent,
    AuditLog,
    Conversation,
    Document,
    ModelProvider,
    TotpSecret,
    User,
    Workspace,
)
from app.queue import enqueue_ingest, queue_depth
from app.schemas import CreateUserRequest, UserOut
from app.security import decrypt, encrypt, hash_password, verify_totp
from app.vectors import collection_for

router = APIRouter(prefix="/api/admin", tags=["admin"])

VALID_ROLES = {"restricted", "user", "developer", "admin", "superadmin"}
KNOWN_PROVIDERS = ["openai", "anthropic", "deepseek"]
AUTONOMY_LEVELS = {"none", "propose", "approve_required", "scoped_auto", "full_auto"}


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


# ---------- user role/status management ----------
class UpdateUserRequest(BaseModel):
    role: str | None = None
    status: str | None = None


@router.put("/users/{username}", response_model=UserOut)
def update_user(
    username: str,
    body: UpdateUserRequest,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> UserOut:
    target = db.scalar(select(User).where(User.username == username))
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid role")
        if admin.role != "superadmin":
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Only superadmin may change roles")
        target.role = body.role
    if body.status is not None:
        if body.status not in {"active", "disabled", "locked"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid status")
        if target.role in ("admin", "superadmin") and admin.role != "superadmin":
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Cannot modify an admin")
        target.status = body.status
        if body.status == "active":
            target.locked_until = None
            target.failed_login_count = 0
    db.commit()
    audit(db, action="admin.user_updated", risk_level="medium",
          user_id=admin.id, details={"target": username,
                                      "role": body.role, "status": body.status})
    return UserOut.model_validate(target)


# ---------- model providers (encrypted API keys) ----------
class ProviderUpdate(BaseModel):
    api_key: str | None = None
    enabled: bool | None = None
    base_url: str | None = None


@router.get("/models")
def list_providers(
    _: User = Depends(require_role("admin")), db: Session = Depends(get_db)
) -> list[dict]:
    out = []
    for name in KNOWN_PROVIDERS:
        row = db.get(ModelProvider, name)
        out.append({
            "provider": name,
            "configured": bool(row and row.api_key_encrypted),
            "enabled": bool(row and row.enabled),
            "base_url": (row.base_url if row else None),
        })
    return out


@router.put("/models/{provider}")
def update_provider(
    provider: str,
    body: ProviderUpdate,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
) -> dict:
    if provider not in KNOWN_PROVIDERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown provider")
    row = db.get(ModelProvider, provider)
    if not row:
        row = ModelProvider(name=provider, display_name=provider.title())
        db.add(row)
    if body.api_key:
        row.api_key_encrypted = encrypt(body.api_key)
    if body.base_url is not None:
        row.base_url = body.base_url or None
    if body.enabled is not None:
        row.enabled = body.enabled
    db.commit()
    audit(db, action="admin.provider_updated", risk_level="critical",
          user_id=admin.id, details={"provider": provider,
                                      "enabled": row.enabled,
                                      "key_set": bool(body.api_key)})
    return {"provider": provider, "configured": bool(row.api_key_encrypted),
            "enabled": row.enabled}


# ---------- per-agent autonomy ----------
class AgentUpdate(BaseModel):
    autonomy: str | None = None
    allowed_auto_actions: list[str] | None = None


def _default_ws(db: Session) -> Workspace:
    ws = db.scalar(select(Workspace).where(
        Workspace.slug == settings.default_workspace))
    if not ws:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace missing")
    return ws


@router.get("/agents")
def list_agents_admin(
    _: User = Depends(require_role("admin")), db: Session = Depends(get_db)
) -> list[dict]:
    ws = _default_ws(db)
    rows = db.scalars(select(Agent).where(Agent.workspace_id == ws.id))
    return [{"name": a.name, "autonomy": a.autonomy,
             "allowed_auto_actions": a.allowed_auto_actions,
             "tools": a.tools} for a in rows]


@router.put("/agents/{name}")
def update_agent(
    name: str,
    body: AgentUpdate,
    admin: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
) -> dict:
    ws = _default_ws(db)
    agent = db.scalar(select(Agent).where(
        Agent.workspace_id == ws.id, Agent.name == name))
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    if body.autonomy is not None:
        if body.autonomy not in AUTONOMY_LEVELS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"autonomy must be one of {sorted(AUTONOMY_LEVELS)}")
        agent.autonomy = body.autonomy
    if body.allowed_auto_actions is not None:
        agent.allowed_auto_actions = body.allowed_auto_actions
    db.commit()
    audit(db, action="admin.agent_updated", risk_level="high",
          user_id=admin.id, details={"agent": name,
                                      "autonomy": agent.autonomy})
    return {"name": name, "autonomy": agent.autonomy,
            "allowed_auto_actions": agent.allowed_auto_actions}


# ---------- system status + Tessa self-management ----------
@router.get("/system")
def system_status(
    _: User = Depends(require_role("admin")), db: Session = Depends(get_db)
) -> dict:
    providers = {
        p: bool((r := db.get(ModelProvider, p)) and r.enabled and r.api_key_encrypted)
        for p in KNOWN_PROVIDERS
    }
    return {
        "ingest_queue": queue_depth(),
        "providers_active": providers,
        "users": db.scalar(select(func.count()).select_from(User)),
        "conversations": db.scalar(select(func.count()).select_from(Conversation)),
        "documents": db.scalar(select(func.count()).select_from(Document)),
        "default_workspace": settings.default_workspace,
    }


@router.post("/vector/reindex-failed")
def reindex_failed(
    admin: User = Depends(require_role("admin")), db: Session = Depends(get_db)
) -> dict:
    import os

    docs = list(db.scalars(select(Document).where(Document.status == "failed")))
    n = 0
    for d in docs:
        ext = os.path.splitext(d.filename)[1].lower()
        path = f"/data/uploads/{d.id}{ext}"
        if not os.path.exists(path):
            continue
        d.status = "uploaded"
        enqueue_ingest({
            "document_id": str(d.id), "path": path, "ext": ext,
            "workspace_id": str(d.workspace_id) if d.workspace_id else None,
            "workspace_slug": settings.default_workspace,
            "user_id": str(d.uploaded_by) if d.uploaded_by else "",
            "visibility": d.visibility, "filename": d.filename,
            "checksum": d.checksum,
        })
        n += 1
    db.commit()
    audit(db, action="admin.vector_reindex_failed", user_id=admin.id,
          details={"requeued": n})
    return {"requeued": n}


class CriticalRequest(BaseModel):
    totp_code: str


@router.delete("/vector/collection")
def delete_collection(
    body: CriticalRequest,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
) -> dict:
    ts = db.get(TotpSecret, admin.id)
    if not ts or not verify_totp(decrypt(ts.secret), body.totp_code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED,
                            "TOTP re-confirmation required (critical action)")
    from qdrant_client import QdrantClient

    coll = collection_for(settings.default_workspace)
    try:
        QdrantClient(url=settings.qdrant_url, timeout=30).delete_collection(coll)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Qdrant error: {exc}")
    audit(db, action="admin.vector_collection_deleted", risk_level="critical",
          status="success", user_id=admin.id, details={"collection": coll})
    return {"status": "deleted", "collection": coll}
