"""Encrypted store for external-integration credentials."""

import json

from sqlalchemy.orm import Session

from app.models import IntegrationCredential
from app.security import decrypt, encrypt

SWISSCHAT = "swisschat"


def save_credentials(db: Session, name: str, secret_data: dict, public: dict) -> None:
    row = db.get(IntegrationCredential, name)
    blob = encrypt(json.dumps(secret_data))
    if not row:
        row = IntegrationCredential(name=name, enabled=True,
                                    data_encrypted=blob, public=public)
        db.add(row)
    else:
        row.enabled = True
        row.data_encrypted = blob
        row.public = public
    db.commit()


def get_credentials(db: Session, name: str) -> dict | None:
    row = db.get(IntegrationCredential, name)
    if not row or not row.enabled or not row.data_encrypted:
        return None
    try:
        return json.loads(decrypt(row.data_encrypted))
    except Exception:
        return None


def get_public(db: Session, name: str) -> dict:
    row = db.get(IntegrationCredential, name)
    if not row:
        return {"configured": False}
    return {"configured": bool(row.data_encrypted), "enabled": row.enabled,
            **(row.public or {})}


def forget(db: Session, name: str) -> None:
    row = db.get(IntegrationCredential, name)
    if row:
        db.delete(row)
        db.commit()
