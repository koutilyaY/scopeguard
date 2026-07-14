# ScopeGuard Data Model

All monetary values are integer **minor units** (cents). Time is stored in whole
**minutes**. Every org-owned table has a non-null `organization_id`.

## Entities and relationships

```
Organization 1──* User
Organization 1──* Client 1──* Project
Project 1──* Document        (also client-level)
Client/Project 1──* Contract 1──* ContractClause 1──* ClauseEmbedding (pgvector)
Contract 1──* RateRule
Contract 1──* Allowance
Project 1──* WorkItem 1──* TimeEntry
Project 1──* CustomerRequest  (→ Document, → WorkItem)
Project 1──* Invoice 1──* InvoiceLine
Project 1──* ReviewRun 1──* Finding 1──* FindingEvidence
                                   Finding 1──* ReviewDecision
                                   Finding 1──* GeneratedArtifact
Organization 1──* AuditEvent
```

## Key tables

| Table | Purpose | Notable columns / constraints |
|-------|---------|-------------------------------|
| `organizations` | Tenant | `slug` unique; `retention_days` |
| `users` | Auth principal | `email` unique, Argon2id `hashed_password`, `role`, lockout fields |
| `auth_sessions` | Server-side sessions | `token_hash` (SHA-256) unique, `csrf_token`, `expires_at` |
| `clients` / `projects` | Engagements | org-scoped; project has `currency` |
| `documents` | Uploaded files | `sha256` (dup detection), `storage_key` (random), `extraction_status` |
| `contracts` | Agreements | `effective_from/to`, `status`, `governing_document_id`, verification |
| `contract_clauses` | Extracted terms | `source_text` (verbatim quote), `page_number`, `confidence`, `human_verified`, `rejected`, `superseded_by_clause_id`; `CHECK confidence 0..1` |
| `clause_embeddings` | Retrieval vectors | `Vector(768)`, HNSW cosine index |
| `rate_rules` | Hourly rates | `hourly_rate_minor` (`CHECK >= 0`), effective dates, `human_verified` |
| `allowances` | Support/impl pools | `included_quantity` minutes, `recurrence` |
| `work_items` | Jira tickets | unique `(org, external_system, external_id)`, `content_hash` |
| `time_entries` | Timesheets | `minutes` (`CHECK > 0`), `content_hash` for dup detection |
| `customer_requests` | Emails/asks | `customer_authorization_status` |
| `invoices` / `invoice_lines` | Existing invoices | `*_minor` totals; unique `(org, invoice_number)` |
| `review_runs` | Review executions | period, `status`, `model_name`, `prompt_version`, `stats` |
| `findings` | Results | `finding_type`, `classification`, `confidence`, `potential_value_minor` (nullable), `evidence_score`, `calculation_breakdown` (JSONB), `dedup_key` |
| `finding_evidence` | Citations | `evidence_type` (supporting/contradicting), `quotation`, page/section |
| `review_decisions` | Human decisions | `previous_status`, `new_status`, `reason` (required) |
| `generated_artifacts` | Drafts | `artifact_type`, `content`, `approved_by_user`, `prompt_version` |
| `audit_events` | Append-only trail | `action`, `entity_type/id`, before/after (redacted), `request_id` |

## Indexes
Organization-scoping indexes on every org-owned table; effective-date indexes on
contracts, clauses, rate rules; `(org, sha256)` for document dedup; `(org, content_hash)`
for time-entry dedup; `(org, dedup_key)` for finding dedup; HNSW vector index on
embeddings.

Enumerations are stored as `VARCHAR` with application-level `StrEnum` validation
(`native_enum=False`) so adding a value never requires an `ALTER TYPE`.
