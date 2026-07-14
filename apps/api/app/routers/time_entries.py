"""Time entry read endpoints (creation happens through imports)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth_context, get_org_object
from app.models import TimeEntry
from app.models.enums import BillableStatus
from app.schemas.common import Page, PageParams
from app.services.pagination import paginate

router = APIRouter(prefix="/time-entries", tags=["time-entries"])


class TimeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    work_item_id: uuid.UUID | None
    external_id: str | None
    employee_name: str
    employee_role: str | None
    work_date: date
    minutes: int
    billable_status: BillableStatus
    description: str | None
    source: str


@router.get("", response_model=Page[TimeEntryOut])
def list_time_entries(
    params: PageParams = Depends(),
    project_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[TimeEntryOut]:
    stmt = (
        select(TimeEntry)
        .where(TimeEntry.organization_id == ctx.organization_id)
        .order_by(TimeEntry.work_date.desc())
    )
    if project_id:
        stmt = stmt.where(TimeEntry.project_id == project_id)
    if date_from:
        stmt = stmt.where(TimeEntry.work_date >= date_from)
    if date_to:
        stmt = stmt.where(TimeEntry.work_date <= date_to)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[TimeEntryOut.model_validate(t) for t in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{time_entry_id}", response_model=TimeEntryOut)
def get_time_entry(
    time_entry_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> TimeEntryOut:
    entry = get_org_object(db, TimeEntry, time_entry_id, ctx.organization_id)
    return TimeEntryOut.model_validate(entry)
