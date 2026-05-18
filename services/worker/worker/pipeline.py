"""Ingestion pipeline: extract -> chunk -> embed -> Qdrant + Postgres.

embed_text MUST stay byte-identical to services/api/app/vectors.py so the
API can retrieve what the worker stored.
"""

from __future__ import annotations

import json
import math
import os
import re
import uuid

import psycopg
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

PG_DSN = (
    f"postgresql://{os.environ.get('POSTGRES_USER','tessa')}:"
    f"{os.environ.get('POSTGRES_PASSWORD','tessa')}@"
    f"{os.environ.get('POSTGRES_HOST','postgres')}:"
    f"{os.environ.get('POSTGRES_PORT','5432')}/"
    f"{os.environ.get('POSTGRES_DB','tessa')}"
)
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
EMBED_DIM = int(os.environ.get("EMBEDDING_DIM", "1536"))
CHUNK_WORDS = 600       # ~800 tokens
OVERLAP_WORDS = 90      # ~120 tokens


def collection_for(slug: str) -> str:
    return "tessa_" + re.sub(r"[^a-z0-9_]", "_", slug.lower())


def embed_text(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = 0
        for ch in tok:
            h = (h * 131 + ord(ch)) & 0xFFFFFFFF
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def extract_text(path: str, ext: str) -> str:
    if ext in (".md", ".txt", ".log", ".csv", ".json"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    if ext in (".html", ".htm"):
        from bs4 import BeautifulSoup

        with open(path, encoding="utf-8", errors="replace") as fh:
            return BeautifulSoup(fh.read(), "lxml").get_text(" ", strip=True)
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if ext == ".docx":
        import docx

        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    return ""


def chunk(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks, i = [], 0
    step = max(1, CHUNK_WORDS - OVERLAP_WORDS)
    while i < len(words):
        chunks.append(" ".join(words[i : i + CHUNK_WORDS]))
        i += step
    return chunks


def _ensure_collection(client: QdrantClient, name: str) -> None:
    try:
        client.get_collection(name)
    except Exception:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=EMBED_DIM, distance=qm.Distance.COSINE),
        )


def ingest(job: dict) -> int:
    doc_id = job["document_id"]
    text = extract_text(job["path"], job["ext"])
    pieces = chunk(text)
    client = QdrantClient(url=QDRANT_URL, timeout=30)
    coll = collection_for(job.get("workspace_slug", "company-default"))
    _ensure_collection(client, coll)

    points, rows = [], []
    for seq, piece in enumerate(pieces):
        cid = str(uuid.uuid4())
        payload = {
            "document_id": doc_id,
            "filename": job.get("filename", ""),
            "seq": seq,
            "text": piece,
            "visibility": job.get("visibility", "workspace"),
            "user_id": job.get("user_id", ""),
            "workspace_id": job.get("workspace_id"),
            "checksum": job.get("checksum", ""),
        }
        points.append(qm.PointStruct(id=cid, vector=embed_text(piece, EMBED_DIM),
                                     payload=payload))
        rows.append((cid, doc_id, seq, piece))

    # Idempotent re-ingest: drop any prior chunks/vectors for this document.
    try:
        client.delete(
            collection_name=coll,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[
                    qm.FieldCondition(key="document_id",
                                      match=qm.MatchValue(value=doc_id))
                ])
            ),
        )
    except Exception:
        pass

    if points:
        client.upsert(collection_name=coll, points=points)

    with psycopg.connect(PG_DSN, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM document_chunks WHERE document_id=%s", (doc_id,))
            cur.execute(
                "DELETE FROM vector_sources WHERE source_type='document' "
                "AND source_id=%s",
                (doc_id,),
            )
            for cid, did, seq, piece in rows:
                cur.execute(
                    "INSERT INTO document_chunks (id, document_id, seq, text, "
                    "vector_id, meta) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                    (uuid.uuid4(), did, seq, piece, cid, json.dumps({})),
                )
            cur.execute(
                "INSERT INTO vector_sources (id, source_type, source_id, "
                "workspace_id, user_id, visibility, collection, tags, "
                "checksum, created_at) "
                "VALUES (%s,'document',%s,%s,%s,%s,%s,%s::jsonb,%s,now())",
                (
                    uuid.uuid4(), doc_id,
                    job.get("workspace_id"),
                    job.get("user_id") or None,
                    job.get("visibility", "workspace"),
                    coll, json.dumps([]), job.get("checksum", ""),
                ),
            )
            cur.execute(
                "UPDATE documents SET status='ingested', updated_at=now() "
                "WHERE id=%s",
                (doc_id,),
            )
    return len(points)


def mark_failed(doc_id: str) -> None:
    try:
        with psycopg.connect(PG_DSN, autocommit=True) as conn:
            conn.execute("UPDATE documents SET status='failed' WHERE id=%s", (doc_id,))
    except Exception:
        pass
