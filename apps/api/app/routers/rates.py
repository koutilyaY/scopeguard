"""Rate rule CRUD. Rates are integer minor units (e.g. 17500 = $175.00/hour)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Contract, RateRule
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/rates", tags=["rates"])


class RateIn(BaseModel):
    contract_id: uuid.UUID
    role_name: str
    service_category: str | None = None
    hourly_rate_minor: int = Field(ge=0)
    currency: str = "USD"
    effective_from: date | None = None
    effective_to: date | None = None
    source_clause_id: uuid.UUID | None = None


class RateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    role_name: str
    service_category: str | None
    hourly_rate_minor: int
    currency: str
    effective_from: date | None
    effective_to: date | None
    source_clause_id: uuid.UUID | None
    human_verified: bool


@router.get("", response_model=Page[RateOut])
def list_rates(
    params: PageParams = Depends(),
    contract_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[RateOut]:
    stmt = (
        select(RateRule)
        .where(RateRule.organization_id == ctx.organization_id)
        .order_by(RateRule.role_name, RateRule.effective_from.asc().nulls_first())
    )
    if contract_id:
        stmt = stmt.where(RateRule.contract_id == contract_id)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[RateOut.model_validate(r) for r in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("", response_model=RateOut, status_code=201)
def create_rate(
    payload: RateIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> RateOut:
    get_org_object(db, Contract, payload.contract_id, ctx.organization_id)
    rate = RateRule(organization_id=ctx.organization_id, **payload.model_dump())
    db.add(rate)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="rate.created",
        entity_type="rate_rule",
        entity_id=rate.id,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return RateOut.model_validate(rate)


@router.put("/{rate_id}", response_model=RateOut)
def update_rate(
    rate_id: uuid.UUID,
    payload: RateIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> RateOut:
    rate = get_org_object(db, RateRule, rate_id, ctx.organization_id)
    before = {"role_name": rate.role_name, "hourly_rate_minor": rate.hourly_rate_minor}
    for key, value in payload.model_dump().items():
        setattr(rate, key, value)
    rate.human_verified = False  # edits require re-verification
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="rate.updated",
        entity_type="rate_rule",
        entity_id=rate.id,
        before_state=before,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return RateOut.model_validate(rate)


@router.post("/{rate_id}/verify", response_model=RateOut)
def verify_rate(
    rate_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> RateOut:
    rate = get_org_object(db, RateRule, rate_id, ctx.organization_id)
    rate.human_verified = True
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="rate.verified",
        entity_type="rate_rule",
        entity_id=rate.id,
    )
    db.commit()
    return RateOut.model_validate(rate)


@router.delete("/{rate_id}")
def delete_rate(
    rate_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    rate = get_org_object(db, RateRule, rate_id, ctx.organization_id)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="rate.deleted",
        entity_type="rate_rule",
        entity_id=rate.id,
        before_state={"role_name": rate.role_name, "hourly_rate_minor": rate.hourly_rate_minor},
    )
    db.delete(rate)
    db.commit()
    return {"detail": "Rate deleted"}
