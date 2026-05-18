import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet

from app.config import settings

_ph = PasswordHasher()


# ---------- passwords ----------
def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# ---------- symmetric encryption (provider keys, TOTP secrets) ----------
def _fernet() -> Fernet:
    key = settings.fernet_key.strip()
    if not key:
        # Deterministic fallback derived from secret_key (dev only).
        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


# ---------- TOTP (RFC-6238) ----------
def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, username: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=f"Tessa ({settings.tessa_domain})"
    )


def verify_totp(secret: str, code: str) -> bool:
    if not code or not secret:
        return False
    return pyotp.TOTP(secret).verify(code.strip(), valid_window=1)


# ---------- session tokens ----------
def generate_session_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def session_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.session_ttl_minutes)
