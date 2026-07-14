# ScopeGuard Architecture

## Components

```
┌─────────────┐     first-party cookies      ┌──────────────────────────┐
│  Next.js    │ ───────────────────────────► │  FastAPI (apps/api)      │
│  web (3000) │   /api/* proxied to api      │  routers → services → DB │
└─────────────┘                              └───────────┬──────────────┘
                                                          │
        ┌───────────────┬─────────────────┬──────────────┼───────────────┐
        ▼               ▼                 ▼               ▼               ▼
  PostgreSQL 16    Redis (broker      MinIO (file    Ollama (local   Mailpit
  + pgvector       + result backend)  bytes)         LLM, optional)  (test SMTP)
        ▲               ▲
        └───────┬───────┘
                │ same image, celery entrypoint
        ┌───────┴────────┐
        │ Celery worker  │  document extraction, embeddings, contract
        │ (apps/worker)  │  extraction, review execution, artifacts
        └────────────────┘
```

`apps/worker` is the **same Python package** as `apps/api` run under a Celery
entrypoint (see [ADR-0009](adr/0009-worker-shares-api-codebase.md)).

## Data flow: a billing review

1. A user uploads contract PDFs/DOCX → bytes to MinIO, metadata to Postgres, a
   Celery task extracts text (PyMuPDF / python-docx), preserving page numbers.
2. The user creates a Contract referencing the governing document and triggers
   clause extraction. The worker chunks the text, asks the LLM for structured
   clauses, **verifies every quotation verbatim** against the source, stores accepted
   clauses (unverified), derives candidate rates/allowances, and embeds clauses into
   pgvector.
3. A human reviews and approves clauses (unverified clauses cannot drive
   high-confidence recommendations).
4. The user imports Jira work items, timesheets and invoices via CSV/XLSX (preview →
   validate per row → commit).
5. The user runs a review for a billing period. The [review engine](../apps/api/app/services/review/engine.py):
   resolves applicable contracts (temporal + precedence logic), gathers work items /
   time entries / customer requests / invoices, detects duplicates, reconciles against
   billed invoices, groups evidence, asks the LLM to classify each group with
   source-grounded output, **validates every returned citation**, performs
   deterministic financial calculations, scores evidence completeness, and creates
   Findings — each `pending` human review.
6. A human decides each finding (reason required). After approval, they may generate
   draft artifacts and export a PDF/JSON/CSV report.

## The deterministic ↔ LLM boundary

| Deterministic application code (never the LLM) | LLM (Ollama or fake) |
|-----------------------------------------------|----------------------|
| All money math (`services/review/money.py`) | Clause extraction candidates |
| Duplicate detection (`duplicates.py`) | Scope classification |
| Contract precedence, effective dates, rate resolution (`temporal.py`) | Artifact drafting |
| Allowance consumption (`allowances.py`) | (nothing else) |
| Invoice reconciliation (`reconciliation.py`) | |
| Evidence scoring (`evidence.py`) | |
| Citation verification (`citations.py`) | |

Every LLM output is validated against a Pydantic schema with retry-and-repair, and
every quotation/ID it returns is checked against the exact evidence supplied. A
fabricated quotation or unknown ID is dropped; if all clause citations fail, the
finding is downgraded to *insufficient information*.

## Security boundaries

- **Tenant isolation**: every org-owned row carries `organization_id`; every query
  filters on it, and cross-tenant object access returns 404. Vector retrieval filters
  by organization *before* similarity ordering.
- **Auth**: Argon2id hashing, server-side sessions (only the SHA-256 of the cookie
  token is stored), CSRF double-submit, account lockout, rate limiting.
- **Uploads**: MIME + extension allowlist, magic-byte check, size limit, random
  storage keys, filename sanitisation.
- **Untrusted data**: uploaded documents and ticket content are treated as data;
  prompts tell the model that embedded instructions are never commands.

## Storage strategy

File **bytes** live in MinIO under random per-org keys; **metadata** (filename, sha256,
type, extraction status/text) lives in Postgres. Embeddings live in a pgvector column
with an HNSW cosine index.

## Multi-tenancy strategy

Single database, shared schema, row-level `organization_id` scoping enforced in the
service/dependency layer (`get_org_object`, org-filtered queries). See
[ADR-0008](adr/0008-tenant-isolation-strategy.md).
