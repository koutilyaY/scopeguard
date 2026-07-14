"""ReviewRun, Finding, FindingEvidence, ReviewDecision, GeneratedArtifact."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    ArtifactType,
    Classification,
    EvidenceType,
    FindingType,
    ReviewRunStatus,
    ReviewStatus,
    RiskLevel,
)


class ReviewRun(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "review_runs"
    __table_args__ = (
        Index("ix_review_runs_org_project", "organization_id", "project_id"),
        # idempotency: one *pending/running* run per project+period is enforced in service code
        Index(
            "ix_review_runs_period",
            "project_id",
            "billing_period_start",
            "billing_period_end",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    billing_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    billing_period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ReviewRunStatus] = mapped_column(
        Enum(ReviewRunStatus, native_enum=False, length=30),
        nullable=False,
        default=ReviewRunStatus.pending,
    )
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    model_name: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    failure_reason: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    findings: Mapped[list["Finding"]] = relationship(back_populates="review_run")


class Finding(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_findings_confidence",
        ),
        Index("ix_findings_org_project", "organization_id", "project_id"),
        Index("ix_findings_org_status", "organization_id", "review_status"),
        Index("ix_findings_dedup", "organization_id", "dedup_key"),
    )

    review_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    finding_type: Mapped[FindingType] = mapped_column(
        Enum(FindingType, native_enum=False, length=40), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[Classification] = mapped_column(
        Enum(Classification, native_enum=False, length=40), nullable=False
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    potential_value_minor: Mapped[int | None] = mapped_column(BigInteger)  # None = unavailable
    value_unavailable_reason: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str | None] = mapped_column(String(3))
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False, length=30),
        nullable=False,
        default=ReviewStatus.pending,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=10), nullable=False, default=RiskLevel.medium
    )
    evidence_score: Mapped[float | None] = mapped_column(Float)  # "evidence completeness" 0..1
    evidence_score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    calculation_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    missing_evidence: Mapped[list[str] | None] = mapped_column(JSONB)
    contradicting_summary: Mapped[str | None] = mapped_column(Text)
    # deterministic key preventing duplicate unresolved findings for the same evidence
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)

    review_run: Mapped[ReviewRun] = relationship(back_populates="findings")
    evidence: Mapped[list["FindingEvidence"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["ReviewDecision"]] = relationship(
        back_populates="finding", cascade="all, delete-orphan"
    )


class FindingEvidence(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "finding_evidence"
    __table_args__ = (Index("ix_finding_evidence_org_finding", "organization_id", "finding_id"),)

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # supporting|contradicting
    entity_type: Mapped[EvidenceType] = mapped_column(
        Enum(EvidenceType, native_enum=False, length=30), nullable=False
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    quotation: Mapped[str | None] = mapped_column(Text)
    document_page: Mapped[int | None] = mapped_column(Integer)
    section_reference: Mapped[str | None] = mapped_column(String(120))
    relevance_explanation: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500))

    finding: Mapped[Finding] = relationship(back_populates="evidence")


class ReviewDecision(Base, UUIDPrimaryKeyMixin, OrgScopedMixin):
    __tablename__ = "review_decisions"
    __table_args__ = (Index("ix_review_decisions_org_finding", "organization_id", "finding_id"),)

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    previous_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False, length=30), nullable=False
    )
    new_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, native_enum=False, length=30), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    finding: Mapped[Finding] = relationship(back_populates="decisions")


class GeneratedArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "generated_artifacts"
    __table_args__ = (Index("ix_generated_artifacts_org_finding", "organization_id", "finding_id"),)

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False
    )
    artifact_type: Mapped[ArtifactType] = mapped_column(
        Enum(ArtifactType, native_enum=False, length=40), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by_model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(50))
    approved_by_user: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
