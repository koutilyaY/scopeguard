"""Reports and exports: findings CSV, audit JSON, PDF evidence report."""

import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth_context, get_org_object
from app.models import Finding
from app.models.enums import ReviewStatus
from app.services.audit import record_audit_event
from app.services.exports import finding_to_audit_json, finding_to_pdf, findings_to_csv

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/findings.csv")
def export_findings_csv(
    project_id: uuid.UUID | None = Query(None),
    review_status: ReviewStatus | None = Query(None),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    stmt = select(Finding).where(Finding.organization_id == ctx.organization_id)
    if project_id:
        stmt = stmt.where(Finding.project_id == project_id)
    if review_status:
        stmt = stmt.where(Finding.review_status == review_status)
    findings = list(db.execute(stmt.order_by(Finding.created_at.desc())).scalars())
    content = findings_to_csv(db, ctx.organization_id, findings)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="report.findings_csv",
        entity_type="report",
        after_state={"count": len(findings)},
    )
    db.commit()
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="scopeguard-findings.csv"'},
    )


@router.get("/findings/{finding_id}.json")
def export_finding_json(
    finding_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> dict:
    finding = get_org_object(db, Finding, finding_id, ctx.organization_id)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="report.finding_json",
        entity_type="finding",
        entity_id=finding.id,
    )
    db.commit()
    return finding_to_audit_json(db, finding)


@router.get("/findings/{finding_id}.pdf")
def export_finding_pdf(
    finding_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    finding = get_org_object(db, Finding, finding_id, ctx.organization_id)
    pdf_bytes = finding_to_pdf(db, finding)
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="report.finding_pdf",
        entity_type="finding",
        entity_id=finding.id,
    )
    db.commit()
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="evidence-report-{finding.id}.pdf"'},
    )
