// Shared API response types, kept in sync with the FastAPI Pydantic models.

export type Role =
  "organization_admin" | "finance_manager" | "project_manager" | "reviewer" | "read_only";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  organization_id: string;
  must_change_password: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Client {
  id: string;
  legal_name: string;
  display_name: string;
  external_reference: string | null;
  status: string;
}

export interface Project {
  id: string;
  client_id: string;
  name: string;
  external_reference: string | null;
  description: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  currency: string;
}

export interface Document {
  id: string;
  client_id: string | null;
  project_id: string | null;
  document_type: string;
  original_filename: string;
  sha256: string;
  mime_type: string;
  file_size: number;
  extraction_status: string;
  extraction_error: string | null;
  created_at: string;
  superseded_by_document_id: string | null;
}

export interface Contract {
  id: string;
  client_id: string;
  project_id: string | null;
  contract_number: string | null;
  title: string;
  effective_from: string | null;
  effective_to: string | null;
  currency: string;
  status: string;
  governing_document_id: string | null;
  verified_by_user: string | null;
  verified_at: string | null;
}

export interface Clause {
  id: string;
  contract_id: string;
  clause_type: string;
  title: string;
  source_text: string;
  normalized_interpretation: string | null;
  page_number: number | null;
  section_reference: string | null;
  effective_from: string | null;
  effective_to: string | null;
  confidence: number | null;
  human_verified: boolean;
  rejected: boolean;
  superseded_by_clause_id: string | null;
}

export interface Finding {
  id: string;
  review_run_id: string;
  project_id: string;
  finding_type: string;
  title: string;
  explanation: string;
  classification: string;
  confidence: number | null;
  potential_value_minor: number | null;
  value_unavailable_reason: string | null;
  currency: string | null;
  review_status: string;
  risk_level: string;
  evidence_score: number | null;
  created_at: string;
  updated_at: string;
}

export interface Evidence {
  id: string;
  evidence_type: string;
  entity_type: string;
  entity_id: string | null;
  quotation: string | null;
  document_page: number | null;
  section_reference: string | null;
  relevance_explanation: string | null;
  entity_summary: Record<string, unknown> | null;
}

export interface Decision {
  id: string;
  reviewer_id: string | null;
  previous_status: string;
  new_status: string;
  reason: string;
  created_at: string;
}

export interface FindingDetail extends Finding {
  evidence_score_breakdown: Record<string, unknown> | null;
  calculation_breakdown: Record<string, unknown> | null;
  missing_evidence: string[] | null;
  contradicting_summary: string | null;
  evidence: Evidence[];
  decisions: Decision[];
  artifacts: {
    id: string;
    artifact_type: string;
    created_at: string;
    approved_by_user: string | null;
  }[];
  disclaimer: string;
}

export interface ReviewRun {
  id: string;
  project_id: string;
  billing_period_start: string;
  billing_period_end: string;
  status: string;
  model_name: string | null;
  prompt_version: string | null;
  started_at: string | null;
  completed_at: string | null;
  failure_reason: string | null;
  stats: Record<string, number> | null;
  created_at: string;
}

export interface ValueByCurrency {
  currency: string;
  amount_minor: number;
}

export interface Dashboard {
  pending_review_count: number;
  potential_value: ValueByCurrency[];
  approved_for_billing_value: ValueByCurrency[];
  invoiced_value: ValueByCurrency[];
  rejected_value: ValueByCurrency[];
  findings_by_type: Record<string, number>;
  findings_by_client: Record<string, number>;
  findings_by_project: Record<string, number>;
  recent_review_runs: Array<Record<string, unknown>>;
  allowances_nearing_exhaustion: Array<{
    allowance_id: string;
    allowance_type: string;
    included_minutes: number;
    consumed_minutes_this_period: number;
    remaining_minutes: number;
    period_label: string;
  }>;
  value_disclaimer: string;
}

export interface AuditEvent {
  id: string;
  actor_user_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  created_at: string;
}

export interface ImportPreview {
  import_type: string;
  supported_fields: string[];
  columns: string[];
  suggested_mapping: Record<string, string>;
  sample_rows: Array<Record<string, string>>;
  total_rows: number;
  valid_rows: number;
  errors: Array<{ row: number; field: string; message: string }>;
  warnings: Array<{ row: number; field: string; message: string }>;
}
