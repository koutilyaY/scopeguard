"""Review decisions. Every status change requires a reason and is audited."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import DECISION_ROLES, AuthContext, get_org_object, require_any_role
from app.models import Finding, ReviewDecision
from app.models.enums import ReviewStatus
from app.routers.findings import FindingOut
from app.services.audit import record_audit_event

router = APIRouter(prefix="/decisions", tags=["decisions"])

ALLOWED_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.pending: {
        ReviewStatus.approved_for_followup,
        ReviewStatus.approved_for_billing,
        ReviewStatus.rejected,
        ReviewStatus.needs_more_evidence,
        ReviewStatus.already_resolved,
    },
    ReviewStatus.needs_more_evidence: {
        ReviewStatus.approved_for_followup,
        ReviewStatus.approved_for_billing,
        ReviewStatus.rejected,
        ReviewStatus.already_resolved,
        ReviewStatus.pending,
    },
    ReviewStatus.approved_for_followup: {
        ReviewStatus.approved_for_billing,
        ReviewStatus.rejected,
        ReviewStatus.already_resolved,
        ReviewStatus.needs_more_evidence,
    },
    ReviewStatus.approved_for_billing: {
        ReviewStatus.rejected,
        ReviewStatus.already_resolved,
    },
    ReviewStatus.rejected: {ReviewStatus.pending},
    ReviewStatus.already_resolved: {ReviewStatus.pending},
}


class DecisionIn(BaseModel):
    finding_id: uuid.UUID
    new_status: ReviewStatus
    reason: str = Field(min_length=5, max_length=4000)


@router.post("", response_model=FindingOut)
def decide(
    payload: DecisionIn,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> FindingOut:
    finding = get_org_object(db, Finding, payload.finding_id, ctx.organization_id)
    current = finding.review_status
    if payload.new_status == current:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Finding already has this status")
    if payload.new_status not in ALLOWED_TRANSITIONS.get(current, set()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move a finding from {current.value} to {payload.new_status.value}",
        )
    decision = ReviewDecision(
        organization_id=ctx.organization_id,
        finding_id=finding.id,
        reviewer_id=ctx.user.id,
        previous_status=current,
        new_status=payload.new_status,
        reason=payload.reason,
        created_at=datetime.now(UTC),
    )
    db.add(decision)
    finding.review_status = payload.new_status
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="finding.decision",
        entity_type="finding",
        entity_id=finding.id,
        before_state={"review_status": current.value},
        after_state={"review_status": payload.new_status.value, "reason": payload.reason},
    )
    db.commit()
    return FindingOut.model_validate(finding)
