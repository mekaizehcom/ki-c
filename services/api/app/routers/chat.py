import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.db import SessionLocal, get_db
from app.deps import SESSION_COOKIE, get_current_user
from app.llm import (
    CONTEXT_WINDOWS,
    MOCK_MODEL,
    chat_completion,
    chat_completion_full,
    chat_stream,
    list_available_models,
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


def _model_for(conv: Conversation, ws_slug: str, db: Session) -> str:
    """Model selection: per-conversation override wins; otherwise the
    agent's MODELS.md/ROUTING.md-derived first-available choice."""
    if conv.model_override:
        return conv.model_override
    ws = load_workspace(ws_slug)
    agent = ws.agents.get(conv.agent_name)
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


def _approx_tokens(messages: list[dict]) -> int:
    """Very rough char/4 heuristic. Good enough for /status."""
    total = 0
    for m in messages:
        c = m.get("content")
        if isinstance(c, str):
            total += len(c)
    return total // 4


def _fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:,.1f} {u}"
        f /= 1024
    return f"{n} B"


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, _ = divmod(s, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or d:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def _build_status(db: Session, user: User, conv: Conversation, ws_slug: str) -> str:
    """Static, deterministic system report. No LLM."""
    import os
    import shutil
    import time

    from app.models import Document as _Doc
    from app.models import ModelProvider as _MP
    from app.models import User as _U
    from app.queue import _pool, queue_depth

    # Host
    try:
        with open("/proc/uptime") as fh:
            up = _fmt_duration(float(fh.read().split()[0]))
    except Exception:
        up = "?"
    meminfo: dict[str, int] = {}
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, _, rest = line.partition(":")
                meminfo[k.strip()] = int(rest.strip().split()[0]) * 1024
    except Exception:
        pass
    ram_total = meminfo.get("MemTotal", 0)
    ram_avail = meminfo.get("MemAvailable", 0)
    ram_used = max(0, ram_total - ram_avail)
    du = shutil.disk_usage("/")

    # Tessa
    try:
        hb = _pool.get("tessa:worker:heartbeat")
        worker = (f"alive ({int(time.time() - int(hb))}s ago)"
                  if hb and time.time() - int(hb) < 300 else "stale")
    except Exception:
        worker = "?"
    n_users = db.scalar(select(func.count()).select_from(_U)) or 0
    n_docs = db.scalar(select(func.count()).select_from(_Doc)) or 0
    n_convs = db.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == user.id)
    ) or 0

    # Conversation
    history = _history(db, conv)
    used_tokens = _approx_tokens(history)
    current_model = _model_for(conv, ws_slug, db)
    cw = CONTEXT_WINDOWS.get(current_model)
    if cw:
        pct = min(100.0, 100 * used_tokens / cw)
        ctx_line = f"{used_tokens:,} / {cw:,} tokens (~{pct:.1f}%)"
    else:
        ctx_line = f"{used_tokens:,} tokens (context window unknown)"

    # Providers
    prov_lines = []
    for p in ("openai", "anthropic", "deepseek"):
        row = db.get(_MP, p)
        on = bool(row and row.enabled and row.api_key_encrypted)
        prov_lines.append(f"  {p:10s} {'✓ enabled' if on else '– disabled'}")

    lines = [
        "**System**",
        f"  Uptime:    {up}",
        (f"  RAM:       {_fmt_bytes(ram_used)} / {_fmt_bytes(ram_total)} "
         f"used ({(100*ram_used/ram_total):.0f}%)") if ram_total else "  RAM: ?",
        (f"  Disk:      {_fmt_bytes(du.used)} / {_fmt_bytes(du.total)} "
         f"used ({(100*du.used/du.total):.0f}%)"),
        "",
        "**Tessa**",
        f"  Users:           {n_users}",
        f"  Your convs:      {n_convs}",
        f"  Documents:       {n_docs}",
        f"  Ingest queue:    {queue_depth()}",
        f"  Worker:          {worker}",
        f"  Workspace:       {ws_slug}",
        "",
        "**This conversation**",
        f"  Agent:           {conv.agent_name}",
        f"  Model:           {current_model}"
        + (f"  (override)" if conv.model_override else ""),
        f"  Messages:        {len(history)}",
        f"  Context (~):     {ctx_line}",
        "",
        "**Providers**",
        *prov_lines,
    ]
    return "\n".join(lines)


def _build_models_list(db: Session, conv: Conversation, ws_slug: str) -> str:
    available = list_available_models(db)
    current = _model_for(conv, ws_slug, db)
    lines = ["Available models (✓ = current):"]
    for m in available:
        mark = "✓" if m["name"] == current else " "
        lines.append(f"  {mark} {m['name']:<20s} ({m['provider']})")
    lines.append("")
    lines.append("Switch:  `/models <name>`     e.g. `/models claude-sonnet`")
    lines.append("Reset:   `/models reset`      (use the agent's default)")
    return "\n".join(lines)


HELP_TEXT = (
    "Available commands (handled directly, no model call):\n"
    "  /help                  — this list\n"
    "  /status                — system + conversation stats\n"
    "  /models                — list available models for this chat\n"
    "  /models <name>         — switch this conversation to a specific model\n"
    "  /models reset          — revert to the agent's default model\n"
    "  /agent                 — show current + available agents\n"
    "  /agent <name>          — switch this conversation to a different agent\n"
    "  /agent reset           — revert to `main`\n"
    "  /workspace             — show the current workspace\n"
    "  /approve <id> [totp]   — approve a pending action (admins; TOTP for high/critical)\n"
    "  /deny <id>             — deny a pending action\n"
    "  /link                  — show your SwissChat link status"
)


def _try_command(
    db: Session, user: User, conv: Conversation, ws_slug: str, text: str
) -> str | None:
    """If `text` is a slash command, handle it and return a reply string.
    Returns None if it's not a command — caller proceeds to the LLM."""
    if not text or not text.startswith("/"):
        return None
    parts = text.strip().split()
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        return HELP_TEXT

    if cmd == "/status":
        return _build_status(db, user, conv, ws_slug)

    if cmd == "/models":
        if not arg:
            return _build_models_list(db, conv, ws_slug)
        if arg.lower() == "reset":
            conv.model_override = None
            db.commit()
            audit(db, action="chat.model_reset", user_id=user.id,
                  agent_id=conv.agent_name,
                  details={"conversation": str(conv.id)})
            return ("Model override cleared — this conversation will use "
                    f"the agent's default ({_model_for(conv, ws_slug, db)}).")
        chosen = arg
        available = {m["name"]: m for m in list_available_models(db)}
        if chosen not in available:
            return (f"Unknown or unavailable model: `{chosen}`.\n\n"
                    + _build_models_list(db, conv, ws_slug))
        conv.model_override = chosen
        db.commit()
        audit(db, action="chat.model_override", user_id=user.id,
              agent_id=conv.agent_name,
              details={"conversation": str(conv.id), "model": chosen})
        return f"Model for this conversation set to **{chosen}**."

    if cmd == "/agent":
        ws = load_workspace(ws_slug)
        if not arg:
            names = ", ".join(ws.agents)
            return f"Current agent: **{conv.agent_name}**. Available: {names}"
        new_name = "main" if arg.lower() == "reset" else arg
        if new_name not in ws.agents:
            return (f"Unknown agent: `{new_name}`. Available: "
                    + ", ".join(ws.agents))
        conv.agent_name = new_name
        db.commit()
        audit(db, action="chat.agent_switched", user_id=user.id,
              agent_id=new_name,
              details={"conversation": str(conv.id), "to": new_name})
        return f"Agent switched to **{new_name}**."

    if cmd == "/workspace":
        # Multi-workspace UI isn't here yet; just report the current one.
        slugs = list_workspace_slugs()
        return (f"Current workspace: **{ws_slug}**\n"
                f"Available: {', '.join(slugs)}\n"
                f"(Switching workspaces from chat is not yet implemented.)")

    if cmd in ("/approve", "/deny"):
        from app.approvals import finalize_approval
        from app.models import Approval

        try:
            ap_id = uuid.UUID(arg)
        except Exception:
            return ("Usage: `/approve <approval_id> [totp]`  or  "
                    "`/deny <approval_id>`")
        ap = db.get(Approval, ap_id)
        if not ap:
            return f"Approval `{arg}` not found."
        totp = parts[2] if len(parts) > 2 else None
        res = finalize_approval(db, ap, user, approve=(cmd == "/approve"),
                                totp_code=totp)
        if res.get("status") == "totp_required":
            return ("TOTP required. Try: `/approve "
                    f"{arg} <6-digit code>`")
        if "result" in res:
            r = res["result"]
            tail = (r.get("stdout") or r.get("stderr") or "")[:600]
            return (f"Approval `{arg}` → **{res['status']}** "
                    f"(exit {r.get('exit_code')})\n{tail}")
        return (f"Approval `{arg}` → **{res.get('status')}** "
                f"{res.get('detail','')}").strip()

    if cmd == "/link":
        from app.models import SwisschatAccount

        rows = list(db.scalars(
            select(SwisschatAccount).where(SwisschatAccount.user_id == user.id)
        ))
        if not rows:
            return ("No SwissChat accounts linked to your Tessa user yet. "
                    "Open https://tessa.ki-c.pro/settings to link one.")
        linked = [r for r in rows if r.linked]
        if linked:
            ids = ", ".join(r.swisschat_user_id[:8] + "…" for r in linked)
            return f"Linked SwissChat account(s): {ids}"
        codes = ", ".join(r.link_code for r in rows if r.link_code)
        return ("Pending link. Enter this code (plus your TOTP) on "
                f"https://tessa.ki-c.pro/settings : {codes}")

    return None  # unknown slash command -> let the model see it


def _save_system_reply(
    db: Session, conv: Conversation, prompt: str, reply: str
) -> None:
    db.add(Message(conversation_id=conv.id, role="user", content=prompt))
    db.add(Message(conversation_id=conv.id, role="assistant", content=reply,
                   model="system"))
    db.commit()


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
        if cmd_name == "ssh_exec":
            details["remote_command"] = (args.get("command") or "")[:1000]
            details["cwd"] = args.get("cwd")
            if "result" in result:
                details["host"] = result["result"].get("host")
                details["stdout_tail"] = (result["result"].get("stdout") or "")[-600:]
                details["stderr_tail"] = (result["result"].get("stderr") or "")[-400:]
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
    # Slash commands short-circuit the LLM call.
    cmd_reply = _try_command(db, user, conv, ws_slug, message)
    if cmd_reply is not None:
        _save_system_reply(db, conv, message, cmd_reply)
        audit(db, action="chat.command", user_id=user.id,
              agent_id=conv.agent_name,
              details={"conversation": str(conv.id),
                       "command": message.split()[0],
                       "channel": conv.channel})
        return cmd_reply, "system", []

    agent_name = conv.agent_name
    db.add(Message(conversation_id=conv.id, role="user", content=message))
    db.commit()

    messages = [{"role": "system", "content": _system_prompt(ws_slug, agent_name)}]
    ctx, sources = _retrieval(user, ws_slug, message)
    if ctx:
        messages.append({"role": "system", "content": ctx})
    messages += _history(db, conv)

    model = _model_for(conv, ws_slug, db)
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
                # Slash commands short-circuit — no LLM, no streaming.
                cmd_reply = _try_command(db, user, conv, ws_slug, body.message)
                if cmd_reply is not None:
                    _save_system_reply(db, conv, body.message, cmd_reply)
                    audit(db, action="chat.command", user_id=user.id,
                          agent_id=conv.agent_name,
                          details={"conversation": str(conv.id),
                                   "command": body.message.split()[0],
                                   "channel": "web-ws"})
                    await ws.send_json({"type": "meta",
                                        "conversation_id": str(conv.id),
                                        "agent": conv.agent_name, "sources": []})
                    await ws.send_json({"type": "delta", "text": cmd_reply})
                    await ws.send_json({"type": "done", "model": "system",
                                        "conversation_id": str(conv.id)})
                    continue
                db.add(Message(conversation_id=conv.id, role="user", content=body.message))
                db.commit()
                messages = [{"role": "system",
                             "content": _system_prompt(ws_slug, agent_name)}]
                ctx, sources = _retrieval(user, ws_slug, body.message)
                if ctx:
                    messages.append({"role": "system", "content": ctx})
                messages += _history(db, conv)
                model = _model_for(conv, ws_slug, db)
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
