import hashlib
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Document, Workspace
from app.queue import enqueue_ingest

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = "/data/uploads"
ALLOWED_EXT = {".md", ".txt", ".pdf", ".docx", ".html", ".htm", ".csv", ".json", ".log"}
VALID_VISIBILITY = {"user_private", "team", "workspace", "admin", "global"}


@router.post("/upload", status_code=201)
async def upload(
    file: UploadFile = File(...),
    visibility: str = Form("workspace"),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if visibility not in VALID_VISIBILITY:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid visibility")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported type {ext}")

    data = await file.read()
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    checksum = hashlib.sha256(data).hexdigest()[:32]

    ws = db.scalar(select(Workspace).where(Workspace.slug == settings.default_workspace))
    doc = Document(
        workspace_id=ws.id if ws else None,
        uploaded_by=user.id,
        filename=file.filename or "upload",
        content_type=file.content_type or "",
        size_bytes=len(data),
        visibility=visibility,
        status="uploaded",
        checksum=checksum,
    )
    db.add(doc)
    db.commit()

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_DIR, f"{doc.id}{ext}")
    with open(path, "wb") as fh:
        fh.write(data)

    enqueue_ingest(
        {
            "document_id": str(doc.id),
            "path": path,
            "ext": ext,
            "workspace_id": str(ws.id) if ws else None,
            "workspace_slug": settings.default_workspace,
            "user_id": str(user.id),
            "visibility": visibility,
            "filename": doc.filename,
            "checksum": checksum,
        }
    )
    audit(db, action="document.upload", user_id=user.id,
          details={"document": str(doc.id), "filename": doc.filename})
    return {"id": str(doc.id), "status": "queued", "filename": doc.filename}


@router.get("")
def list_documents(
    user=Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    rows = db.scalars(select(Document).order_by(Document.created_at.desc()).limit(100))
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "status": d.status,
            "visibility": d.visibility,
            "size_bytes": d.size_bytes,
            "created_at": d.created_at.isoformat(),
        }
        for d in rows
        if d.visibility != "user_private" or d.uploaded_by == user.id
    ]


@router.post("/{doc_id}/vectorize")
def revectorize(
    doc_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    doc = db.get(Document, uuid.UUID(doc_id))
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    ext = os.path.splitext(doc.filename)[1].lower()
    path = os.path.join(UPLOAD_DIR, f"{doc.id}{ext}")
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_409_CONFLICT, "Source file missing")
    doc.status = "uploaded"
    db.commit()
    enqueue_ingest(
        {
            "document_id": str(doc.id),
            "path": path,
            "ext": ext,
            "workspace_id": str(doc.workspace_id) if doc.workspace_id else None,
            "workspace_slug": settings.default_workspace,
            "user_id": str(doc.uploaded_by) if doc.uploaded_by else "",
            "visibility": doc.visibility,
            "filename": doc.filename,
            "checksum": doc.checksum,
        }
    )
    audit(db, action="document.revectorize", user_id=user.id,
          details={"document": str(doc.id)})
    return {"id": str(doc.id), "status": "queued"}
