"""Project CRUD and guarded deletion workflow."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Client, Project
from app.models.enums import ProjectStatus, UserRole
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.pagination import apply_sort, paginate

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectIn(BaseModel):
    client_id: uuid.UUID
    name: str
    external_reference: str | None = None
    description: str | None = None
    status: ProjectStatus = ProjectStatus.active
    start_date: date | None = None
    end_date: date | None = None
    currency: str = "USD"


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    name: str
    external_reference: str | None
    description: str | None
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    currency: str


class ProjectDeleteRequest(BaseModel):
    confirm_name: str


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    params: PageParams = Depends(),
    client_id: uuid.UUID | None = Query(None),
    status_filter: ProjectStatus | None = Query(None, alias="status"),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[ProjectOut]:
    stmt = select(Project).where(Project.organization_id == ctx.organization_id)
    if client_id:
        stmt = stmt.where(Project.client_id == client_id)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    stmt = apply_sort(stmt, Project, params.sort or "name", {"name", "created_at", "start_date"})
    items, total = paginate(db, stmt, params)
    return Page(
        items=[ProjectOut.model_validate(p) for p in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = get_org_object(db, Project, project_id, ctx.organization_id)
    return ProjectOut.model_validate(project)


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> ProjectOut:
    get_org_object(db, Client, payload.client_id, ctx.organization_id)  # tenant check
    project = Project(organization_id=ctx.organization_id, **payload.model_dump())
    db.add(project)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="project.created",
        entity_type="project",
        entity_id=project.id,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return ProjectOut.model_validate(project)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectIn,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = get_org_object(db, Project, project_id, ctx.organization_id)
    get_org_object(db, Client, payload.client_id, ctx.organization_id)
    before = {"name": project.name, "status": project.status.value}
    for key, value in payload.model_dump().items():
        setattr(project, key, value)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="project.updated",
        entity_type="project",
        entity_id=project.id,
        before_state=before,
        after_state=payload.model_dump(mode="json"),
    )
    db.commit()
    return ProjectOut.model_validate(project)


@router.post("/{project_id}/delete", status_code=200)
def delete_project(
    project_id: uuid.UUID,
    payload: ProjectDeleteRequest,
    ctx: AuthContext = Depends(require_any_role({UserRole.organization_admin})),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Destructive: cascades to documents, work items, time entries, findings.

    Requires typing the exact project name; an audit tombstone records the deletion.
    """
    project = get_org_object(db, Project, project_id, ctx.organization_id)
    if payload.confirm_name != project.name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Confirmation name does not match the project name.",
        )
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="project.deleted",
        entity_type="project",
        entity_id=project.id,
        before_state={"name": project.name, "client_id": str(project.client_id)},
    )
    db.delete(project)
    db.commit()
    return {"detail": f"Project '{payload.confirm_name}' and its records were deleted."}
