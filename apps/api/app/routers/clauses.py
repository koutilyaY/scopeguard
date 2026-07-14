"""Contract clause review: list, edit, approve, reject, supersede.

Unverified clauses cannot drive high-confidence recommendations (enforced in the
review engine), so human verification here is a first-class workflow.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import (
    DECISION_ROLES,
    AuthContext,
    get_auth_context,
    get_org_object,
    require_any_role,
)
from app.models import ContractClause
from app.models.enums import ClauseType
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/clauses", tags=["clauses"])


class ClauseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    clause_type: ClauseType
    title: str
    source_text: str
    normalized_interpretation: str | None
    page_number: int | None
    section_reference: str | None
    effective_from: date | None
    effective_to: date | None
    confidence: float | None
    human_verified: bool
    rejected: bool
    superseded_by_clause_id: uuid.UUID | None


class ClauseUpdate(BaseModel):
    clause_type: ClauseType | None = None
    title: str | None = None
    normalized_interpretation: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    section_reference: str | None = None


class SupersedeRequest(BaseModel):
    superseded_by_clause_id: uuid.UUID


def _snapshot(clause: ContractClause) -> dict:
    return {
        "clause_type": clause.clause_type.value,
        "title": clause.title,
        "human_verified": clause.human_verified,
        "rejected": clause.rejected,
        "effective_from": str(clause.effective_from) if clause.effective_from else None,
        "effective_to": str(clause.effective_to) if clause.effective_to else None,
    }


@router.get("", response_model=Page[ClauseOut])
def list_clauses(
    params: PageParams = Depends(),
    contract_id: uuid.UUID | None = Query(None),
    clause_type: ClauseType | None = Query(None),
    verified: bool | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[ClauseOut]:
    stmt = (
        select(ContractClause)
        .where(ContractClause.organization_id == ctx.organization_id)
        .order_by(ContractClause.page_number.asc().nulls_last(), ContractClause.created_at)
    )
    if contract_id:
        stmt = stmt.where(ContractClause.contract_id == contract_id)
    if clause_type:
        stmt = stmt.where(ContractClause.clause_type == clause_type)
    if verified is not None:
        stmt = stmt.where(ContractClause.human_verified == verified)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[ClauseOut.model_validate(c) for c in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{clause_id}", response_model=ClauseOut)
def get_clause(
    clause_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> ClauseOut:
    clause = get_org_object(db, ContractClause, clause_id, ctx.organization_id)
    return ClauseOut.model_validate(clause)


@router.patch("/{clause_id}", response_model=ClauseOut)
def update_clause(
    clause_id: uuid.UUID,
    payload: ClauseUpdate,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ClauseOut:
    clause = get_org_object(db, ContractClause, clause_id, ctx.organization_id)
    before = _snapshot(clause)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(clause, key, value)
    # Any human edit invalidates prior verification until re-approved.
    clause.human_verified = False
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="clause.updated",
        entity_type="contract_clause",
        entity_id=clause.id,
        before_state=before,
        after_state=_snapshot(clause),
    )
    db.commit()
    return ClauseOut.model_validate(clause)


@router.post("/{clause_id}/approve", response_model=ClauseOut)
def approve_clause(
    clause_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ClauseOut:
    clause = get_org_object(db, ContractClause, clause_id, ctx.organization_id)
    before = _snapshot(clause)
    clause.human_verified = True
    clause.rejected = False
    clause.verified_by = ctx.user.id
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="clause.approved",
        entity_type="contract_clause",
        entity_id=clause.id,
        before_state=before,
        after_state=_snapshot(clause),
    )
    db.commit()
    return ClauseOut.model_validate(clause)


@router.post("/{clause_id}/reject", response_model=ClauseOut)
def reject_clause(
    clause_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ClauseOut:
    clause = get_org_object(db, ContractClause, clause_id, ctx.organization_id)
    before = _snapshot(clause)
    clause.rejected = True
    clause.human_verified = False
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="clause.rejected",
        entity_type="contract_clause",
        entity_id=clause.id,
        before_state=before,
        after_state=_snapshot(clause),
    )
    db.commit()
    return ClauseOut.model_validate(clause)


@router.post("/{clause_id}/supersede", response_model=ClauseOut)
def supersede_clause(
    clause_id: uuid.UUID,
    payload: SupersedeRequest,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ClauseOut:
    clause = get_org_object(db, ContractClause, clause_id, ctx.organization_id)
    replacement = get_org_object(
        db, ContractClause, payload.superseded_by_clause_id, ctx.organization_id
    )
    if replacement.id == clause.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="A clause cannot supersede itself")
    before = _snapshot(clause)
    clause.superseded_by_clause_id = replacement.id
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="clause.superseded",
        entity_type="contract_clause",
        entity_id=clause.id,
        before_state=before,
        after_state={**_snapshot(clause), "superseded_by": str(replacement.id)},
    )
    db.commit()
    return ClauseOut.model_validate(clause)
