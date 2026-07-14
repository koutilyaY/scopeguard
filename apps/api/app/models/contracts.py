"""Contract, ContractClause, clause embeddings, RateRule, Allowance."""

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AllowanceRecurrence, AllowanceType, ClauseType, ContractStatus

# Embedding dimension is fixed at migration time; changing the embedding model to one
# with a different dimension requires a new migration (documented in docs/LIMITATIONS.md).
EMBEDDING_DIM = 768


class Contract(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "contracts"
    __table_args__ = (
        Index("ix_contracts_org_client", "organization_id", "client_id"),
        Index("ix_contracts_effective", "effective_from", "effective_to"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    contract_number: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, native_enum=False, length=20),
        nullable=False,
        default=ContractStatus.draft,
    )
    governing_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    verified_by_user: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column()

    clauses: Mapped[list["ContractClause"]] = relationship(back_populates="contract")


class ContractClause(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "contract_clauses"
    __table_args__ = (
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_clause_confidence"),
        Index("ix_clauses_org_contract", "organization_id", "contract_id"),
        Index("ix_clauses_effective", "effective_from", "effective_to"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    clause_type: Mapped[ClauseType] = mapped_column(
        Enum(ClauseType, native_enum=False, length=40), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_interpretation: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_reference: Mapped[str | None] = mapped_column(String(120))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    confidence: Mapped[float | None] = mapped_column(Float)
    human_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    rejected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    superseded_by_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_clauses.id", ondelete="SET NULL")
    )

    contract: Mapped[Contract] = relationship(back_populates="clauses")


class ClauseEmbedding(Base, UUIDPrimaryKeyMixin, OrgScopedMixin):
    """Vector for one contract clause / document chunk, used for retrieval."""

    __tablename__ = "clause_embeddings"
    __table_args__ = (Index("ix_clause_embeddings_org", "organization_id"),)

    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_clauses.id", ondelete="CASCADE"), index=True
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_reference: Mapped[str | None] = mapped_column(String(120))
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)


class RateRule(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "rate_rules"
    __table_args__ = (
        CheckConstraint("hourly_rate_minor >= 0", name="ck_rate_nonnegative"),
        Index("ix_rate_rules_org_contract", "organization_id", "contract_id"),
        Index("ix_rate_rules_effective", "effective_from", "effective_to"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    service_category: Mapped[str | None] = mapped_column(String(100))
    hourly_rate_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_clauses.id", ondelete="SET NULL")
    )
    human_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Allowance(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "allowances"
    __table_args__ = (
        CheckConstraint("included_quantity >= 0", name="ck_allowance_nonnegative"),
        Index("ix_allowances_org_contract", "organization_id", "contract_id"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    allowance_type: Mapped[AllowanceType] = mapped_column(
        Enum(AllowanceType, native_enum=False, length=40), nullable=False
    )
    included_quantity: Mapped[int] = mapped_column(Integer, nullable=False)  # minutes or units
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="minutes")
    recurrence: Mapped[AllowanceRecurrence] = mapped_column(
        Enum(AllowanceRecurrence, native_enum=False, length=20), nullable=False
    )
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_clauses.id", ondelete="SET NULL")
    )
