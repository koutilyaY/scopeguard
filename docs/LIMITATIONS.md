# ScopeGuard Known Limitations

ScopeGuard is an evidence-gathering, decision-support MVP. It is deliberately narrow.

## It does not
- **Give legal advice.** Findings never state legal conclusions; contract
  interpretation may be ambiguous and is flagged as such.
- **Give accounting advice.** Monetary figures are operational estimates for human
  review, not accounting determinations.
- **Automatically invoice.** No invoice is ever created by the system.
- **Automatically send email.** Clarification emails are drafts only; nothing is sent.
- **OCR scanned documents.** PDFs without machine-readable text are rejected with a
  clear message; content is never hallucinated from unreadable files.

## Not in the MVP
- Live Jira synchronization (CSV import + a connector interface only).
- Live QuickBooks/NetSuite/accounting integration (CSV import + interface only).
- Full Gmail/Outlook mailbox ingestion (uploaded `.eml`/`.txt`/PDF/DOCX or manual
  entry only).
- Slack ingestion, mobile/native apps, multiple UI languages, custom model training,
  Kubernetes, SOC 2 / HIPAA claims.

## Quality and operational caveats
- **Local model quality varies.** Classification and draft quality depend on the chosen
  Ollama model and hardware. The deterministic financial and duplicate logic is
  unaffected by model quality.
- **Unverified clauses are weak evidence.** Clauses the model extracts but a human has
  not verified cannot drive high-confidence recommendations; confidence is capped.
- **Contract ambiguity is real.** Where clauses conflict or are unclear, ScopeGuard
  reports *contract ambiguity* / *insufficient information* rather than guessing.
- **Human verification is required** for every finding and before any external-facing
  draft is generated.
- **Embedding dimension is fixed** at migration time (768 by default). Switching to an
  embedding model with a different dimension requires a new Alembic migration and
  re-embedding existing clauses.
- **Single-server Compose is not production-grade.** It is suitable for evaluation and
  pilots, not for regulated or enterprise production without the hardening in
  docs/DEPLOYMENT.md and SECURITY.md.

## Explicitly deferred
Automatic invoice creation, automatic email sending, legal conclusions, OCR, live
integrations, mailbox-wide ingestion, and fully autonomous contract decisions are all
out of scope by design — not oversights.

## Audit notes and residual caveats (2026-07-14)

A full audit against the mandatory acceptance criteria was performed; results are in
[REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md). Honest residual caveats:

- **Finding dedup keys on the deterministic work-group signature, not on semantic
  equivalence.** Re-running a review no longer duplicates a finding that a human has
  approved for follow-up/billing (fixed this audit). However, if the underlying
  evidence *changes* such that the work-group key changes (e.g. new time entries land),
  a re-run may legitimately raise a new finding for the changed group; humans should
  review the group composition shown on each finding.
- **Rejected / already-resolved findings can re-appear on a later run.** By design, a
  terminal human decision frees the evidence, so if the same out-of-scope work is still
  present next period a fresh finding is raised. This is intentional (persistent issues
  should resurface) but means a rejection is per-run, not permanent suppression.
- **The host `pg_dump` restore smoke test skips when the host client version cannot dump
  the containerized Postgres 16 server.** The production backup path
  (`scripts/backup.sh`) runs `pg_dump` *inside* the container where versions match; that
  path was exercised manually (valid PGDMP dump produced).
- **Test isolation vs. the shared dev database.** The demo (`scopeguard`) database
  accumulates findings across manual review runs; this is expected operational state,
  not a defect. The automated suite uses a separate `scopeguard_test` database that is
  truncated between tests.
- **Local model quality still varies** (unchanged): deterministic financial/duplicate
  logic is unaffected, but classification/draft quality depends on the chosen Ollama
  model. All gating tests and evaluations run against the deterministic fake provider.
