import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.db import SessionLocal, get_db
from app.deps import SESSION_COOKIE, get_current_user
from app.llm import chat_completion, chat_stream, resolve_models
from app.models import Conversation, Message, SessionToken, User
from app.security import hash_token
from app.vectors import collection_for, embed_query, search
from app.workspace import load_workspace

router = APIRouter(prefix="/api", tags=["chat"])
ws_router = APIRouter(tags=["chat-ws"])  # no /api prefix: nginx routes /ws/

HISTORY_LIMIT = 20


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    workspace: str | None = None
    agent: str | None = None


def _system_prompt(ws_slug: str, agent_name: str) -> str:
    ws = load_workspace(ws_slug)
    agent = ws.agents.get(agent_name)
    parts = [ws.soul.strip()]
    if agent and agent.purpose:
        parts.append(f"\n# Agent: {agent_name}\n{agent.purpose}")
    return "\n".join(p for p in parts if p).strip()


def _model_for(ws_slug: str, agent_name: str, db: Session) -> str:
    ws = load_workspace(ws_slug)
    agent = ws.agents.get(agent_name)
    profile_name = agent.model_profile if agent else "default-balanced"
    prof = ws.model_profiles.get(profile_name)
    providers = prof.providers if prof else []
    return resolve_models(providers, db)[0]


def _get_or_create_conv(
    db: Session, user: User, body: ChatRequest, channel: str = "web"
) -> Conversation:
    if body.conversation_id:
        conv = db.get(Conversation, uuid.UUID(body.conversation_id))
        if not conv or conv.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
        return conv
    ws_slug = body.workspace or settings.default_workspace
    conv = Conversation(
        user_id=user.id,
        channel=channel,
        agent_name=body.agent or "main",
        title=body.message[:60] or "New conversation",
    )
    db.add(conv)
    db.commit()
    return conv


def _retrieval(user: User, ws_slug: str, query: str) -> tuple[str, list[dict]]:
    """Vector-retrieved context block + cited sources (§22)."""
    try:
        hits = search(
            collection_for(ws_slug),
            embed_query(query),
            role=user.role,
            user_id=str(user.id),
            workspace_id=None,
            top_k=5,
        )
    except Exception:
        hits = []
    if not hits:
        return "", []
    lines = ["# Kontext aus der Wissensbasis (zitiere Quellen):"]
    for i, h in enumerate(hits, 1):
        lines.append(f"[{i}] {h['filename']}#{h.get('seq')}: {h['text'][:600]}")
    return "\n".join(lines), [
        {"n": i, "filename": h["filename"], "document_id": h["document_id"],
         "score": round(h["score"], 4)}
        for i, h in enumerate(hits, 1)
    ]


def _history(db: Session, conv: Conversation) -> list[dict]:
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return [{"role": m.role, "content": m.content} for m in reversed(rows)]


async def generate_reply(
    db: Session, user: User, conv: Conversation, message: str, ws_slug: str
) -> tuple[str, str, list[dict]]:
    """Shared turn: store user msg, retrieve, call model, persist, audit.

    Used by REST chat and the SwissChat connector (WS uses its own
    streaming path).
    """
    agent_name = conv.agent_name
    db.add(Message(conversation_id=conv.id, role="user", content=message))
    db.commit()

    messages = [{"role": "system", "content": _system_prompt(ws_slug, agent_name)}]
    ctx, sources = _retrieval(user, ws_slug, message)
    if ctx:
        messages.append({"role": "system", "content": ctx})
    messages += _history(db, conv)

    model = _model_for(ws_slug, agent_name, db)
    reply, used = await chat_completion(model, messages)

    db.add(Message(conversation_id=conv.id, role="assistant", content=reply,
                   model=used, meta={"sources": sources}))
    conv.updated_at = conv.updated_at  # touch via onupdate
    db.commit()
    audit(db, action="chat.message", user_id=user.id, agent_id=agent_name,
          details={"model": used, "conversation": str(conv.id),
                   "sources": len(sources), "channel": conv.channel})
    return reply, used, sources


@router.get("/workspaces")
def list_workspaces(_: User = Depends(get_current_user)) -> list[dict]:
    ws = load_workspace(settings.default_workspace)
    return [{"slug": ws.slug, "name": ws.name}]


@router.get("/agents")
def list_agents(
    workspace: str | None = None, _: User = Depends(get_current_user)
) -> list[dict]:
    ws = load_workspace(workspace or settings.default_workspace)
    return [
        {
            "name": a.name,
            "purpose": a.purpose,
            "model_profile": a.model_profile,
            "autonomy": a.autonomy,
        }
        for a in ws.agents.values()
    ]


@router.get("/conversations")
def list_conversations(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id, Conversation.status == "active")
        .order_by(Conversation.updated_at.desc())
        .limit(50)
    )
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "agent": c.agent_name,
            "channel": c.channel,
            "updated_at": c.updated_at.isoformat(),
        }
        for c in rows
    ]


@router.get("/conversations/{cid}")
def get_conversation(
    cid: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    conv = db.get(Conversation, uuid.UUID(cid))
    if not conv or conv.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    msgs = db.scalars(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
    )
    return {
        "id": str(conv.id),
        "title": conv.title,
        "agent": conv.agent_name,
        "messages": [
            {"role": m.role, "content": m.content, "model": m.model} for m in msgs
        ],
    }


@router.post("/chat")
async def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not body.message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty message")
    ws_slug = body.workspace or settings.default_workspace
    conv = _get_or_create_conv(db, user, body)
    reply, used, sources = await generate_reply(db, user, conv, body.message, ws_slug)
    return {
        "conversation_id": str(conv.id),
        "reply": reply,
        "model": used,
        "agent": conv.agent_name,
        "sources": sources,
    }


def _user_from_cookie(raw: str | None) -> User | None:
    if not raw:
        return None
    db = SessionLocal()
    try:
        st = db.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(raw)))
        if not st or st.revoked:
            return None
        return db.get(User, st.user_id)
    finally:
        db.close()


@ws_router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket) -> None:
    await ws.accept()
    user = _user_from_cookie(ws.cookies.get(SESSION_COOKIE))
    if not user:
        await ws.send_json({"type": "error", "error": "unauthorized"})
        await ws.close()
        return
    try:
        while True:
            data = await ws.receive_json()
            body = ChatRequest(**data)
            db = SessionLocal()
            try:
                ws_slug = body.workspace or settings.default_workspace
                conv = _get_or_create_conv(db, user, body)
                agent_name = conv.agent_name
                db.add(Message(conversation_id=conv.id, role="user", content=body.message))
                db.commit()
                messages = [{"role": "system",
                             "content": _system_prompt(ws_slug, agent_name)}]
                ctx, sources = _retrieval(user, ws_slug, body.message)
                if ctx:
                    messages.append({"role": "system", "content": ctx})
                messages += _history(db, conv)
                model = _model_for(ws_slug, agent_name, db)

                await ws.send_json({"type": "meta",
                                    "conversation_id": str(conv.id),
                                    "agent": agent_name,
                                    "sources": sources})
                full, used = "", model
                async for delta, m in chat_stream(model, messages):
                    full += delta
                    used = m
                    await ws.send_json({"type": "delta", "text": delta})
                db.add(Message(conversation_id=conv.id, role="assistant",
                               content=full, model=used,
                               meta={"sources": sources}))
                db.commit()
                audit(db, action="chat.message", user_id=user.id,
                      agent_id=agent_name,
                      details={"model": used, "conversation": str(conv.id),
                               "channel": "web-ws"})
                await ws.send_json({"type": "done", "model": used,
                                    "conversation_id": str(conv.id)})
            finally:
                db.close()
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        await ws.send_json({"type": "error", "error": str(exc)})
        await ws.close()
