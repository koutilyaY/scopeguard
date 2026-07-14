"""Organization settings and data export."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth_context, require_any_role
from app.models import (
    Client,
    Contract,
    ContractClause,
    Finding,
    Invoice,
    Organization,
    Project,
    TimeEntry,
    WorkItem,
)
from app.models.enums import UserRole
from app.services.audit import record_audit_event

router = APIRouter(prefix="/organizations", tags=["organizations"])

admin_only = require_any_role({UserRole.organization_admin})


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    retention_days: int | None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    retention_days: int | None = None


@router.get("/current", response_model=OrganizationOut)
def get_current_organization(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> OrganizationOut:
    org = db.get(Organization, ctx.organization_id)
    return OrganizationOut.model_validate(org)


@router.patch("/current", response_model=OrganizationOut)
def update_organization(
    payload: OrganizationUpdate,
    ctx: AuthContext = Depends(admin_only),
    db: Session = Depends(get_db),
) -> OrganizationOut:
    org = db.get(Organization, ctx.organization_id)
    assert org is not None
    before = {"name": org.name, "retention_days": org.retention_days}
    if payload.name is not None:
        org.name = payload.name
    if payload.retention_days is not None:
        org.retention_days = payload.retention_days
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="organization.updated",
        entity_type="organization",
        entity_id=org.id,
        before_state=before,
        after_state={"name": org.name, "retention_days": org.retention_days},
    )
    db.commit()
    return OrganizationOut.model_validate(org)


@router.get("/current/export")
def export_organization_data(
    ctx: AuthContext = Depends(admin_only),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Full JSON export of the organization's own data (privacy/portability)."""

    def dump(model) -> list[dict[str, Any]]:
        rows = db.execute(
            select(model).where(model.organization_id == ctx.organization_id)
        ).scalars()
        out = []
        for row in rows:
            item = {}
            for column in model.__table__.columns:
                value = getattr(row, column.name)
                item[column.name] = str(value) if value is not None else None
            out.append(item)
        return out

    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="organization.data_exported",
        entity_type="organization",
        entity_id=ctx.organization_id,
    )
    db.commit()
    return {
        "clients": dump(Client),
        "projects": dump(Project),
        "contracts": dump(Contract),
        "contract_clauses": dump(ContractClause),
        "work_items": dump(WorkItem),
        "time_entries": dump(TimeEntry),
        "invoices": dump(Invoice),
        "findings": dump(Finding),
    }
