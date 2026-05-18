"""SwissChat Bot Protocol v1 client.

Spec: docs/bot-protocol/README.md of the swisschat repo.
- Pairing:  POST {api_base}/api/v1/bots/register
- Inbound:  signed webhook (X-SwissChat-Signature: sha256=HMAC_SHA256(body))
- Outbound: POST {api_base}/api/v1/messages  (Bearer service_token)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx
import redis

from app.config import settings

DEFAULT_API_BASE = "https://swisschat.konnektai.pro"
_redis = redis.from_url(settings.redis_url)
_ACCESS_KEY = "tessa:swisschat:access_token"
_REFRESH_MARGIN_S = 60  # refresh if <60s of validity remains


def expected_signature(raw_body: bytes, webhook_secret: str) -> str:
    return "sha256=" + hmac.new(
        webhook_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()


def verify_signature(raw_body: bytes, header: str | None, webhook_secret: str) -> bool:
    """Constant-time HMAC check (protocol §4.1, MANDATORY)."""
    if not webhook_secret:
        return False
    return hmac.compare_digest(
        header or "", expected_signature(raw_body, webhook_secret)
    )


async def register_bot(
    api_base: str, pairing_code: str, webhook_url: str, bot_username: str
) -> dict:
    """Redeem a one-time pairing code (protocol §3.2). Returns creds dict."""
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{api_base.rstrip('/')}/api/v1/bots/register",
            json={
                "pairing_code": pairing_code,
                "webhook_url": webhook_url,
                "bot_username": bot_username,
            },
        )
        r.raise_for_status()
        return r.json()


async def _exchange_for_access_token(
    api_base: str, service_token: str
) -> tuple[str, int]:
    """Exchange the long-lived service_token for a short-lived access JWT
    (protocol §6). Despite being framed as "WS-only" in the doc, the REST
    /api/v1/messages endpoint ALSO requires this JWT, not the service_token."""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            f"{api_base.rstrip('/')}/api/v1/bots/me/ws-token",
            headers={"Authorization": f"Bearer {service_token}"},
        )
        r.raise_for_status()
        data = r.json()
    return data["access_token"], int(data.get("expires_in", 3600))


async def get_access_token(api_base: str, service_token: str) -> str:
    """Return a valid access JWT, refreshing it via the service_token when
    the cached one is missing or near expiry. Cached in Redis so all
    workers share one token and renew rarely."""
    cached = _redis.get(_ACCESS_KEY)
    if cached:
        try:
            payload = json.loads(cached)
            if payload.get("expires_at", 0) - time.time() > _REFRESH_MARGIN_S:
                return payload["access_token"]
        except Exception:
            pass
    access, expires_in = await _exchange_for_access_token(api_base, service_token)
    _redis.set(
        _ACCESS_KEY,
        json.dumps({"access_token": access,
                    "expires_at": int(time.time()) + expires_in}),
        ex=max(60, expires_in - _REFRESH_MARGIN_S),
    )
    return access


def invalidate_access_token() -> None:
    _redis.delete(_ACCESS_KEY)


async def send_message(
    api_base: str,
    service_token: str,
    conversation_id: str,
    plaintext: str,
    client_message_id: str | None = None,
) -> tuple[bool, str]:
    """Outbound message — bot path.

    The public bot-protocol doc shows POST /api/v1/messages, but the real
    server has a separate bot endpoint at POST /api/v1/bots/messages that
    is explicitly server-side plaintext (ADR-042) and takes the
    service_token directly as Bearer (no sealed envelope, no JWT exchange).
    The /messages path requires sealed envelopes from human clients
    (ADR-021) and rejects plaintext.
    """
    body: dict = {"conversation_id": conversation_id, "kind": "text",
                  "plaintext": plaintext[:32000]}
    if client_message_id:
        body["client_message_id"] = client_message_id
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{api_base.rstrip('/')}/api/v1/bots/messages",
                headers={"Authorization": f"Bearer {service_token}"},
                json=body,
            )
        if r.status_code == 200 or r.status_code == 201:
            return True, "ok"
        if r.status_code == 409:
            return True, "duplicate"
        return False, f"{r.status_code}: {r.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
