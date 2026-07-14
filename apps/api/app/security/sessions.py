"""Server-side session management.

The browser holds an opaque random token in an HttpOnly cookie. Only the SHA-256 of
that token is stored server-side, so a database leak does not expose usable sessions.
A per-session CSRF token is exposed in a readable cookie (double-submit pattern) and
must be echoed in the X-CSRF-Token header for mutating requests.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthSession, User


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, ip_address: str | None) -> tuple[str, str]:
    """Create a session; returns (session_token, csrf_token). Caller commits."""
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_hex(32)
    now = datetime.now(UTC)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=_hash_token(token),
            csrf_token=csrf,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.session_ttl_minutes),
            ip_address=ip_address,
        )
    )
    return token, csrf


def resolve_session(db: Session, token: str) -> tuple[AuthSession, User] | None:
    """Return the (session, user) pair for a valid, unexpired token."""
    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == _hash_token(token))
    ).first()
    if row is None:
        return None
    session, user = row
    if session.expires_at < datetime.now(UTC):
        db.delete(session)
        db.commit()
        return None
    if not user.active:
        return None
    return session, user


def destroy_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash_token(token)))


def destroy_all_sessions_for_user(db: Session, user_id) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
