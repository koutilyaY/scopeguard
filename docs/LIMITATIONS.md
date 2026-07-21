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
- **The web API URL is baked at image-build time, not runtime.** Next.js resolves
  `next.config.mjs` `rewrites()` during `next build` and freezes the destination into
  `routes-manifest.json`, so setting `API_INTERNAL_URL` as a *runtime* env var has no
  effect on the built image. The Dockerfile therefore accepts it as a build arg
  (default `http://api:8000`, matching the compose service name). Pointing the web app
  at a different API host requires a rebuild:
  `docker build --build-arg API_INTERNAL_URL=https://api.example.com -f apps/web/Dockerfile .`
  A runtime-configurable proxy (e.g. Next middleware) would remove this constraint but
  is not implemented in the MVP.
- **Docker-only failure modes exist that host/dev-mode testing will not catch.** The
  audit found two (build-time-baked proxy URL; a healthcheck binary absent from the
  runtime image). Always validate changes against `docker compose up`, not just
  `make dev`.
- **Ollama is required for scope classification** — it is not optional. With the shipped
  `LLM_PROVIDER=ollama` and no reachable Ollama, reviews complete but are marked
  `completed_with_errors` and classify nothing; only deterministic findings
  (duplicates, allowances, reconciliation) are produced. Use `LLM_PROVIDER=fake` for a
  no-AI demo, or start Ollama with `--profile ai` and pull the configured models. The
  `ollama` service is behind a compose profile, so a plain `docker compose up` does
  **not** start it.
- **A database-less test run is refused, by design.** Roughly a third of the suite is
  DB-backed; silently skipping it produced a green run that proved almost nothing. The
  suite now fails loudly instead. Override with `SCOPEGUARD_ALLOW_DB_SKIP=1` only if you
  deliberately want unit-only coverage and accept the skips.
- **Chat-model size vs. the default timeout (measured).** `OLLAMA_TIMEOUT_SECONDS`
  defaults to 120. On a CPU-only machine under load, that is enough for a small model
  but not a large one. Measured on an Apple-silicon laptop running several other Docker
  stacks, using the real scope-classification prompt:
  | Model | Size | Result |
  |-------|------|--------|
  | `llama3.2:latest` | 2.0 GB | classification returned in **82 s** — inside the default |
  | `qwen3.5:latest` | 6.6 GB | **exceeded 120 s**, retried 3×, group left unclassified |
  If groups fail with "Ollama unreachable or failing … timed out", either pick a smaller
  `OLLAMA_CHAT_MODEL` or raise `OLLAMA_TIMEOUT_SECONDS`. Note the retry math: 3 attempts
  per group, so an over-long timeout makes failures slow to surface.
- **A worker restart mid-run leaves the review stuck in `running`.** There is no reaper
  for orphaned runs: if the Celery worker is killed or crashes while a review is
  executing, that `ReviewRun` keeps `status='running'` indefinitely and the UI polls it
  forever. Recover manually with
  `UPDATE review_runs SET status='failed', failure_reason='…' WHERE status='running';`
  A stale-run reaper (e.g. fail runs whose `started_at` exceeds a deadline) is not
  implemented in the MVP.
- **Host ports must not collide with other local projects.** ScopeGuard's infra ports are
  now configurable (`POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `MINIO_HOST_PORT`,
  `MINIO_CONSOLE_HOST_PORT`, `MAILPIT_HOST_PORT`, `MAILPIT_SMTP_HOST_PORT`,
  `OLLAMA_HOST_PORT`, plus `API_PORT`/`WEB_PORT`). If another container already owns a
  default port, you may connect to *that* service and see confusing auth errors — change
  the port rather than debugging the wrong database.
