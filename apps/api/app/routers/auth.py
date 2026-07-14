"""Authentication endpoints: login, logout, me, change-password."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.deps import AuthContext, get_auth_context
from app.models import User
from app.security.passwords import hash_password, validate_password_policy, verify_password
from app.security.rate_limit import check_rate_limit
from app.security.sessions import (
    create_session,
    destroy_all_sessions_for_user,
    destroy_session,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("scopeguard.auth")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: str
    must_change_password: bool

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            organization_id=str(user.organization_id),
            must_change_password=user.must_change_password,
        )


class LoginResponse(BaseModel):
    user: UserOut
    csrf_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    settings = get_settings()
    ip = _client_ip(request) or "unknown"

    if not check_rate_limit(f"login:{ip}", limit=20, window_seconds=60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")

    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()

    generic_error = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user is None or not user.active:
        raise generic_error

    now = datetime.now(UTC)
    if user.locked_until is not None and user.locked_until > now:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail="Account temporarily locked after repeated failed logins. Try again later.",
        )

    if not verify_password(user.hashed_password, payload.password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.login_max_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_login_attempts = 0
            record_audit_event(
                db,
                organization_id=user.organization_id,
                actor_user_id=None,
                action="auth.account_locked",
                entity_type="user",
                entity_id=user.id,
                ip_address=ip,
            )
        db.commit()
        raise generic_error

    user.failed_login_attempts = 0
    user.locked_until = None
    token, csrf = create_session(db, user, ip)
    record_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="auth.login",
        entity_type="user",
        entity_id=user.id,
        ip_address=ip,
    )
    db.commit()

    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
        path="/",
    )
    # CSRF cookie is intentionally readable by JS (double-submit pattern)
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_minutes * 60,
        path="/",
    )
    return LoginResponse(user=UserOut.from_user(user), csrf_token=csrf)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        destroy_session(db, token)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="auth.logout",
        entity_type="user",
        entity_id=ctx.user.id,
    )
    db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserOut)
def me(ctx: AuthContext = Depends(get_auth_context)) -> UserOut:
    return UserOut.from_user(ctx.user)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = db.get(User, ctx.user.id)
    assert user is not None
    if not verify_password(user.hashed_password, payload.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    problems = validate_password_policy(payload.new_password)
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=" ".join(problems))
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    destroy_all_sessions_for_user(db, user.id)
    record_audit_event(
        db,
        organization_id=user.organization_id,
        actor_user_id=user.id,
        action="auth.password_changed",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    return {"detail": "Password changed. Please log in again."}
