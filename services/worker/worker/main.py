"""Background worker.

Phase 1: heartbeat loop + Redis connectivity check.
Phase 3 fills in the ingestion / embedding pipeline (consumes a Redis queue).
"""

import os
import time

import redis

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


def main() -> None:
    r = redis.from_url(REDIS_URL)
    print("[worker] started", flush=True)
    while True:
        try:
            r.ping()
            r.set("tessa:worker:heartbeat", int(time.time()))
        except Exception as exc:  # noqa: BLE001
            print(f"[worker] redis error: {exc}", flush=True)
        time.sleep(15)


if __name__ == "__main__":
    main()
