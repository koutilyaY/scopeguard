"""User management (organization admins only)."""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, require_any_role
from app.models import User
from app.models.enums import UserRole
from app.routers.auth import UserOut
from app.schemas.common import Page, PageParams
from app.security.passwords import hash_password, validate_password_policy
from app.security.sessions import destroy_all_sessions_for_user
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/users", tags=["users"])

admin_only = require_any_role({UserRole.organization_admin})


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole
    password: str | None = None  # None => generate a temporary password


class UserCreateResponse(BaseModel):
    user: UserOut
    temporary_password: str | None


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    active: bool | None = None


@router.get("", response_model=Page[UserOut])
def list_users(
    params: PageParams = Depends(),
    ctx: AuthContext = Depends(admin_only),
    db: Session = Depends(get_db),
) -> Page[UserOut]:
    stmt = select(User).where(User.organization_id == ctx.organization_id).order_by(User.email)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[UserOut.from_user(u) for u in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=UserCreateResponse, status_code=201)
def create_user(
    payload: UserCreate,
    ctx: AuthContext = Depends(admin_only),
    db: Session = Depends(get_db),
) -> UserCreateResponse:
    existing = db.execute(
        select(User).where(User.email == payload.email.lower())
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="A user with this email exists")

    temp_password: str | None = None
    if payload.password:
        problems = validate_password_policy(payload.password)
        if problems:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=" ".join(problems))
        password = payload.password
    else:
        temp_password = secrets.token_urlsafe(12) + "aA1"
        password = temp_password

    user = User(
        organization_id=ctx.organization_id,
        email=payload.email.lower(),
        full_name=payload.full_name,
        hashed_password=hash_password(password),
        role=payload.role,
        active=True,
        must_change_password=True,
    )
    db.add(user)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="user.created",
        entity_type="user",
        entity_id=user.id,
        after_state={"email": user.email, "role": user.role.value},
    )
    db.commit()
    return UserCreateResponse(user=UserOut.from_user(user), temporary_password=temp_password)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    ctx: AuthContext = Depends(admin_only),
    db: Session = Depends(get_db),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None or user.organization_id != ctx.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    if user.id == ctx.user.id and payload.active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    before = {"full_name": user.full_name, "role": user.role.value, "active": user.active}
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.active is not None:
        user.active = payload.active
        if not payload.active:
            destroy_all_sessions_for_user(db, user.id)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="user.updated",
        entity_type="user",
        entity_id=user.id,
        before_state=before,
        after_state={"full_name": user.full_name, "role": user.role.value, "active": user.active},
    )
    db.commit()
    return UserOut.from_user(user)
