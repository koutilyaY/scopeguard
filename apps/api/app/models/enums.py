"""Domain enumerations. Stored as VARCHAR with check constraints (native_enum=False)."""

from enum import StrEnum


class UserRole(StrEnum):
    organization_admin = "organization_admin"
    finance_manager = "finance_manager"
    project_manager = "project_manager"
    reviewer = "reviewer"
    read_only = "read_only"


class ClientStatus(StrEnum):
    active = "active"
    inactive = "inactive"
    archived = "archived"


class ProjectStatus(StrEnum):
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    archived = "archived"


class DocumentType(StrEnum):
    master_service_agreement = "master_service_agreement"
    statement_of_work = "statement_of_work"
    amendment = "amendment"
    change_order = "change_order"
    rate_card = "rate_card"
    customer_request = "customer_request"
    invoice = "invoice"
    other = "other"


class ExtractionStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    unreadable = "unreadable"  # no machine-readable text (e.g. scanned PDF; OCR not enabled)


class ContractStatus(StrEnum):
    draft = "draft"
    active = "active"
    expired = "expired"
    terminated = "terminated"


class ClauseType(StrEnum):
    included_service = "included_service"
    excluded_service = "excluded_service"
    deliverable = "deliverable"
    support_allowance = "support_allowance"
    hourly_rate = "hourly_rate"
    fixed_fee = "fixed_fee"
    approval_requirement = "approval_requirement"
    change_control = "change_control"
    expense_rule = "expense_rule"
    payment_term = "payment_term"
    other = "other"


class AllowanceType(StrEnum):
    support_hours = "support_hours"
    implementation_hours = "implementation_hours"
    other = "other"


class AllowanceRecurrence(StrEnum):
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    total = "total"  # one pool for the whole engagement


class WorkItemStatus(StrEnum):
    open = "open"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class BillableStatus(StrEnum):
    billable = "billable"
    non_billable = "non_billable"
    unknown = "unknown"


class AuthorizationStatus(StrEnum):
    none = "none"
    verbal_claimed = "verbal_claimed"
    written = "written"
    disputed = "disputed"


class InvoiceStatus(StrEnum):
    draft = "draft"
    approved_draft = "approved_draft"
    issued = "issued"
    paid = "paid"
    void = "void"


class ReviewRunStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"


class FindingType(StrEnum):
    potentially_out_of_scope = "potentially_out_of_scope"
    exhausted_allowance = "exhausted_allowance"
    unbilled_time = "unbilled_time"
    rate_mismatch = "rate_mismatch"
    possible_duplicate = "possible_duplicate"
    already_invoiced = "already_invoiced"
    missing_customer_authorization = "missing_customer_authorization"
    insufficient_evidence = "insufficient_evidence"
    contract_ambiguity = "contract_ambiguity"


class Classification(StrEnum):
    in_scope = "in_scope"
    potentially_out_of_scope = "potentially_out_of_scope"
    clearly_out_of_scope = "clearly_out_of_scope"
    insufficient_information = "insufficient_information"


class ReviewStatus(StrEnum):
    pending = "pending"
    approved_for_followup = "approved_for_followup"
    approved_for_billing = "approved_for_billing"
    rejected = "rejected"
    needs_more_evidence = "needs_more_evidence"
    already_resolved = "already_resolved"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidenceType(StrEnum):
    contract_clause = "contract_clause"
    work_item = "work_item"
    time_entry = "time_entry"
    customer_request = "customer_request"
    invoice = "invoice"
    invoice_line = "invoice_line"
    document = "document"
    calculation = "calculation"


class ArtifactType(StrEnum):
    internal_review_summary = "internal_review_summary"
    change_order_draft = "change_order_draft"
    invoice_narrative = "invoice_narrative"
    clarification_email = "clarification_email"
    evidence_report = "evidence_report"
