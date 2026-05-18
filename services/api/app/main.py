from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import SessionLocal
from app.routers import admin, auth, chat, health, me
from app.workspace import load_workspace, sync_to_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        sync_to_db(db, load_workspace(settings.default_workspace))
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] workspace sync skipped: {exc}", flush=True)
    finally:
        db.close()
    yield

app = FastAPI(title="Tessa API", version="0.2.0", lifespan=lifespan)

_origins = [
    settings.public_base_url,
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(admin.router)
app.include_router(chat.router)
app.include_router(chat.ws_router)


@app.get("/api")
def root() -> dict:
    return {"service": "tessa-api", "version": "0.1.0", "env": settings.tessa_env}
