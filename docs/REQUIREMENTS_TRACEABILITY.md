# ScopeGuard — Requirements Traceability Matrix

Audit date: 2026-07-14. Method: inspection of the real implementation plus execution
of every available automated check (lint, type, unit, integration, security, frontend,
e2e, evaluation, migration, seed, build, Docker startup). Findings were reproduced
before fixing; fixes carry regression tests. Legend — **Implemented**: Yes / Partial /
No. **Automated test**: file::test or suite. **Manually verified**: how it was
exercised by hand during this audit.

Ports used in manual checks: API `:18000` (container) / `:8010` (host), web `:3000`,
Postgres `:5433`, MinIO `:9002` — chosen to avoid a conflicting unrelated container on
`:8000`.

## A. Mandatory acceptance criteria (spec §"MANDATORY ACCEPTANCE CRITERIA")

| # | Requirement | Implemented | Source files | Automated test | Manually verified | Defect | Required correction |
|---|-------------|-------------|--------------|----------------|-------------------|--------|---------------------|
| 1 | `docker compose up --build` starts required services | Yes | `docker-compose.yml`, `apps/api/Dockerfile`, `apps/web/Dockerfile` | CI `docker-build` job | `docker compose up -d` → all 7 services healthy; `/health/ready` all true | None | — |
| 2 | A user can log in | Yes | `app/routers/auth.py`, `app/security/{passwords,sessions}.py` | `test_auth_flow.py` (12) | Browser login as admin → dashboard | None | — |
| 3 | Seeded demonstration data available | Yes | `app/seed.py` | `test_review_pipeline.py::seeded` | `python -m app.seed` on fresh DB → Northstar org | None | — |
| 4 | Contract can be uploaded and extracted | Yes | `routers/documents.py`, `services/{extraction,contract_extraction}.py` | `test_imports_and_exports.py::test_document_upload_extracts_text_via_worker`, `test_fake_provider.py` | Uploaded txt → extraction completed via worker | None | — |
| 5 | Extracted clauses can be verified by a human | Yes | `routers/clauses.py`, `app/(app)/contracts/[id]/page.tsx` | `test_fake_provider.py` (extraction), clause approve/reject routes exercised in `test_imports_and_exports` flow | Contract review page renders clauses w/ approve/reject | None | — |
| 6 | Work items importable via CSV | Yes | `routers/imports.py`, `services/imports.py` | `test_imports_validation.py` (15) | Preview/commit path in ImportsTab | None | — |
| 7 | Timesheets importable via CSV/XLSX | Yes | `services/imports.py` | `test_imports_and_exports.py::test_timesheet_{preview,commit}` | Preview reports row errors; commit creates valid rows only | None | — |
| 8 | Invoices importable or manually entered | Yes | `routers/invoices.py`, `services/imports.py` | `test_imports_validation.py`, `test_review_pipeline` (seeded invoice) | Seed creates fixed-fee invoice; reconciliation uses it | None | — |
| 9 | A billing-period review can be run | Yes | `routers/review_runs.py`, `services/review/engine.py` | `test_review_pipeline.py::test_review_run_completes` | Ran June review via API + UI Reviews tab | None | — |
| 10 | Finding contains traceable contract + operational evidence | Yes | `engine.py`, `services/citations.py` | `test_review_pipeline.py::test_evidence_cites_clause_workitem_and_request` | Finding detail shows clause quote + Jira + request | None | — |
| 11 | Duplicate time entries not double-counted | Yes | `services/review/duplicates.py`, `engine.py` | `test_duplicates.py` (7), `test_review_pipeline.py::test_duplicate_excluded_from_value` | 7 rows → 6 valued; $6,080 | None | — |
| 12 | Effective dates and amendments respected | Yes | `services/review/temporal.py` | `test_temporal.py` (18) | Split-rate 21h@175 + 13h@185 in calc breakdown | None | — |
| 13 | Financial calculations use deterministic code | Yes | `services/review/money.py`, `engine.py` | `test_money.py` (11), `evaluations` financial 100% | Eval financial accuracy 100% (11/11) | None | — |
| 14 | Missing rates do not produce invented values | Yes | `money.py`, `engine.py` (value_unavailable_reason) | `evaluations` case `fin_missing_rate`, `test_temporal::test_unknown_role_returns_none` | Calc UI shows "value unavailable" | None | — |
| 15 | Existing invoices reconciled | Yes | `services/review/reconciliation.py` | `evaluations` cases `fin_reconciliation_billed/void` | BILLED={issued,paid,approved_draft}; void excluded | None | — |
| 16 | Human approval required before external-facing drafts | Yes | `routers/artifacts.py`, `services/artifacts.py` | `test_imports_and_exports.py::test_artifact_generation_requires_approval` | Pre-approval generate → 409; UI hides button until approved | None | — |
| 17 | No email is automatically sent | Yes | `services/artifacts.py` (drafts only; no SMTP send path) | grep: no send/SMTP call in app code | Clarification email is a draft artifact only | None | — |
| 18 | No invoice is automatically created | Yes | `routers/invoices.py` (manual/import only) | `test_review_pipeline` (review creates findings, never invoices) | Review run creates findings only | None | — |
| 19 | Cross-tenant access tests pass | Yes | `deps.py::get_org_object`, org-scoped queries | `test_tenant_isolation.py` (5) | Second org sees 0 of org A's rows | None | — |
| 20 | Unit, integration, frontend, e2e tests pass | Yes | `apps/api/tests`, `apps/web` | 140 backend + 13 frontend + 5 e2e | All green this audit | **Fixed**: flaky e2e "approve→generate" | Deterministic targeting + state waits (`e2e/demo-workflow.spec.ts`) |
| 21 | Deterministic evaluation suite passes | Yes | `apps/api/evaluations/` | `python -m evaluations.run --provider fake` → PASS | Financial 100%, citation 100% | None | — |
| 22 | README setup tested from clean env | Yes | `README.md`, `Makefile` | migration-from-empty + seed rerun this audit | Fresh DB migrate→seed→review reproduced | None | — |
| 23 | No placeholder buttons / fake APIs / TODO in critical flows | Yes | whole tree | grep sweeps (0 TODO/FIXME/NotImplemented/mock) | Manual UI walk of login→review→decision→artifact→export | None | — |
| 24 | Known limitations documented honestly | Yes | `docs/LIMITATIONS.md` | — | Reviewed & updated this audit | None | — |
| 25 | Final report includes actual command output | Yes | `docs/FINAL_VERIFICATION.md` | — | Updated with this run's real output | None | — |

## B. Audit priority areas (1–15)

| # | Priority area | Implemented | Source files | Automated test | Manually verified | Defect found | Correction |
|---|---------------|-------------|--------------|----------------|-------------------|--------------|------------|
| 1 | Authentication & tenant isolation | Yes | `security/{passwords,sessions,csrf,rate_limit}.py`, `deps.py` | `test_auth_flow` (12), `test_tenant_isolation` (5), `test_rbac_and_uploads` (10) | Argon2id verified in hash prefix; session stored as SHA-256; cross-tenant 404 | None | — |
| 2 | Contract upload & extraction | Yes | `services/{files,extraction,contract_extraction}.py`, `routers/documents.py` | `test_files_citations` (19), `test_fake_provider` (11) | Upload → MinIO + worker extraction | None | — |
| 3 | Clause verification | Yes | `routers/clauses.py`, contract review UI | clause approve/reject exercised; `test_fake_provider` extraction | Unverified clauses cap confidence (`engine.py`) | None | — |
| 4 | Work & timesheet imports | Yes | `services/imports.py`, `routers/imports.py` | `test_imports_validation` (15), `test_imports_and_exports` | Row errors surfaced; duplicates skipped | None | — |
| 5 | Deterministic duplicate removal | Yes | `services/review/duplicates.py` | `test_duplicates` (7) | 1 duplicate excluded, not double-counted | None | — |
| 6 | Contract effective-date & precedence | Yes | `services/review/temporal.py` | `test_temporal` (18) | Rate change mid-period, superseded clause, project-scoped amendment | None | — |
| 7 | Rate & allowance calculations | Yes | `services/review/{allowances,money}.py`, `temporal.py::resolve_rate` | `test_allowances_evidence` (11), `test_money` (11) | Only excess over allowance billable | None | — |
| 8 | Invoice reconciliation | Yes | `services/review/reconciliation.py` | eval `fin_reconciliation_*` | Void not billed; approved_draft billed | None | — |
| 9 | Evidence-grounded review findings | Yes | `services/review/engine.py`, `citations.py` | `test_review_pipeline` (9), `test_llm_safety` (4) | Fabricated citations dropped; $6,080 finding | **CRITICAL: re-run after approval created a duplicate finding, double-counting value ($12,160)** | Expanded `OCCUPYING_STATUSES` to include approved_for_followup/billing (`engine.py`); regression test `test_rerun_after_approval_does_not_duplicate_finding` |
| 10 | Human review decisions | Yes | `routers/decisions.py`, DecisionForm | `test_imports_and_exports::test_decision_requires_reason` | Reason required (min 5); status transitions enforced | None | — |
| 11 | Artifact generation | Yes | `services/artifacts.py`, `routers/artifacts.py` | `test_artifact_generation_requires_approval` | Post-approval generate → DRAFT summary in UI | None | — |
| 12 | Audit logging | Yes | `services/audit.py`, `logging.py` | audit events asserted in `test_auth_flow`, `test_tenant_isolation` | before/after redacted; login events logged | None | — |
| 13 | Exports (CSV/JSON/PDF) | Yes | `services/exports.py`, `routers/reports.py` | `test_imports_and_exports::test_exports_include_evidence_and_disclaimer` | 4-page PDF w/ supporting+contradicting evidence + disclaimer | None | — |
| 14 | End-to-end tests | Yes | `apps/web/e2e/demo-workflow.spec.ts` | 5 Playwright tests | Full login→review→approve→artifact→export→audit | **Flaky approve→generate test** | Deterministic finding targeting + explicit approval-persisted waits |
| 15 | Documentation accuracy | Yes | `README.md`, `docs/*` | — | Cross-checked commands & claims against real behavior | Minor: prettier/format gate not previously run | Ran `prettier --write` (17 files) + `ruff format`; docs updated |

## C. Static-audit sweep results

| Check | Result |
|-------|--------|
| `grep TODO/FIXME/XXX/HACK` (app + src) | 0 |
| `grep not-implemented / NotImplementedError / stub / dummy` | 0 (only citation-verification comments matched "fabricat") |
| `grep mock` in app/src | 0 |
| `grep placeholder` | only legitimate HTML input `placeholder` attrs |
| Hardcoded-secret scan | 0 |
| Dead buttons (`onClick={()=>{}}`, `href="#"`) | 0 |
| Fake router returns (`return []/{}` sentinels) | 0 |
| Bare `pass` in app code | 3, all legitimate (2 empty exception subclasses, 1 JSON-parse fallthrough) |
| Disabled/only-focused tests | 0 (only environment-conditional skips: `requires_db`, pg-tools-absent backup test) |
| Health endpoint fabricates status? | No — real DB/Redis/MinIO/Celery/Ollama probes |

## D. Defects found and corrected in this audit

1. **Double-counting of potential value (CRITICAL, correctness).** Re-running a review
   after a finding was approved for follow-up created a second finding for the same
   evidence, because dedup only treated `pending`/`needs_more_evidence` as occupying.
   The dashboard's potential bucket includes `approved_for_followup`, so the same
   $6,080 was counted twice ($12,160). Fixed in `services/review/engine.py`
   (`OCCUPYING_STATUSES` now includes `approved_for_followup` and `approved_for_billing`;
   only `rejected`/`already_resolved` free the evidence). Regression test added.
   Verified: unit test, host end-to-end, and fully containerized stack all now show a
   single finding and $6,080 after approve + re-run.
2. **Flaky E2E test** (`approve a finding, generate a summary…`). Non-deterministic
   finding selection and no wait for the approval to persist. Rewritten to filter to the
   out-of-scope finding and wait on the "approved for followup" status before generating.
   Passes deterministically across repeated runs.
3. **Accessibility: unlabeled filter selects.** Finding-inbox `FilterSelect` had a
   `<label>` not associated with its `<select>`. Added `htmlFor`/`id`/`aria-label`.
4. **Formatting gate not applied.** 17 frontend files and 1 backend test file failed
   `prettier --check` / `ruff format --check`. Formatted; both gates now clean.

No mandatory acceptance criterion remains unsupported by working code and a test or a
documented manual verification.
