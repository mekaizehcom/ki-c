from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import admin, auth, health, me

app = FastAPI(title="Tessa API", version="0.1.0")

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


@app.get("/api")
def root() -> dict:
    return {"service": "tessa-api", "version": "0.1.0", "env": settings.tessa_env}
