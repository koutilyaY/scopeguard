"""Work item read endpoints (creation happens through imports)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth_context, get_org_object
from app.models import WorkItem
from app.models.enums import WorkItemStatus
from app.schemas.common import Page, PageParams
from app.services.pagination import paginate

router = APIRouter(prefix="/work-items", tags=["work-items"])


class WorkItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    external_system: str
    external_id: str
    title: str
    description: str | None
    status: WorkItemStatus
    work_type: str | None
    assignee: str | None
    created_at_external: datetime | None
    completed_at_external: datetime | None
    source_url: str | None


@router.get("", response_model=Page[WorkItemOut])
def list_work_items(
    params: PageParams = Depends(),
    project_id: uuid.UUID | None = Query(None),
    status_filter: WorkItemStatus | None = Query(None, alias="status"),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[WorkItemOut]:
    stmt = (
        select(WorkItem)
        .where(WorkItem.organization_id == ctx.organization_id)
        .order_by(WorkItem.external_id)
    )
    if project_id:
        stmt = stmt.where(WorkItem.project_id == project_id)
    if status_filter:
        stmt = stmt.where(WorkItem.status == status_filter)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[WorkItemOut.model_validate(w) for w in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{work_item_id}", response_model=WorkItemOut)
def get_work_item(
    work_item_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> WorkItemOut:
    item = get_org_object(db, WorkItem, work_item_id, ctx.organization_id)
    return WorkItemOut.model_validate(item)
