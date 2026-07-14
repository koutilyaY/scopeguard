"""Invoices: manual entry, lines, listing. Import happens via the imports router.

ScopeGuard never creates customer-facing invoices automatically; these records
represent invoices that already exist in the firm's accounting system.
"""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Invoice, InvoiceLine, Project
from app.models.enums import InvoiceStatus
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/invoices", tags=["invoices"])


class InvoiceLineIn(BaseModel):
    description: str
    service_category: str | None = None
    quantity: Decimal = Field(default=Decimal(1), ge=0)
    unit_price_minor: int = 0
    amount_minor: int = 0
    linked_work_item_id: uuid.UUID | None = None
    linked_time_entry_id: uuid.UUID | None = None


class InvoiceIn(BaseModel):
    project_id: uuid.UUID
    invoice_number: str
    billing_period_start: date | None = None
    billing_period_end: date | None = None
    issue_date: date | None = None
    currency: str = "USD"
    status: InvoiceStatus = InvoiceStatus.draft
    tax_minor: int = 0
    external_reference: str | None = None
    lines: list[InvoiceLineIn] = []


class InvoiceLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    description: str
    service_category: str | None
    quantity: Decimal
    unit_price_minor: int
    amount_minor: int
    linked_work_item_id: uuid.UUID | None
    linked_time_entry_id: uuid.UUID | None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    invoice_number: str
    billing_period_start: date | None
    billing_period_end: date | None
    issue_date: date | None
    currency: str
    status: InvoiceStatus
    subtotal_minor: int
    tax_minor: int
    total_minor: int
    external_reference: str | None
    lines: list[InvoiceLineOut] = []


@router.get("", response_model=Page[InvoiceOut])
def list_invoices(
    params: PageParams = Depends(),
    project_id: uuid.UUID | None = Query(None),
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[InvoiceOut]:
    stmt = (
        select(Invoice)
        .where(Invoice.organization_id == ctx.organization_id)
        .order_by(Invoice.issue_date.desc().nulls_last())
    )
    if project_id:
        stmt = stmt.where(Invoice.project_id == project_id)
    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[InvoiceOut.model_validate(i) for i in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> InvoiceOut:
    invoice = get_org_object(db, Invoice, invoice_id, ctx.organization_id)
    return InvoiceOut.model_validate(invoice)


@router.post("", response_model=InvoiceOut, status_code=201)
def create_invoice(
    payload: InvoiceIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> InvoiceOut:
    get_org_object(db, Project, payload.project_id, ctx.organization_id)

    # Deterministic totals: subtotal = sum(line amounts); total = subtotal + tax.
    subtotal = sum(line.amount_minor for line in payload.lines)
    invoice = Invoice(
        organization_id=ctx.organization_id,
        project_id=payload.project_id,
        invoice_number=payload.invoice_number,
        billing_period_start=payload.billing_period_start,
        billing_period_end=payload.billing_period_end,
        issue_date=payload.issue_date,
        currency=payload.currency,
        status=payload.status,
        subtotal_minor=subtotal,
        tax_minor=payload.tax_minor,
        total_minor=subtotal + payload.tax_minor,
        external_reference=payload.external_reference,
    )
    db.add(invoice)
    db.flush()
    for line in payload.lines:
        db.add(
            InvoiceLine(
                organization_id=ctx.organization_id,
                invoice_id=invoice.id,
                **line.model_dump(),
            )
        )
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="invoice.created",
        entity_type="invoice",
        entity_id=invoice.id,
        after_state={
            "invoice_number": payload.invoice_number,
            "subtotal_minor": subtotal,
            "status": payload.status.value,
        },
    )
    db.commit()
    db.refresh(invoice)
    return InvoiceOut.model_validate(invoice)


@router.patch("/{invoice_id}/status", response_model=InvoiceOut)
def update_invoice_status(
    invoice_id: uuid.UUID,
    new_status: InvoiceStatus,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> InvoiceOut:
    invoice = get_org_object(db, Invoice, invoice_id, ctx.organization_id)
    before = invoice.status.value
    invoice.status = new_status
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="invoice.status_changed",
        entity_type="invoice",
        entity_id=invoice.id,
        before_state={"status": before},
        after_state={"status": new_status.value},
    )
    db.commit()
    return InvoiceOut.model_validate(invoice)
