import io
import uuid
from datetime import datetime, timedelta, timezone

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import audit
from app.config import settings
from app.db import get_db
from app.deps import SESSION_COOKIE, get_current_user
from app.models import SessionToken, TotpSecret, User
from app.schemas import (
    LoginRequest,
    LoginStep1Response,
    SessionResponse,
    TotpVerifyRequest,
    UserOut,
)
from app.security import (
    decrypt,
    encrypt,
    generate_session_token,
    hash_token,
    new_totp_secret,
    session_expiry,
    totp_provisioning_uri,
    verify_password,
    verify_totp,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="tessa-totp-challenge")
CHALLENGE_MAX_AGE = 300  # seconds


def _make_challenge(user_id: str, purpose: str) -> str:
    return _serializer.dumps({"uid": user_id, "purpose": purpose})


def _read_challenge(token: str) -> dict:
    try:
        return _serializer.loads(token, max_age=CHALLENGE_MAX_AGE)
    except SignatureExpired:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Challenge expired")
    except BadSignature:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid challenge")


@router.post("/login", response_model=LoginStep1Response)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> LoginStep1Response:
    user = db.scalar(select(User).where(User.username == body.username))
    generic_err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    if not user:
        raise generic_err
    if user.status == "disabled":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    now = datetime.now(timezone.utc)
    if user.locked_until and user.locked_until > now:
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked")

    if not verify_password(body.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_count = 0
            user.status = "locked" if user.status == "active" else user.status
            audit(db, action="login.locked", status="denied", risk_level="medium",
                  user_id=user.id, details={"username": user.username})
        db.commit()
        audit(db, action="login.failed", status="denied", user_id=user.id,
              details={"username": user.username})
        raise generic_err

    user.failed_login_count = 0
    if user.status == "locked":
        user.status = "active"
    user.locked_until = None
    db.commit()

    totp = db.get(TotpSecret, user.id)
    if not totp or not totp.confirmed:
        # First-time enrollment required.
        secret = new_totp_secret()
        if totp:
            totp.secret = encrypt(secret)
            totp.confirmed = False
        else:
            db.add(TotpSecret(user_id=user.id, secret=encrypt(secret), confirmed=False))
        db.commit()
        uri = totp_provisioning_uri(secret, user.username)
        audit(db, action="login.totp_enroll_start", user_id=user.id)
        return LoginStep1Response(
            status="totp_enroll",
            challenge_id=_make_challenge(str(user.id), "enroll"),
            enroll_uri=uri,
            enroll_secret=secret,
        )

    audit(db, action="login.password_ok", user_id=user.id)
    return LoginStep1Response(
        status="totp_required",
        challenge_id=_make_challenge(str(user.id), "login"),
    )


@router.get("/totp/qr")
def totp_qr(challenge_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    data = _read_challenge(challenge_id)
    if data["purpose"] != "enroll":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not an enrollment challenge")
    user = db.get(User, uuid.UUID(data["uid"]))
    totp = db.get(TotpSecret, user.id) if user else None
    if not user or not totp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No enrollment in progress")
    uri = totp_provisioning_uri(decrypt(totp.secret), user.username)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.post("/totp/verify", response_model=SessionResponse)
def totp_verify(
    body: TotpVerifyRequest, response: Response, db: Session = Depends(get_db)
) -> SessionResponse:
    data = _read_challenge(body.challenge_id)
    user = db.get(User, uuid.UUID(data["uid"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid challenge")
    totp = db.get(TotpSecret, user.id)
    if not totp:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No TOTP enrolled")

    if not verify_totp(decrypt(totp.secret), body.code):
        audit(db, action="login.totp_failed", status="denied", risk_level="medium",
              user_id=user.id)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid TOTP code")

    if data["purpose"] == "enroll":
        totp.confirmed = True
        user.totp_enabled = True
        db.commit()
        audit(db, action="login.totp_enrolled", user_id=user.id)

    raw = generate_session_token()
    db.add(
        SessionToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            channel="web",
            expires_at=session_expiry(),
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
        path="/",
    )
    audit(db, action="login.success", user_id=user.id)
    return SessionResponse(status="ok", user=UserOut.model_validate(user))


@router.post("/logout")
def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Revoke all active sessions for the user (simple + safe for v1).
    for st in db.scalars(
        select(SessionToken).where(
            SessionToken.user_id == user.id, SessionToken.revoked == False  # noqa: E712
        )
    ):
        st.revoked = True
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    audit(db, action="logout", user_id=user.id)
    return {"detail": "logged out"}
