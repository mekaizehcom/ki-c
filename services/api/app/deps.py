from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SessionToken, User
from app.security import hash_token

SESSION_COOKIE = "tessa_session"

ROLE_RANK = {
    "restricted": 10,
    "user": 20,
    "developer": 30,
    "admin": 40,
    "superadmin": 50,
}


def get_current_user(
    tessa_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not tessa_session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    th = hash_token(tessa_session)
    st = db.scalar(select(SessionToken).where(SessionToken.token_hash == th))
    if not st or st.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    if st.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    user = db.get(User, st.user_id)
    if not user or user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User inactive")
    st.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    return user


def require_role(min_role: str):
    threshold = ROLE_RANK.get(min_role, 999)

    def _guard(user: User = Depends(get_current_user)) -> User:
        if ROLE_RANK.get(user.role, 0) < threshold:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user

    return _guard
