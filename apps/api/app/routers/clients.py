"""Client CRUD."""

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Client
from app.models.enums import ClientStatus
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import apply_sort, paginate

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientIn(BaseModel):
    legal_name: str
    display_name: str
    external_reference: str | None = None
    status: ClientStatus = ClientStatus.active


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    legal_name: str
    display_name: str
    external_reference: str | None
    status: ClientStatus


@router.get("", response_model=Page[ClientOut])
def list_clients(
    params: PageParams = Depends(),
    status_filter: ClientStatus | None = Query(None, alias="status"),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[ClientOut]:
    stmt = select(Client).where(Client.organization_id == ctx.organization_id)
    if status_filter:
        stmt = stmt.where(Client.status == status_filter)
    stmt = apply_sort(stmt, Client, params.sort or "display_name", {"display_name", "created_at"})
    items, total = paginate(db, stmt, params)
    return Page(
        items=[ClientOut.model_validate(c) for c in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> ClientOut:
    client = get_org_object(db, Client, client_id, ctx.organization_id)
    return ClientOut.model_validate(client)


@router.post("", response_model=ClientOut, status_code=201)
def create_client(
    payload: ClientIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> ClientOut:
    client = Client(organization_id=ctx.organization_id, **payload.model_dump())
    db.add(client)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="client.created",
        entity_type="client",
        entity_id=client.id,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return ClientOut.model_validate(client)


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: uuid.UUID,
    payload: ClientIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> ClientOut:
    client = get_org_object(db, Client, client_id, ctx.organization_id)
    before = {
        "legal_name": client.legal_name,
        "display_name": client.display_name,
        "status": client.status.value,
    }
    for key, value in payload.model_dump().items():
        setattr(client, key, value)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="client.updated",
        entity_type="client",
        entity_id=client.id,
        before_state=before,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return ClientOut.model_validate(client)
