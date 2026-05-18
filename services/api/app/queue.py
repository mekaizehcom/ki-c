import json

import redis

from app.config import settings

INGEST_QUEUE = "tessa:ingest"

_pool = redis.from_url(settings.redis_url)


def enqueue_ingest(job: dict) -> None:
    _pool.lpush(INGEST_QUEUE, json.dumps(job))


def queue_depth() -> int:
    return int(_pool.llen(INGEST_QUEUE))


def seen_once(key: str, ttl: int = 3600) -> bool:
    """True if `key` was already seen (idempotency); records it otherwise."""
    return not bool(_pool.set(key, "1", nx=True, ex=ttl))
