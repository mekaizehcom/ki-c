"""SwissChat connector: signed webhook in, REST out, user linking, commands."""

from __future__ import annotations

import logging
import secrets
import traceback

import httpx

logger = logging.getLogger("tessa.swisschat")
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.approvals import finalize_approval
from app.audit import audit
from app.channels.swisschat import (
    DEFAULT_API_BASE,
    register_bot,
    send_message,
    verify_signature,
)
from app.config import settings
from app.db import SessionLocal, get_db
from app.deps import get_current_user, require_role
from app.integrations import SWISSCHAT, forget, get_credentials, get_public, save_credentials
from app.models import Approval, Conversation, SwisschatAccount, TotpSecret, User
from app.queue import queue_depth, seen_once
from app.routers.chat import generate_reply, _try_command
from app.security import decrypt, verify_totp
from app.workspace import load_workspace

router = APIRouter(tags=["swisschat"])  # webhook has NO /api prefix (nginx /webhook/)
api_router = APIRouter(prefix="/api", tags=["swisschat-api"])
admin_router = APIRouter(prefix="/api/admin/swisschat", tags=["swisschat-admin"])

def _new_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


def _conv_for(db: Session, user: User, sc_conv_id: str) -> Conversation:
    conv = db.scalar(
        select(Conversation).where(
            Conversation.channel == "swisschat",
            Conversation.external_id == sc_conv_id,
        )
    )
    if not conv:
        conv = Conversation(
            user_id=user.id, channel="swisschat", external_id=sc_conv_id,
            agent_name="main", title=f"SwissChat {sc_conv_id[:8]}",
        )
        db.add(conv)
        db.commit()
    return conv


async def _handle_command(
    db: Session, user: User, conv: Conversation, text: str
) -> str | None:
    """SwissChat command path — delegates to the unified _try_command in
    chat.py so both channels share /help, /status, /models, /agent,
    /approve, /deny, /link, /workspace. Falls back to the German
    'Unbekannter Befehl' nudge for unknown slash inputs (in the web chat
    these fall through to the model instead)."""
    reply = _try_command(db, user, conv, settings.default_workspace, text)
    if reply is not None:
        return reply
    return "Unbekannter Befehl. /help für die Liste."


async def _process(raw_event: dict) -> None:
    print(f"[swisschat] event keys={sorted(raw_event)} type={raw_event.get('type')!r} "
          f"conv={raw_event.get('conversation_id')!r} "
          f"sender={raw_event.get('sender_user_id')!r} "
          f"msg_id={raw_event.get('message_id')!r}", flush=True)
    db = SessionLocal()
    try:
        await _process_inner(db, raw_event)
    except Exception:
        print("[swisschat] _process crashed:\n" + traceback.format_exc(), flush=True)
    finally:
        db.close()


async def _process_inner(db, raw_event: dict) -> None:
    creds = get_credentials(db, SWISSCHAT)
    if not creds:
        print("[swisschat] no creds, ignoring", flush=True)
        return
    if raw_event.get("type") != "message":
        print(f"[swisschat] non-message event {raw_event.get('type')!r} ignored",
              flush=True)
        return
    msg_id = raw_event.get("message_id") or ""
    sender = raw_event.get("sender_user_id") or ""
    sc_conv = raw_event.get("conversation_id") or ""
    text = (raw_event.get("plaintext") or "").strip()
    if not sender or not sc_conv:
        print(f"[swisschat] missing sender/conv (sender={sender!r}, "
              f"conv={sc_conv!r}) -- skipping", flush=True)
        return
    if sender == creds.get("bot_user_id"):
        print("[swisschat] self-echo skipped", flush=True)
        return
    if msg_id and seen_once(f"swisschat:seen:{msg_id}"):
        print(f"[swisschat] duplicate msg_id={msg_id} skipped", flush=True)
        return

    api_base = creds.get("api_base", DEFAULT_API_BASE)
    token = creds.get("service_token", "")

    async def reply(t: str) -> None:
        ok, detail = await send_message(api_base, token, sc_conv, t,
                                        client_message_id=f"tessa-{msg_id}")
        if not ok:
            print(f"[swisschat] send_message FAILED: {detail}", flush=True)
        else:
            print(f"[swisschat] sent reply ({len(t)} chars)", flush=True)

    acc = db.scalar(
        select(SwisschatAccount).where(
            SwisschatAccount.swisschat_user_id == sender
        )
    )
    if not acc:
        acc = SwisschatAccount(swisschat_user_id=sender,
                               link_code=_new_code(), linked=False)
        db.add(acc)
        db.commit()
        print(f"[swisschat] new SwisschatAccount for {sender!r}, "
              f"link_code={acc.link_code}", flush=True)
    if not acc.linked or not acc.user_id:
        await reply(
            "Dieses SwissChat-Konto ist noch nicht mit Tessa verknüpft.\n"
            f"Öffne {settings.public_base_url}/settings, melde dich an "
            f"und gib diesen Code ein: {acc.link_code}"
        )
        return

    user = db.get(User, acc.user_id)
    if not user or user.status != "active":
        await reply("Verknüpftes Tessa-Konto ist inaktiv.")
        return

    conv = _conv_for(db, user, sc_conv)
    if text.startswith("/"):
        out = await _handle_command(db, user, conv, text)
        await reply(out or "Unbekannter Befehl. /help für Hilfe.")
        return
    if not text:
        return
    answer, _model, _src = await generate_reply(
        db, user, conv, text, settings.default_workspace
    )
    await reply(answer)


@router.post("/webhook/swisschat")
async def webhook(request: Request, bg: BackgroundTasks) -> dict:
    raw = await request.body()
    db = SessionLocal()
    try:
        creds = get_credentials(db, SWISSCHAT)
    finally:
        db.close()
    if not creds:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SwissChat not paired")
    sig = request.headers.get("X-SwissChat-Signature")
    if not verify_signature(raw, sig, creds.get("webhook_secret", "")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad signature")
    import json

    try:
        event = json.loads(raw)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid JSON")
    # log truncated raw body so we see what SwissChat actually sends
    snippet = raw[:600].decode("utf-8", errors="replace")
    print(f"[swisschat] webhook accepted ({len(raw)}B): {snippet}", flush=True)
    bg.add_task(_process, event)  # ack fast (<10s), process async
    return {"ok": True}


# ---- web: user linking ----
class LinkRequest(BaseModel):
    code: str
    totp_code: str


@api_router.post("/swisschat/link")
def link_account(
    body: LinkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    ts = db.get(TotpSecret, user.id)
    if not ts or not verify_totp(decrypt(ts.secret), body.totp_code):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "TOTP confirmation failed")
    acc = db.scalar(
        select(SwisschatAccount).where(
            SwisschatAccount.link_code == body.code,
            SwisschatAccount.linked == False,  # noqa: E712
        )
    )
    if not acc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invalid or used code")
    acc.user_id = user.id
    acc.linked = True
    acc.link_code = None
    db.commit()
    audit(db, action="swisschat.linked", user_id=user.id,
          details={"swisschat_user_id": acc.swisschat_user_id})
    return {"status": "linked", "swisschat_user_id": acc.swisschat_user_id}


@api_router.get("/swisschat/me")
def my_links(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.scalars(
        select(SwisschatAccount).where(SwisschatAccount.user_id == user.id)
    )
    return [{"swisschat_user_id": a.swisschat_user_id, "linked": a.linked}
            for a in rows]


# ---- admin: pairing ----
class PairRequest(BaseModel):
    pairing_code: str
    bot_username: str = "tessa"
    webhook_url: str | None = None
    api_base: str | None = None


@admin_router.post("/pair")
async def pair(
    body: PairRequest,
    admin: User = Depends(require_role("superadmin")),
    db: Session = Depends(get_db),
) -> dict:
    api_base = body.api_base or DEFAULT_API_BASE
    webhook_url = body.webhook_url or f"{settings.public_base_url}/webhook/swisschat"
    try:
        data = await register_bot(api_base, body.pairing_code, webhook_url,
                                  body.bot_username)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Pairing failed: {exc.response.status_code} "
                            f"{exc.response.text[:200]}")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Pairing error: {exc}")

    save_credentials(
        db, SWISSCHAT,
        secret_data={
            "bot_user_id": data.get("bot_user_id"),
            "bot_username": data.get("bot_username"),
            "service_token": data.get("service_token"),
            "webhook_secret": data.get("webhook_secret"),
            "api_base": api_base,
        },
        public={"bot_username": data.get("bot_username"),
                "webhook_url": webhook_url, "api_base": api_base},
    )
    audit(db, action="swisschat.paired", user_id=admin.id, risk_level="high",
          details={"bot_username": data.get("bot_username")})
    return {"status": "paired", "bot_username": data.get("bot_username"),
            "webhook_url": webhook_url}


@admin_router.get("")
def status_(
    _: User = Depends(require_role("admin")), db: Session = Depends(get_db)
) -> dict:
    return get_public(db, SWISSCHAT)


@admin_router.delete("")
def forget_(
    admin: User = Depends(require_role("superadmin")), db: Session = Depends(get_db)
) -> dict:
    forget(db, SWISSCHAT)
    audit(db, action="swisschat.forgotten", user_id=admin.id, risk_level="high")
    return {"status": "forgotten"}
