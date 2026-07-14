"""Customer requests: manual entry plus creation from uploaded EML/TXT/PDF/DOCX."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import CustomerRequest, Document, Project, WorkItem
from app.models.enums import AuthorizationStatus
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/customer-requests", tags=["customer-requests"])


class CustomerRequestIn(BaseModel):
    project_id: uuid.UUID | None = None
    subject: str
    sender: str | None = None
    recipients: str | None = None
    request_date: date | None = None
    body: str | None = None
    source_document_id: uuid.UUID | None = None
    linked_work_item_id: uuid.UUID | None = None
    customer_authorization_status: AuthorizationStatus = AuthorizationStatus.none


class CustomerRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID | None
    subject: str
    sender: str | None
    recipients: str | None
    request_date: date | None
    body: str | None
    source_document_id: uuid.UUID | None
    linked_work_item_id: uuid.UUID | None
    customer_authorization_status: AuthorizationStatus


@router.get("", response_model=Page[CustomerRequestOut])
def list_customer_requests(
    params: PageParams = Depends(),
    project_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[CustomerRequestOut]:
    stmt = (
        select(CustomerRequest)
        .where(CustomerRequest.organization_id == ctx.organization_id)
        .order_by(CustomerRequest.request_date.desc().nulls_last())
    )
    if project_id:
        stmt = stmt.where(CustomerRequest.project_id == project_id)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[CustomerRequestOut.model_validate(r) for r in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{request_id}", response_model=CustomerRequestOut)
def get_customer_request(
    request_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> CustomerRequestOut:
    request = get_org_object(db, CustomerRequest, request_id, ctx.organization_id)
    return CustomerRequestOut.model_validate(request)


@router.post("", response_model=CustomerRequestOut, status_code=201)
def create_customer_request(
    payload: CustomerRequestIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerRequestOut:
    if payload.project_id:
        get_org_object(db, Project, payload.project_id, ctx.organization_id)
    if payload.source_document_id:
        get_org_object(db, Document, payload.source_document_id, ctx.organization_id)
    if payload.linked_work_item_id:
        get_org_object(db, WorkItem, payload.linked_work_item_id, ctx.organization_id)
    request = CustomerRequest(organization_id=ctx.organization_id, **payload.model_dump())
    db.add(request)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="customer_request.created",
        entity_type="customer_request",
        entity_id=request.id,
        after_state={"subject": payload.subject},
    )
    db.commit()
    return CustomerRequestOut.model_validate(request)


@router.patch("/{request_id}", response_model=CustomerRequestOut)
def update_customer_request(
    request_id: uuid.UUID,
    payload: CustomerRequestIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerRequestOut:
    request = get_org_object(db, CustomerRequest, request_id, ctx.organization_id)
    before = {
        "subject": request.subject,
        "authorization": request.customer_authorization_status.value,
    }
    if payload.linked_work_item_id:
        get_org_object(db, WorkItem, payload.linked_work_item_id, ctx.organization_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(request, key, value)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="customer_request.updated",
        entity_type="customer_request",
        entity_id=request.id,
        before_state=before,
        after_state={
            "subject": request.subject,
            "authorization": request.customer_authorization_status.value,
        },
    )
    db.commit()
    return CustomerRequestOut.model_validate(request)
