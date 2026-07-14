"""Finding inbox (rich filters) and finding detail with full evidence."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth_context, get_org_object
from app.models import (
    ContractClause,
    CustomerRequest,
    Finding,
    FindingEvidence,
    GeneratedArtifact,
    InvoiceLine,
    Project,
    ReviewDecision,
    TimeEntry,
    WorkItem,
)
from app.models.enums import (
    Classification,
    EvidenceType,
    FindingType,
    ReviewStatus,
    RiskLevel,
)
from app.schemas.common import Page, PageParams
from app.services.pagination import apply_sort, paginate

router = APIRouter(prefix="/findings", tags=["findings"])

DISCLAIMER = (
    "ScopeGuard provides operational review assistance. Findings are not legal or "
    "accounting advice; contract interpretation may be ambiguous. Human verification "
    "is required. Potential value does not equal invoiced or collected revenue."
)


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    review_run_id: uuid.UUID
    project_id: uuid.UUID
    finding_type: FindingType
    title: str
    explanation: str
    classification: Classification
    confidence: float | None
    potential_value_minor: int | None
    value_unavailable_reason: str | None
    currency: str | None
    review_status: ReviewStatus
    risk_level: RiskLevel
    evidence_score: float | None
    created_at: datetime
    updated_at: datetime


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_type: str
    entity_type: EvidenceType
    entity_id: uuid.UUID | None
    quotation: str | None
    document_page: int | None
    section_reference: str | None
    relevance_explanation: str | None
    entity_summary: dict[str, Any] | None = None


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reviewer_id: uuid.UUID | None
    previous_status: ReviewStatus
    new_status: ReviewStatus
    reason: str
    created_at: datetime


class ArtifactSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    artifact_type: str
    created_at: datetime
    approved_by_user: uuid.UUID | None


class FindingDetailOut(FindingOut):
    evidence_score_breakdown: dict[str, Any] | None
    calculation_breakdown: dict[str, Any] | None
    missing_evidence: list[str] | None
    contradicting_summary: str | None
    evidence: list[EvidenceOut]
    decisions: list[DecisionOut]
    artifacts: list[ArtifactSummaryOut]
    disclaimer: str = DISCLAIMER


@router.get("", response_model=Page[FindingOut])
def list_findings(
    params: PageParams = Depends(),
    project_id: uuid.UUID | None = Query(None),
    client_id: uuid.UUID | None = Query(None),
    review_run_id: uuid.UUID | None = Query(None),
    finding_type: FindingType | None = Query(None),
    classification: Classification | None = Query(None),
    review_status: ReviewStatus | None = Query(None),
    risk_level: RiskLevel | None = Query(None),
    confidence_min: float | None = Query(None, ge=0, le=1),
    confidence_max: float | None = Query(None, ge=0, le=1),
    value_min_minor: int | None = Query(None),
    value_max_minor: int | None = Query(None),
    evidence_score_min: float | None = Query(None, ge=0, le=1),
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Page[FindingOut]:
    stmt = select(Finding).where(Finding.organization_id == ctx.organization_id)
    if project_id:
        stmt = stmt.where(Finding.project_id == project_id)
    if client_id:
        stmt = stmt.join(Project, Project.id == Finding.project_id).where(
            Project.client_id == client_id
        )
    if review_run_id:
        stmt = stmt.where(Finding.review_run_id == review_run_id)
    if finding_type:
        stmt = stmt.where(Finding.finding_type == finding_type)
    if classification:
        stmt = stmt.where(Finding.classification == classification)
    if review_status:
        stmt = stmt.where(Finding.review_status == review_status)
    if risk_level:
        stmt = stmt.where(Finding.risk_level == risk_level)
    if confidence_min is not None:
        stmt = stmt.where(Finding.confidence >= confidence_min)
    if confidence_max is not None:
        stmt = stmt.where(Finding.confidence <= confidence_max)
    if value_min_minor is not None:
        stmt = stmt.where(Finding.potential_value_minor >= value_min_minor)
    if value_max_minor is not None:
        stmt = stmt.where(Finding.potential_value_minor <= value_max_minor)
    if evidence_score_min is not None:
        stmt = stmt.where(Finding.evidence_score >= evidence_score_min)
    stmt = apply_sort(
        stmt,
        Finding,
        params.sort or "-created_at",
        {"created_at", "potential_value_minor", "confidence", "evidence_score", "risk_level"},
    )
    items, total = paginate(db, stmt, params)
    return Page(
        items=[FindingOut.model_validate(f) for f in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


def _entity_summary(db: Session, evidence: FindingEvidence) -> dict[str, Any] | None:
    """Small denormalized summary of the referenced entity for display."""
    if evidence.entity_id is None:
        return None
    if evidence.entity_type == EvidenceType.contract_clause:
        clause = db.get(ContractClause, evidence.entity_id)
        if clause:
            return {
                "title": clause.title,
                "clause_type": clause.clause_type.value,
                "human_verified": clause.human_verified,
                "page_number": clause.page_number,
                "section_reference": clause.section_reference,
            }
    elif evidence.entity_type == EvidenceType.work_item:
        item = db.get(WorkItem, evidence.entity_id)
        if item:
            return {
                "title": item.title,
                "external_id": item.external_id,
                "status": item.status.value,
                "work_type": item.work_type,
            }
    elif evidence.entity_type == EvidenceType.time_entry:
        entry = db.get(TimeEntry, evidence.entity_id)
        if entry:
            return {
                "employee_name": entry.employee_name,
                "employee_role": entry.employee_role,
                "work_date": str(entry.work_date),
                "minutes": entry.minutes,
            }
    elif evidence.entity_type == EvidenceType.customer_request:
        request = db.get(CustomerRequest, evidence.entity_id)
        if request:
            return {
                "subject": request.subject,
                "sender": request.sender,
                "request_date": str(request.request_date) if request.request_date else None,
                "authorization": request.customer_authorization_status.value,
            }
    elif evidence.entity_type == EvidenceType.invoice_line:
        line = db.get(InvoiceLine, evidence.entity_id)
        if line:
            return {"description": line.description, "amount_minor": line.amount_minor}
    return None


@router.get("/{finding_id}", response_model=FindingDetailOut)
def get_finding(
    finding_id: uuid.UUID,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> FindingDetailOut:
    finding = get_org_object(db, Finding, finding_id, ctx.organization_id)
    evidence_rows = list(
        db.execute(
            select(FindingEvidence).where(
                FindingEvidence.organization_id == ctx.organization_id,
                FindingEvidence.finding_id == finding.id,
            )
        ).scalars()
    )
    decisions = list(
        db.execute(
            select(ReviewDecision)
            .where(
                ReviewDecision.organization_id == ctx.organization_id,
                ReviewDecision.finding_id == finding.id,
            )
            .order_by(ReviewDecision.created_at.desc())
        ).scalars()
    )
    artifacts = list(
        db.execute(
            select(GeneratedArtifact)
            .where(
                GeneratedArtifact.organization_id == ctx.organization_id,
                GeneratedArtifact.finding_id == finding.id,
            )
            .order_by(GeneratedArtifact.created_at.desc())
        ).scalars()
    )
    evidence_out = []
    for row in evidence_rows:
        item = EvidenceOut.model_validate(row)
        item.entity_summary = _entity_summary(db, row)
        evidence_out.append(item)

    base = FindingOut.model_validate(finding)
    return FindingDetailOut(
        **base.model_dump(),
        evidence_score_breakdown=finding.evidence_score_breakdown,
        calculation_breakdown=finding.calculation_breakdown,
        missing_evidence=finding.missing_evidence,
        contradicting_summary=finding.contradicting_summary,
        evidence=evidence_out,
        decisions=[DecisionOut.model_validate(d) for d in decisions],
        artifacts=[
            ArtifactSummaryOut(
                id=a.id,
                artifact_type=a.artifact_type.value,
                created_at=a.created_at,
                approved_by_user=a.approved_by_user,
            )
            for a in artifacts
        ],
    )
