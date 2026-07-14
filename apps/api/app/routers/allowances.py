"""Allowance CRUD (support-hour pools etc.). Quantities are stored in minutes/units."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Allowance, Contract
from app.models.enums import AllowanceRecurrence, AllowanceType
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/allowances", tags=["allowances"])


class AllowanceIn(BaseModel):
    contract_id: uuid.UUID
    allowance_type: AllowanceType
    included_quantity: int = Field(ge=0, description="minutes (unit=minutes) or units")
    unit: str = "minutes"
    recurrence: AllowanceRecurrence
    effective_from: date | None = None
    effective_to: date | None = None
    source_clause_id: uuid.UUID | None = None


class AllowanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    allowance_type: AllowanceType
    included_quantity: int
    unit: str
    recurrence: AllowanceRecurrence
    effective_from: date | None
    effective_to: date | None
    source_clause_id: uuid.UUID | None


@router.get("", response_model=Page[AllowanceOut])
def list_allowances(
    params: PageParams = Depends(),
    contract_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[AllowanceOut]:
    stmt = (
        select(Allowance)
        .where(Allowance.organization_id == ctx.organization_id)
        .order_by(Allowance.created_at)
    )
    if contract_id:
        stmt = stmt.where(Allowance.contract_id == contract_id)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[AllowanceOut.model_validate(a) for a in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=AllowanceOut, status_code=201)
def create_allowance(
    payload: AllowanceIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AllowanceOut:
    get_org_object(db, Contract, payload.contract_id, ctx.organization_id)
    allowance = Allowance(organization_id=ctx.organization_id, **payload.model_dump())
    db.add(allowance)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="allowance.created",
        entity_type="allowance",
        entity_id=allowance.id,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return AllowanceOut.model_validate(allowance)


@router.put("/{allowance_id}", response_model=AllowanceOut)
def update_allowance(
    allowance_id: uuid.UUID,
    payload: AllowanceIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> AllowanceOut:
    allowance = get_org_object(db, Allowance, allowance_id, ctx.organization_id)
    before = {"included_quantity": allowance.included_quantity, "unit": allowance.unit}
    for key, value in payload.model_dump().items():
        setattr(allowance, key, value)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="allowance.updated",
        entity_type="allowance",
        entity_id=allowance.id,
        before_state=before,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return AllowanceOut.model_validate(allowance)


@router.delete("/{allowance_id}")
def delete_allowance(
    allowance_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    allowance = get_org_object(db, Allowance, allowance_id, ctx.organization_id)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="allowance.deleted",
        entity_type="allowance",
        entity_id=allowance.id,
        before_state={"included_quantity": allowance.included_quantity},
    )
    db.delete(allowance)
    db.commit()
    return {"detail": "Allowance deleted"}
