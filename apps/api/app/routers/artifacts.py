"""Generated artifact endpoints. Generation requires a human-approved finding."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import DECISION_ROLES, AuthContext, get_org_object, require_any_role
from app.models import Finding, GeneratedArtifact
from app.models.enums import ArtifactType
from app.services.artifacts import generate_artifact
from app.services.audit import record_audit_event
from app.services.llm import LLMError

router = APIRouter(prefix="/generated-artifacts", tags=["generated-artifacts"])


class ArtifactGenerateIn(BaseModel):
    finding_id: uuid.UUID
    artifact_type: ArtifactType


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    finding_id: uuid.UUID
    artifact_type: ArtifactType
    content: str
    generated_by_model: str | None
    prompt_version: str | None
    approved_by_user: uuid.UUID | None
    created_at: datetime


@router.post("", response_model=ArtifactOut, status_code=201)
def create_artifact(
    payload: ArtifactGenerateIn,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ArtifactOut:
    if payload.artifact_type == ArtifactType.evidence_report:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Evidence reports are generated deterministically via /reports",
        )
    finding = get_org_object(db, Finding, payload.finding_id, ctx.organization_id)
    try:
        artifact = generate_artifact(db, finding, payload.artifact_type)
    except PermissionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Draft generation failed: the language model is unavailable or "
            f"returned invalid output. ({exc})",
        ) from exc
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="artifact.generated",
        entity_type="generated_artifact",
        entity_id=artifact.id,
        after_state={"artifact_type": payload.artifact_type.value, "finding_id": str(finding.id)},
    )
    db.commit()
    return ArtifactOut.model_validate(artifact)


@router.get("/{artifact_id}", response_model=ArtifactOut)
def get_artifact(
    artifact_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ArtifactOut:
    artifact = get_org_object(db, GeneratedArtifact, artifact_id, ctx.organization_id)
    return ArtifactOut.model_validate(artifact)


@router.post("/{artifact_id}/approve", response_model=ArtifactOut)
def approve_artifact(
    artifact_id: uuid.UUID,
    ctx: AuthContext = Depends(require_any_role(DECISION_ROLES)),
    db: Session = Depends(get_db),
) -> ArtifactOut:
    artifact = get_org_object(db, GeneratedArtifact, artifact_id, ctx.organization_id)
    artifact.approved_by_user = ctx.user.id
    record_audit_event(
        db,
        organization_id=ctx.organization_id,
        actor_user_id=ctx.user.id,
        action="artifact.approved",
        entity_type="generated_artifact",
        entity_id=artifact.id,
    )
    db.commit()
    return ArtifactOut.model_validate(artifact)
