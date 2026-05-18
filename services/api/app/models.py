"""SQLAlchemy models for the §23 data model.

All tables from the architecture doc are defined so the schema is complete
from Phase 1; later phases fill in the behaviour around them.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class Role(Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")
    rank: Mapped[int] = mapped_column(Integer, default=0)  # higher = more power


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(50), ForeignKey("roles.name"), default="user")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|disabled|locked
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    allowed_channels: Mapped[list] = mapped_column(JSONB, default=lambda: ["web", "swisschat"])

    totp_secret: Mapped["TotpSecret"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class TotpSecret(Base):
    __tablename__ = "totp_secrets"
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    secret: Mapped[str] = mapped_column(Text, nullable=False)  # encrypted (Fernet)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    user: Mapped["User"] = relationship(back_populates="totp_secret")


class SessionToken(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), default="")
    config: Mapped[dict] = mapped_column(JSONB, default=dict)


class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("workspaces.id"))
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="")
    model_profile: Mapped[str] = mapped_column(String(80), default="default-balanced")
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    autonomy: Mapped[str] = mapped_column(String(40), default="approve_required")
    approval_actions: Mapped[list] = mapped_column(JSONB, default=list)
    allowed_auto_actions: Mapped[list] = mapped_column(JSONB, default=list)
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_agent_ws_name"),)


class Tool(Base):
    __tablename__ = "tools"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")
    allowed: Mapped[list] = mapped_column(JSONB, default=list)
    denied: Mapped[list] = mapped_column(JSONB, default=list)
    default_risk: Mapped[str] = mapped_column(String(20), default="medium")
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)


class ModelProfile(Base):
    __tablename__ = "model_profiles"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    purpose: Mapped[str] = mapped_column(Text, default="")
    providers: Mapped[list] = mapped_column(JSONB, default=list)  # ordered model names


class ModelProvider(Base, TimestampMixin):
    __tablename__ = "model_providers"
    name: Mapped[str] = mapped_column(String(60), primary_key=True)  # openai|anthropic|deepseek
    display_name: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(80), default="main")
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    status: Mapped[str] = mapped_column(String(20), default="active")
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))  # user|assistant|system|tool
    content: Mapped[str] = mapped_column(Text, default="")
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    requested_by: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(80))
    tool_name: Mapped[str] = mapped_column(String(80))
    action_name: Mapped[str] = mapped_column(String(120))
    risk_level: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    request_payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(160))
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    status: Mapped[str] = mapped_column(String(30), default="success")
    details: Mapped[dict] = mapped_column(JSONB, default=dict)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    visibility: Mapped[str] = mapped_column(String(20), default="workspace")
    status: Mapped[str] = mapped_column(String(20), default="uploaded")  # uploaded|ingested|failed
    checksum: Mapped[str] = mapped_column(String(80), default="")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    vector_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class VectorSource(Base):
    __tablename__ = "vector_sources"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    source_type: Mapped[str] = mapped_column(String(40))  # document|chat|memory|log|config
    source_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="workspace")
    collection: Mapped[str] = mapped_column(String(80), default="tessa")
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    checksum: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SwisschatAccount(Base):
    __tablename__ = "swisschat_accounts"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    swisschat_user_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    link_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    linked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class IntegrationCredential(Base, TimestampMixin):
    """Encrypted credential blob for an external integration (e.g. swisschat).

    `data_encrypted` is Fernet(JSON) holding tokens/secrets; `public` holds
    non-secret metadata safe to display in the admin UI.
    """

    __tablename__ = "integration_credentials"
    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    data_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    public: Mapped[dict] = mapped_column(JSONB, default=dict)


class SystemEvent(Base):
    __tablename__ = "system_events"
    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
