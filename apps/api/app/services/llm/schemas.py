"""Pydantic schemas for structured LLM output. All model output is validated
against these; malformed output is retried and then rejected."""

from pydantic import BaseModel, Field

from app.models.enums import Classification


class ExtractedClauseOut(BaseModel):
    clause_type: str
    title: str = Field(max_length=255)
    source_quotation: str = Field(
        description="EXACT quotation from the document; verified verbatim against the source"
    )
    normalized_interpretation: str | None = None
    page_number: int | None = None
    section_reference: str | None = None
    effective_from: str | None = Field(None, description="ISO date if stated")
    effective_to: str | None = None
    confidence: float = Field(ge=0, le=1)
    # for hourly_rate clauses
    role_name: str | None = None
    hourly_rate: float | None = None
    currency: str | None = None
    # for allowance clauses
    included_quantity: float | None = None
    unit: str | None = None
    recurrence: str | None = None


class ContractExtractionOut(BaseModel):
    clauses: list[ExtractedClauseOut]
    notes: str | None = None


class EvidenceRef(BaseModel):
    entity_type: str
    entity_id: str
    quotation: str
    reason: str


class ScopeClassificationOut(BaseModel):
    classification: Classification
    confidence: float = Field(ge=0, le=1)
    summary: str
    applicable_clause_ids: list[str] = []
    supporting_evidence: list[EvidenceRef] = []
    contradicting_evidence: list[EvidenceRef] = []
    missing_evidence: list[str] = []
    requires_customer_authorization: bool = False
    recommended_review_action: str = ""


class ArtifactDraftOut(BaseModel):
    content: str
