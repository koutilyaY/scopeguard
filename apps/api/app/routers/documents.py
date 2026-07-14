"""Document upload, listing, retrieval and deletion.

Bytes live in MinIO under random keys; metadata lives in Postgres. Extraction and
embedding run as background jobs.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_auth_context, get_org_object, require_any_role
from app.models import Client, Document, Project
from app.models.enums import DocumentType, ExtractionStatus
from app.schemas.common import Page, PageParams
from app.services.audit import record_audit_event
from app.services.files import sha256_hex, validate_upload
from app.services.pagination import paginate
from app.services.storage import delete_object, generate_storage_key, get_object, put_object

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger("scopeguard.documents")


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID | None
    project_id: uuid.UUID | None
    document_type: DocumentType
    original_filename: str
    sha256: str
    mime_type: str
    file_size: int
    extraction_status: ExtractionStatus
    extraction_error: str | None
    created_at: datetime
    superseded_by_document_id: uuid.UUID | None


class DocumentTextOut(BaseModel):
    id: uuid.UUID
    extraction_status: ExtractionStatus
    extracted_text: str | None
    extraction_error: str | None


class UploadResponse(BaseModel):
    document: DocumentOut
    duplicate_of: uuid.UUID | None = None


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    params: PageParams = Depends(),
    project_id: uuid.UUID | None = Query(None),
    client_id: uuid.UUID | None = Query(None),
    document_type: DocumentType | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[DocumentOut]:
    stmt = (
        select(Document)
        .where(Document.organization_id == ctx.organization_id)
        .order_by(Document.created_at.desc())
    )
    if project_id:
        stmt = stmt.where(Document.project_id == project_id)
    if client_id:
        stmt = stmt.where(Document.client_id == client_id)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    items, total = paginate(db, stmt, params)
    return Page(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


@router.post("/upload", response_model=UploadResponse, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    document_type: DocumentType = Form(...),
    client_id: uuid.UUID | None = Form(None),
    project_id: uuid.UUID | None = Form(None),
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> UploadResponse:
    data = file.file.read()
    safe_name, ext = validate_upload(file.filename or "upload", file.content_type or "", data)

    if client_id:
        get_org_object(db, Client, client_id, ctx.organization_id)
    if project_id:
        project = get_org_object(db, Project, project_id, ctx.organization_id)
        if client_id is None:
            client_id = project.client_id

    digest = sha256_hex(data)
    duplicate = db.execute(
        select(Document).where(
            Document.organization_id == ctx.organization_id, Document.sha256 == digest
        )
    ).scalar_one_or_none()

    storage_key = generate_storage_key(str(ctx.organization_id), ext)
    put_object(storage_key, data, file.content_type or "application/octet-stream")

    document = Document(
        organization_id=ctx.organization_id,
        client_id=client_id,
        project_id=project_id,
        document_type=document_type,
        original_filename=safe_name,
        storage_key=storage_key,
        sha256=digest,
        mime_type=(file.content_type or "application/octet-stream").split(";")[0],
        file_size=len(data),
        extraction_status=ExtractionStatus.pending,
        uploaded_by=ctx.user.id,
    )
    db.add(document)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        after_state={
            "filename": safe_name,
            "document_type": document_type.value,
            "sha256": digest,
            "duplicate_of": str(duplicate.id) if duplicate else None,
        },
    )
    db.commit()

    from app.worker import extract_document_task

    extract_document_task.delay(str(document.id))

    return UploadResponse(
        document=DocumentOut.model_validate(document),
        duplicate_of=duplicate.id if duplicate else None,
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> DocumentOut:
    document = get_org_object(db, Document, document_id, ctx.organization_id)
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/text", response_model=DocumentTextOut)
def get_document_text(
    document_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> DocumentTextOut:
    document = get_org_object(db, Document, document_id, ctx.organization_id)
    return DocumentTextOut(
        id=document.id,
        extraction_status=document.extraction_status,
        extracted_text=document.extracted_text,
        extraction_error=document.extraction_error,
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    document = get_org_object(db, Document, document_id, ctx.organization_id)
    try:
        data = get_object(document.storage_key)
    except Exception:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Stored file unavailable") from None
    return Response(
        content=data,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    document = get_org_object(db, Document, document_id, ctx.organization_id)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="document.deleted",
        entity_type="document",
        entity_id=document.id,
        before_state={"filename": document.original_filename, "sha256": document.sha256},
    )
    try:
        delete_object(document.storage_key)
    except Exception:
        logger.warning("Object already absent in storage for document %s", document.id)
    db.delete(document)
    db.commit()
    return {"detail": "Document deleted"}
