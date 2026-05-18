"""LiteLLM client + model router.

A model profile (from MODELS.md) is an ordered list of `provider/model`
tokens. We map each to a LiteLLM model_name, keep only those whose provider
key is configured (env or DB), and try them in order. If none are
available we fall back to `mock-echo`, which always works without keys.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ModelProvider

MOCK_MODEL = "mock-echo"

# MODELS.md token  ->  LiteLLM model_name (see infra/litellm/config.yaml)
TOKEN_MAP = {
    "openai/gpt-4o-mini": "gpt-4o-mini",
    "openai/gpt-4.1": "gpt-4.1",
    "openai/gpt-5": "gpt-4.1",
    "anthropic/claude-haiku": "claude-haiku",
    "anthropic/claude-sonnet": "claude-sonnet",
    "deepseek/deepseek-chat": "deepseek-chat",
    "deepseek/deepseek-reasoner": "deepseek-reasoner",
}

PROVIDER_OF = {
    "gpt-4o-mini": "openai",
    "gpt-4.1": "openai",
    "claude-haiku": "anthropic",
    "claude-sonnet": "anthropic",
    "deepseek-chat": "deepseek",
    "deepseek-reasoner": "deepseek",
}

_ENV_KEY = {
    "openai": settings.openai_api_key,
    "anthropic": settings.anthropic_api_key,
    "deepseek": settings.deepseek_api_key,
}


def _provider_available(db: Session | None, provider: str) -> bool:
    if _ENV_KEY.get(provider):
        return True
    if db is not None:
        row = db.get(ModelProvider, provider)
        if row and row.enabled and row.api_key_encrypted:
            return True
    return False


def provider_credentials(db: Session | None, model: str) -> dict:
    """Resolve {api_key, api_base} for a model: DB (admin UI) wins over env.

    Returned dict is merged into the LiteLLM request body so UI-entered
    keys take effect without restarting the gateway.
    """
    if model == MOCK_MODEL:
        return {}
    provider = PROVIDER_OF.get(model, "")
    if db is not None:
        row = db.get(ModelProvider, provider)
        if row and row.enabled and row.api_key_encrypted:
            from app.security import decrypt

            out: dict = {"api_key": decrypt(row.api_key_encrypted)}
            if row.base_url:
                out["api_base"] = row.base_url
            return out
    key = _ENV_KEY.get(provider)
    return {"api_key": key} if key else {}


def resolve_models(profile_providers: list[str], db: Session | None = None) -> list[str]:
    """Ordered list of usable LiteLLM model names, mock-echo last."""
    out: list[str] = []
    for tok in profile_providers:
        name = TOKEN_MAP.get(tok.strip())
        if not name or name in out:
            continue
        if _provider_available(db, PROVIDER_OF.get(name, "")):
            out.append(name)
    out.append(MOCK_MODEL)
    return out


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.litellm_master_key}"}


async def chat_completion(
    model: str, messages: list[dict], extra: dict | None = None
) -> tuple[str, str]:
    """Non-streaming. Returns (text, model_used). Falls back to mock-echo."""
    url = f"{settings.litellm_base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        for m in (model, MOCK_MODEL):
            try:
                body = {"model": m, "messages": messages}
                if m == model and extra:
                    body.update(extra)
                r = await client.post(url, headers=_headers(), json=body)
                r.raise_for_status()
                data = r.json()
                return data["choices"][0]["message"]["content"], m
            except Exception:
                continue
    return ("Tessa konnte kein Modell erreichen. Bitte Provider-Key im "
            "Admin-Bereich konfigurieren."), "none"


async def chat_stream(
    model: str, messages: list[dict], extra: dict | None = None
) -> AsyncIterator[tuple[str, str]]:
    """Yields (delta_text, model_used). Falls back to mock-echo on failure."""
    url = f"{settings.litellm_base_url}/chat/completions"
    async with httpx.AsyncClient(timeout=120) as client:
        for m in (model, MOCK_MODEL):
            try:
                body = {"model": m, "messages": messages, "stream": True}
                if m == model and extra:
                    body.update(extra)
                async with client.stream(
                    "POST", url, headers=_headers(), json=body,
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            return
                        try:
                            chunk = json.loads(payload)
                            delta = chunk["choices"][0]["delta"].get("content")
                        except Exception:
                            delta = None
                        if delta:
                            yield delta, m
                    return
            except Exception:
                continue
        yield ("Tessa konnte kein Modell erreichen.", "none")
