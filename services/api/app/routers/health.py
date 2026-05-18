import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Conversation, Document, User

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "tessa-api"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "db": "ok"}


@router.get("/health/metrics")
def metrics(db: Session = Depends(get_db)) -> dict:
    from app.queue import _pool, queue_depth

    worker_ok = None
    try:
        hb = _pool.get("tessa:worker:heartbeat")
        worker_ok = bool(hb) and (time.time() - int(hb)) < 60
    except Exception:
        worker_ok = None
    return {
        "status": "ok",
        "ingest_queue": queue_depth(),
        "worker_alive": worker_ok,
        "users": db.scalar(func.count(User.id)),
        "conversations": db.scalar(func.count(Conversation.id)),
        "documents": db.scalar(func.count(Document.id)),
    }
