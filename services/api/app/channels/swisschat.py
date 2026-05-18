"""SwissChat Bot Protocol v1 client.

Spec: docs/bot-protocol/README.md of the swisschat repo.
- Pairing:  POST {api_base}/api/v1/bots/register
- Inbound:  signed webhook (X-SwissChat-Signature: sha256=HMAC_SHA256(body))
- Outbound: POST {api_base}/api/v1/messages  (Bearer service_token)
"""

from __future__ import annotations

import hashlib
import hmac

import httpx

DEFAULT_API_BASE = "https://swisschat.konnektai.pro"


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


async def send_message(
    api_base: str,
    service_token: str,
    conversation_id: str,
    plaintext: str,
    client_message_id: str | None = None,
) -> tuple[bool, str]:
    """Outbound message (protocol §5.1). Returns (ok, detail)."""
    body: dict = {"conversation_id": conversation_id, "kind": "text",
                  "plaintext": plaintext[:32000]}
    if client_message_id:
        body["client_message_id"] = client_message_id
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{api_base.rstrip('/')}/api/v1/messages",
                headers={"Authorization": f"Bearer {service_token}"},
                json=body,
            )
        if r.status_code == 200:
            return True, "ok"
        if r.status_code == 409:  # idempotent duplicate -> treat as success
            return True, "duplicate"
        return False, f"{r.status_code}: {r.text[:200]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
