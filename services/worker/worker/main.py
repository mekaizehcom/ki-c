"""Background worker: consumes the Redis ingestion queue."""

import json
import os
import time

import redis

from worker.pipeline import ingest, mark_failed

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
INGEST_QUEUE = "tessa:ingest"


def main() -> None:
    r = redis.from_url(REDIS_URL)
    print("[worker] started; waiting for ingest jobs", flush=True)
    while True:
        try:
            item = r.brpop(INGEST_QUEUE, timeout=15)
            r.set("tessa:worker:heartbeat", int(time.time()))
            if not item:
                continue
            job = json.loads(item[1])
            doc_id = job.get("document_id")
            try:
                n = ingest(job)
                print(f"[worker] ingested {doc_id}: {n} chunks", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[worker] ingest failed for {doc_id}: {exc}", flush=True)
                mark_failed(doc_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[worker] loop error: {exc}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
