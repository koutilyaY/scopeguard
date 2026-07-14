"""Audit log read access."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, require_role
from app.models import AuditEvent
from app.models.enums import UserRole
from app.schemas.common import Page, PageParams
from app.services.pagination import paginate

router = APIRouter(prefix="/audit-events", tags=["audit-events"])


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: uuid.UUID | None
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    ip_address: str | None
    request_id: str | None
    created_at: datetime


@router.get("", response_model=Page[AuditEventOut])
def list_audit_events(
    params: PageParams = Depends(),
    entity_type: str | None = Query(None),
    entity_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None),
    ctx: AuthContext = Depends(require_role(UserRole.reviewer)),
    db: Session = Depends(get_db),
) -> Page[AuditEventOut]:
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == ctx.organization_id)
        .order_by(AuditEvent.created_at.desc())
    )
    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[AuditEventOut.model_validate(e) for e in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
