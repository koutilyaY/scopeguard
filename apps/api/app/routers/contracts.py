"""Contract CRUD, verification, and extraction trigger."""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Client, Contract, Document, Project
from app.models.enums import ContractStatus, ExtractionStatus
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import paginate

router = APIRouter(prefix="/contracts", tags=["contracts"])


class ContractIn(BaseModel):
    client_id: uuid.UUID
    project_id: uuid.UUID | None = None
    contract_number: str | None = None
    title: str
    effective_from: date | None = None
    effective_to: date | None = None
    currency: str = "USD"
    status: ContractStatus = ContractStatus.draft
    governing_document_id: uuid.UUID | None = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    project_id: uuid.UUID | None
    contract_number: str | None
    title: str
    effective_from: date | None
    effective_to: date | None
    currency: str
    status: ContractStatus
    governing_document_id: uuid.UUID | None
    verified_by_user: uuid.UUID | None
    verified_at: datetime | None


@router.get("", response_model=Page[ContractOut])
def list_contracts(
    params: PageParams = Depends(),
    client_id: uuid.UUID | None = Query(None),
    project_id: uuid.UUID | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[ContractOut]:
    stmt = (
        select(Contract)
        .where(Contract.organization_id == ctx.organization_id)
        .order_by(Contract.created_at.desc())
    )
    if client_id:
        stmt = stmt.where(Contract.client_id == client_id)
    if project_id:
        stmt = stmt.where(Contract.project_id == project_id)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[ContractOut.model_validate(c) for c in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract(
    contract_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> ContractOut:
    contract = get_org_object(db, Contract, contract_id, ctx.organization_id)
    return ContractOut.model_validate(contract)


@router.post("", response_model=ContractOut, status_code=201)
def create_contract(
    payload: ContractIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> ContractOut:
    get_org_object(db, Client, payload.client_id, ctx.organization_id)
    if payload.project_id:
        get_org_object(db, Project, payload.project_id, ctx.organization_id)
    if payload.governing_document_id:
        get_org_object(db, Document, payload.governing_document_id, ctx.organization_id)
    contract = Contract(organization_id=ctx.organization_id, **payload.model_dump())
    db.add(contract)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="contract.created",
        entity_type="contract",
        entity_id=contract.id,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return ContractOut.model_validate(contract)


@router.put("/{contract_id}", response_model=ContractOut)
def update_contract(
    contract_id: uuid.UUID,
    payload: ContractIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> ContractOut:
    contract = get_org_object(db, Contract, contract_id, ctx.organization_id)
    get_org_object(db, Client, payload.client_id, ctx.organization_id)
    before = {"title": contract.title, "status": contract.status.value}
    for key, value in payload.model_dump().items():
        setattr(contract, key, value)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="contract.updated",
        entity_type="contract",
        entity_id=contract.id,
        before_state=before,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/verify", response_model=ContractOut)
def verify_contract(
    contract_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> ContractOut:
    contract = get_org_object(db, Contract, contract_id, ctx.organization_id)
    contract.verified_by_user = ctx.user.id
    contract.verified_at = datetime.now(UTC)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="contract.verified",
        entity_type="contract",
        entity_id=contract.id,
    )
    db.commit()
    return ContractOut.model_validate(contract)


@router.post("/{contract_id}/extract", status_code=202)
def trigger_extraction(
    contract_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Queue LLM clause extraction for the contract's governing document."""
    contract = get_org_object(db, Contract, contract_id, ctx.organization_id)
    if not contract.governing_document_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="Contract has no governing document"
        )
    document = get_org_object(db, Document, contract.governing_document_id, ctx.organization_id)
    if document.extraction_status != ExtractionStatus.completed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                "Document text extraction has not completed "
                f"(status: {document.extraction_status.value})."
            ),
        )
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="contract.extraction_queued",
        entity_type="contract",
        entity_id=contract.id,
    )
    db.commit()

    from app.worker import extract_contract_clauses_task

    extract_contract_clauses_task.delay(str(contract.id))
    return {"detail": "Clause extraction queued"}
