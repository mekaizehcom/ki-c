import json

import redis

from app.config import settings

INGEST_QUEUE = "tessa:ingest"

_pool = redis.from_url(settings.redis_url)


def enqueue_ingest(job: dict) -> None:
    _pool.lpush(INGEST_QUEUE, json.dumps(job))


def queue_depth() -> int:
    return int(_pool.llen(INGEST_QUEUE))
