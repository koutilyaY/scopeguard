"""Import endpoints: preview (parse + validate) and commit, per import type.

The preview step returns detected columns, sample rows and row-level errors so the
UI can offer column mapping before anything is written.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Json
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import WRITE_ROLES, AuthContext, get_org_object, require_any_role
from app.models import CustomerRequest, Document, Project
from app.models.enums import AuthorizationStatus, DocumentType, ExtractionStatus
from app.services import imports as import_service
from app.services.audit import record_audit_event
from app.services.extraction import extract_eml, extract_txt
from app.services.files import sha256_hex, validate_upload
from app.services.storage import generate_storage_key, put_object

router = APIRouter(prefix="/imports", tags=["imports"])

VALIDATORS = {
    "work_items": (
        import_service.validate_work_item_rows,
        import_service.commit_work_items,
        import_service.JIRA_FIELDS,
    ),
    "time_entries": (
        import_service.validate_time_entry_rows,
        import_service.commit_time_entries,
        import_service.TIMESHEET_FIELDS,
    ),
    "invoices": (
        import_service.validate_invoice_rows,
        import_service.commit_invoices,
        import_service.INVOICE_FIELDS,
    ),
}


class RowErrorOut(BaseModel):
    row: int
    field: str
    message: str


class PreviewOut(BaseModel):
    import_type: str
    supported_fields: list[str]
    columns: list[str]
    suggested_mapping: dict[str, str]
    sample_rows: list[dict]
    total_rows: int
    valid_rows: int
    errors: list[RowErrorOut]
    warnings: list[RowErrorOut]


class CommitOut(BaseModel):
    created: int
    skipped_duplicates: int
    errors: list[RowErrorOut]
    warnings: list[RowErrorOut]


def _suggest_mapping(fields: list[str], columns: list[str]) -> dict[str, str]:
    """Best-effort automatic column mapping by name similarity."""
    aliases = {
        "external_id": ["id", "key", "issue key", "issue", "ticket", "entry id"],
        "title": ["summary", "title", "name"],
        "description": ["description", "notes", "details", "comment"],
        "status": ["status", "state"],
        "work_type": ["type", "issue type", "work type", "category"],
        "assignee": ["assignee", "owner"],
        "created_at": ["created", "created at", "created date"],
        "completed_at": ["resolved", "completed", "done date", "resolution date"],
        "source_url": ["url", "link"],
        "employee_name": ["employee", "employee name", "person", "user", "resource"],
        "employee_role": ["role", "employee role", "title"],
        "work_date": ["date", "work date", "day"],
        "hours": ["hours", "time spent", "duration"],
        "minutes": ["minutes", "mins"],
        "billable_status": ["billable", "billable status"],
        "work_item_external_id": ["work item", "issue key", "ticket", "jira id", "work item id"],
        "invoice_number": ["invoice", "invoice number", "invoice #", "number"],
        "billing_period_start": ["period start", "billing period start", "from"],
        "billing_period_end": ["period end", "billing period end", "to"],
        "issue_date": ["issue date", "invoice date", "date"],
        "currency": ["currency"],
        "line_description": ["line description", "description", "item"],
        "service_category": ["service category", "category", "service"],
        "quantity": ["quantity", "qty", "units"],
        "unit_price": ["unit price", "rate", "price"],
        "amount": ["amount", "total", "line total"],
    }
    lowered = {c.lower(): c for c in columns}
    mapping: dict[str, str] = {}
    for field_name in fields:
        for alias in [field_name.replace("_", " "), *aliases.get(field_name, [])]:
            if alias in lowered:
                mapping[field_name] = lowered[alias]
                break
    return mapping


@router.post("/{import_type}/preview", response_model=PreviewOut)
def preview_import(
    import_type: str,
    file: UploadFile = File(...),
    mapping: Json[dict[str, str]] | None = Form(None),
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
) -> PreviewOut:
    if import_type not in VALIDATORS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown import type")
    validator, _, fields = VALIDATORS[import_type]
    data = file.file.read()
    safe_name, _ = validate_upload(file.filename or "import.csv", file.content_type or "", data)
    try:
        columns, rows = import_service.parse_tabular(safe_name, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    effective_mapping = mapping or _suggest_mapping(fields, columns)
    valid, errors, warnings = validator(rows, effective_mapping)
    return PreviewOut(
        import_type=import_type,
        supported_fields=fields,
        columns=columns,
        suggested_mapping=effective_mapping,
        sample_rows=rows[:10],
        total_rows=len(rows),
        valid_rows=len(valid),
        errors=[RowErrorOut(**e.__dict__) for e in errors],
        warnings=[RowErrorOut(**w.__dict__) for w in warnings],
    )


@router.post("/{import_type}/commit", response_model=CommitOut)
def commit_import(
    import_type: str,
    file: UploadFile = File(...),
    project_id: uuid.UUID = Form(...),
    mapping: Json[dict[str, str]] | None = Form(None),
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> CommitOut:
    if import_type not in VALIDATORS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown import type")
    validator, committer, fields = VALIDATORS[import_type]
    project = get_org_object(db, Project, project_id, ctx.organization_id)
    data = file.file.read()
    safe_name, _ = validate_upload(file.filename or "import.csv", file.content_type or "", data)
    try:
        columns, rows = import_service.parse_tabular(safe_name, data)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    effective_mapping = mapping or _suggest_mapping(fields, columns)
    valid, errors, warnings = validator(rows, effective_mapping)
    result = committer(db, ctx.organization_id, project, valid)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action=f"import.{import_type}",
        entity_type="project",
        entity_id=project.id,
        after_state={
            "filename": safe_name,
            "created": result.created,
            "skipped_duplicates": result.skipped_duplicates,
            "row_errors": len(errors),
        },
    )
    db.commit()
    return CommitOut(
        created=result.created,
        skipped_duplicates=result.skipped_duplicates,
        errors=[RowErrorOut(**e.__dict__) for e in errors],
        warnings=[RowErrorOut(**w.__dict__) for w in [*warnings, *result.warnings]],
    )


@router.post("/customer-request/upload", status_code=201)
def import_customer_request(
    file: UploadFile = File(...),
    project_id: uuid.UUID = Form(...),
    ctx: AuthContext = Depends(require_any_role(WRITE_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    """Create a CustomerRequest from an uploaded EML or TXT file (PDF/DOCX go
    through the documents endpoint and can be linked manually)."""
    project = get_org_object(db, Project, project_id, ctx.organization_id)
    data = file.file.read()
    safe_name, ext = validate_upload(file.filename or "request.eml", file.content_type or "", data)
    if ext not in (".eml", ".txt"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Use .eml or .txt here; upload PDF/DOCX via /documents/upload",
        )

    storage_key = generate_storage_key(str(ctx.organization_id), ext)
    put_object(storage_key, data, file.content_type or "application/octet-stream")
    document = Document(
        organization_id=ctx.organization_id,
        client_id=project.client_id,
        project_id=project.id,
        document_type=DocumentType.customer_request,
        original_filename=safe_name,
        storage_key=storage_key,
        sha256=sha256_hex(data),
        mime_type=(file.content_type or "application/octet-stream").split(";")[0],
        file_size=len(data),
        extraction_status=ExtractionStatus.completed,
        uploaded_by=ctx.user.id,
    )

    if ext == ".eml":
        result, parsed = extract_eml(data)
        if not result.ok or parsed is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.error)
        subject, sender, recipients, body = (
            parsed.subject,
            parsed.sender,
            parsed.recipients,
            parsed.body,
        )
        request_date = None
        if parsed.date:
            from email.utils import parsedate_to_datetime

            try:
                request_date = parsedate_to_datetime(parsed.date).date()
            except (TypeError, ValueError):
                request_date = None
    else:
        result = extract_txt(data)
        if not result.ok:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=result.error)
        body = result.plain_text
        subject = safe_name
        sender = recipients = None
        request_date = None

    document.extracted_text = result.full_text
    db.add(document)
    db.flush()

    request = CustomerRequest(
        organization_id=ctx.organization_id,
        project_id=project.id,
        subject=subject[:500],
        sender=sender,
        recipients=recipients,
        request_date=request_date,
        body=body,
        source_document_id=document.id,
        customer_authorization_status=AuthorizationStatus.none,
    )
    db.add(request)
    db.flush()
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="import.customer_request",
        entity_type="customer_request",
        entity_id=request.id,
        after_state={"subject": request.subject, "filename": safe_name},
    )
    db.commit()
    return {"id": str(request.id), "subject": request.subject, "document_id": str(document.id)}
