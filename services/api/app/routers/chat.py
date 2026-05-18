import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.db import SessionLocal, get_db
from app.deps import SESSION_COOKIE, get_current_user
from app.llm import (
    chat_completion,
    chat_completion_full,
    chat_stream,
    provider_credentials,
    resolve_models,
)
from app.models import Conversation, Message, SessionToken, User
from app.security import hash_token
from app.vectors import collection_for, embed_query, hybrid_rerank, search
from app.tools.engine import decide
from app.tools.executor import run, run_internal
from app.tools.registry import REGISTRY, build_argv
from app.workspace import list_workspace_slugs, load_workspace

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
            top_k=10,
        )
        hits = hybrid_rerank(query, hits, top_k=5)
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


MAX_TOOL_ITERATIONS = 5


def _agent_tools(db: Session, ws_slug: str, agent_name: str) -> list[str]:
    ws = load_workspace(ws_slug)
    a = ws.agents.get(agent_name)
    return list(a.tools) if a else []


def _build_tool_schemas(agent_tool_categories: list[str]) -> list[dict]:
    """Filter registry to commands whose tool-category the agent may use,
    and translate to OpenAI/Anthropic function-calling schema."""
    out: list[dict] = []
    for cmd in REGISTRY.values():
        if cmd.tool not in agent_tool_categories:
            continue
        if cmd.payload_schema:
            params = cmd.payload_schema
        elif cmd.arg_pattern:
            params = {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": (
                            f"Single argument. Must match regex: "
                            f"{cmd.arg_pattern}"
                        ),
                    }
                },
                "required": ["target"],
            }
        else:
            params = {"type": "object", "properties": {}}
        out.append({
            "type": "function",
            "function": {
                "name": cmd.name,
                "description": cmd.description,
                "parameters": params,
            },
        })
    return out


def _run_tool_in_chat(
    db: Session, user: User, ws_slug: str, agent_name: str,
    cmd_name: str, args: dict,
) -> dict:
    """Run a tool the model asked for. Goes through the permission engine.
    Returns a dict that we serialize back to the model as the tool result."""
    d = decide(db, user, ws_slug, agent_name, cmd_name)
    audit(db, action="tool.request", user_id=user.id, agent_id=agent_name,
          risk_level=d.risk,
          status="denied" if not d.allowed else "pending",
          details={"command": cmd_name, "args": args, "reason": d.reason,
                   "via": "chat"})

    if not d.allowed:
        return {"ok": False, "error": "denied", "reason": d.reason}
    if d.proposed:
        return {"ok": False, "status": "proposed",
                "reason": d.reason,
                "note": "agent autonomy is 'propose' — tool not executed"}
    if not d.execute_now:
        return {"ok": False, "status": "approval_required",
                "risk": d.risk, "approver_role": d.approver_role,
                "reason": d.reason,
                "note": "tell the user this needs approval at /approvals"}

    if d.command.internal is not None:
        result = run_internal(d.command, args, {"user_id": str(user.id)})
        details = {"command": cmd_name, "exit_code": result["exit_code"],
                   "via": "chat"}
        if cmd_name == "workspace_write" and "result" in result:
            details["file"] = result["result"].get("file")
            details["reason"] = result["result"].get("reason")
            details["diff"] = (result["result"].get("diff") or "")[:4000]
        audit(db, action="tool.executed", user_id=user.id, agent_id=agent_name,
              risk_level=d.risk,
              status="success" if result["exit_code"] == 0 else "failed",
              details=details)
        return result.get("result", result) if result["exit_code"] == 0 \
               else {"ok": False, "error": result.get("stderr", "failed")}

    # subprocess argv tool
    try:
        argv = build_argv(d.command, args.get("target"))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    result = run(argv)
    audit(db, action="tool.executed", user_id=user.id, agent_id=agent_name,
          risk_level=d.risk,
          status="success" if result["exit_code"] == 0 else "failed",
          details={"command": cmd_name, "target": args.get("target"),
                   "exit_code": result["exit_code"], "via": "chat"})
    return result


async def generate_reply(
    db: Session, user: User, conv: Conversation, message: str, ws_slug: str
) -> tuple[str, str, list[dict]]:
    """Shared turn: store user msg, retrieve, call model (with optional
    tool-use loop), persist, audit. Used by REST chat and SwissChat.
    WS path is text-only and bypasses tool-use today."""
    agent_name = conv.agent_name
    db.add(Message(conversation_id=conv.id, role="user", content=message))
    db.commit()

    messages = [{"role": "system", "content": _system_prompt(ws_slug, agent_name)}]
    ctx, sources = _retrieval(user, ws_slug, message)
    if ctx:
        messages.append({"role": "system", "content": ctx})
    messages += _history(db, conv)

    model = _model_for(ws_slug, agent_name, db)
    extra = provider_credentials(db, model)
    tool_schemas = _build_tool_schemas(_agent_tools(db, ws_slug, agent_name))
    if tool_schemas:
        extra["tools"] = tool_schemas

    used = model
    final_text = ""
    for _ in range(MAX_TOOL_ITERATIONS):
        msg, used = await chat_completion_full(model, messages, extra)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            final_text = msg.get("content") or ""
            break
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
        })
        for tc in tool_calls:
            fn = tc.get("function", {})
            cmd_name = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            tool_result = _run_tool_in_chat(
                db, user, ws_slug, agent_name, cmd_name, args
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "name": cmd_name,
                "content": json.dumps(tool_result, ensure_ascii=False)[:16000],
            })
    else:
        final_text = ("(Tool-Schleife unterbrochen nach "
                      f"{MAX_TOOL_ITERATIONS} Iterationen.)")

    db.add(Message(conversation_id=conv.id, role="assistant", content=final_text,
                   model=used, meta={"sources": sources}))
    conv.updated_at = conv.updated_at  # touch via onupdate
    db.commit()
    audit(db, action="chat.message", user_id=user.id, agent_id=agent_name,
          details={"model": used, "conversation": str(conv.id),
                   "sources": len(sources), "channel": conv.channel,
                   "tool_use": bool(tool_schemas)})
    return final_text, used, sources


@router.get("/workspaces")
def list_workspaces(_: User = Depends(get_current_user)) -> list[dict]:
    out = []
    for slug in list_workspace_slugs():
        try:
            ws = load_workspace(slug)
            out.append({"slug": ws.slug, "name": ws.name})
        except Exception:  # noqa: BLE001
            continue
    return out


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
                creds = provider_credentials(db, model)

                await ws.send_json({"type": "meta",
                                    "conversation_id": str(conv.id),
                                    "agent": agent_name,
                                    "sources": sources})
                full, used = "", model
                async for delta, m in chat_stream(model, messages, creds):
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
