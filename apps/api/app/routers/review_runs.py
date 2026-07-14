"""Review run creation (idempotent per project+period while active) and status."""

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import DECISION_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Project, ReviewRun
from app.models.enums import ReviewRunStatus
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/review-runs", tags=["review-runs"])

ACTIVE_STATUSES = {ReviewRunStatus.pending, ReviewRunStatus.running}


class ReviewRunIn(BaseModel):
    project_id: uuid.UUID
    billing_period_start: date
    billing_period_end: date


class ReviewRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    billing_period_start: date
    billing_period_end: date
    status: ReviewRunStatus
    initiated_by: uuid.UUID | None
    model_name: str | None
    prompt_version: str | None
    started_at: datetime | None
    completed_at: datetime | None
    failure_reason: str | None
    stats: dict[str, Any] | None
    created_at: datetime


@router.get("", response_model=Page[ReviewRunOut])
def list_review_runs(
    params: PageParams = Depends(),
    project_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[ReviewRunOut]:
    stmt = (
        select(ReviewRun)
        .where(ReviewRun.organization_id == ctx.organization_id)
        .order_by(ReviewRun.created_at.desc())
    )
    if project_id:
        stmt = stmt.where(ReviewRun.project_id == project_id)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[ReviewRunOut.model_validate(r) for r in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{run_id}", response_model=ReviewRunOut)
def get_review_run(
    run_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> ReviewRunOut:
    run = get_org_object(db, ReviewRun, run_id, ctx.organization_id)
    return ReviewRunOut.model_validate(run)


@router.post("", response_model=ReviewRunOut, status_code=201)
def create_review_run(
    payload: ReviewRunIn,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ReviewRunOut:
    project = get_org_object(db, Project, payload.project_id, ctx.organization_id)
    if payload.billing_period_end < payload.billing_period_start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Billing period end precedes start")
    # Idempotency: return the existing active run for the same project+period.
    existing = db.execute(
        select(ReviewRun).where(
            ReviewRun.organization_id == ctx.organization_id,
            ReviewRun.project_id == project.id,
            ReviewRun.billing_period_start == payload.billing_period_start,
            ReviewRun.billing_period_end == payload.billing_period_end,
            ReviewRun.status.in_(ACTIVE_STATUSES),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ReviewRunOut.model_validate(existing)

    run = ReviewRun(
        organization_id=ctx.organization_id,
        project_id=project.id,
        billing_period_start=payload.billing_period_start,
        billing_period_end=payload.billing_period_end,
        status=ReviewRunStatus.pending,
        initiated_by=ctx.user.id,
    )
    db.add(run)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="review_run.created",
        entity_type="review_run",
        entity_id=run.id,
        after_state={
            "project_id": str(project.id),
            "period": f"{payload.billing_period_start}..{payload.billing_period_end}",
        },
    )
    db.commit()

    from app.worker import execute_review_run_task

    execute_review_run_task.delay(str(run.id))
    return ReviewRunOut.model_validate(run)
