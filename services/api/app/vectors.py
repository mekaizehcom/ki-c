"""Embeddings + Qdrant retrieval (API side).

The mock embedding is deterministic and MUST stay byte-identical to the
worker's copy (services/worker/worker/pipeline.py:embed_text) so that
documents ingested by the worker are retrievable by queries embedded here.
"""

from __future__ import annotations

import math
import re

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.config import settings

# Role -> visibility levels the user may retrieve (§22.2).
VISIBILITY_BY_ROLE = {
    "restricted": ["workspace", "global"],
    "user": ["workspace", "team", "global"],
    "developer": ["workspace", "team", "global"],
    "admin": ["workspace", "team", "global", "admin"],
    "superadmin": ["workspace", "team", "global", "admin"],
}


def collection_for(workspace_slug: str) -> str:
    return "tessa_" + re.sub(r"[^a-z0-9_]", "_", workspace_slug.lower())


def embed_text(text: str, dim: int) -> list[float]:
    """Deterministic hashing embedding (keep identical to worker)."""
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = 0
        for ch in tok:
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_query(text: str) -> list[float]:
    dim = settings.embedding_dim
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        try:
            r = httpx.post(
                f"{settings.litellm_base_url}/embeddings",
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
                json={"model": settings.embedding_model, "input": text},
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["data"][0]["embedding"]
        except Exception:
            pass
    return embed_text(text, dim)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def hybrid_rerank(query: str, hits: list[dict], top_k: int = 5) -> list[dict]:
    """Blend vector score with lexical overlap (simple hybrid retrieval)."""
    q = _tokens(query)
    if not q:
        return hits[:top_k]
    for h in hits:
        overlap = len(q & _tokens(h.get("text", ""))) / len(q)
        h["score"] = round(0.6 * float(h.get("score", 0.0)) + 0.4 * overlap, 6)
    return sorted(hits, key=lambda x: x["score"], reverse=True)[:top_k]


def _client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, timeout=30)


def allowed_visibilities(role: str) -> list[str]:
    return VISIBILITY_BY_ROLE.get(role, ["workspace", "global"])


def search(
    collection: str,
    query_vec: list[float],
    *,
    role: str,
    user_id: str,
    workspace_id: str | None,
    top_k: int = 5,
) -> list[dict]:
    """Visibility-filtered semantic search. Returns chunk payloads."""
    client = _client()
    try:
        client.get_collection(collection)
    except Exception:
        return []

    vis = allowed_visibilities(role)
    # user_private docs are only visible to their owner.
    should = [
        qm.FieldCondition(key="visibility", match=qm.MatchAny(any=vis)),
        qm.Filter(
            must=[
                qm.FieldCondition(key="visibility", match=qm.MatchValue(value="user_private")),
                qm.FieldCondition(key="user_id", match=qm.MatchValue(value=user_id)),
            ]
        ),
    ]
    flt = qm.Filter(should=should)
    try:
        hits = client.query_points(
            collection_name=collection,
            query=query_vec,
            limit=top_k,
            query_filter=flt,
            with_payload=True,
        ).points
    except Exception:
        return []

    out = []
    for h in hits:
        p = h.payload or {}
        out.append(
            {
                "text": p.get("text", ""),
                "document_id": p.get("document_id"),
                "filename": p.get("filename", ""),
                "seq": p.get("seq"),
                "score": h.score,
            }
        )
    return out
