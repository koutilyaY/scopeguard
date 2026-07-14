# ScopeGuard — Build Status

Living log of implementation progress. Updated as each phase completes.

## Environment (verified 2026-07-14)

| Tool | Version | Notes |
|------|---------|-------|
| Docker | 29.0.1 | Docker Desktop, Compose v2.40.3 |
| Node.js | 26.3.1 | npm 11.16.0 |
| Python | 3.12 (miniforge) | used for the API venv; 3.11/3.13 also present |
| Ollama | server 0.31.2 | local install available; NOT required for tests |
| GNU Make | 3.81 | macOS default |

Repository root: `~/scopeguard` (fresh git repo, branch `main`).
The neighbouring `~/supply_chain_project` repo is unrelated and untouched.

## Phase checklist

- [x] **Phase 0 — Repository analysis and plan** (this file, structure, risks)
- [x] **Phase 1 — Infrastructure**: docker-compose (postgres+pgvector, redis, minio, mailpit, ollama), health checks, env config — infra containers verified healthy
- [x] **Phase 2 — Backend foundation**: FastAPI, config, JSON logging, SQLAlchemy 2, Alembic (up/down/up verified), Argon2id auth + sessions + CSRF, RBAC, org isolation, audit framework
- [x] **Phase 3 — Domain and imports**: all models, CRUD routers, document upload→MinIO + extraction, CSV/XLSX imports with preview, validation, demo fixtures (Northstar seed)
- [x] **Phase 4 — Local AI and retrieval**: Ollama provider + deterministic fake, embeddings, pgvector retrieval (tenant-filtered), contract extraction, clause verification, prompt versioning, citation validation
- [x] **Phase 5 — Review engine**: contract resolution, grouping, duplicate detection, allowances, rate resolution, invoice reconciliation, classification, evidence scoring, findings — demo produces the $6,080 finding
- [x] **Phase 6 — Frontend**: auth, dashboard, clients, projects, project detail (docs/contracts/imports/reviews tabs), contract review, finding inbox/detail, decisions, artifacts, reports, audit log, settings — Next.js build clean, 13 vitest pass
- [x] **Phase 7 — Artifacts and exports**: summaries, change-order drafts, narratives, clarification emails, CSV/JSON/PDF exports — wired into finding detail UI
- [x] **Phase 8 — E2E and security**: Playwright (5 pass), tenant isolation ✅, RBAC + upload security ✅, prompt-injection + fabricated-evidence ✅, full Docker stack verified
- [x] **Phase 9 — Documentation and release**: README, ARCHITECTURE, DATA_MODEL, THREAT_MODEL, LLM_SAFETY, DEPLOYMENT, PILOT_GUIDE, LIMITATIONS, 9 ADRs, SECURITY.md, CONTRIBUTING.md, CI workflow, backup/restore scripts, FINAL_VERIFICATION.md

### Final verification (2026-07-14) — see docs/FINAL_VERIFICATION.md
- Backend: ruff clean · mypy clean · **139 pytest passed** · migration up/down/up from empty OK
- Evaluation (fake): **PASS** — financial 100%, citation validity 100%, classification 100%
- Frontend: eslint clean · tsc strict clean · **13 vitest passed** · production build OK
- E2E: **5 Playwright passed** · `docker compose up` → all services Healthy · containerized review → $6,080 finding
- Repo hygiene: 0 TODO/FIXME/not-implemented/mock, 0 hardcoded secrets

### Backend test status (2026-07-14)
- `pytest tests/` — **138 passed** (unit + integration + security)
- `ruff check` — clean · `mypy app` — clean
- `python -m evaluations.run --provider fake` — **PASS**: financial accuracy 100% (11/11),
  classification 100% (7/7), citation validity 100%, prompt-injection resisted

## Key technical decisions (see docs/adr/ for full records)

1. **Worker shares the API codebase.** `apps/worker` is the same Python package as
   `apps/api` run under a Celery entrypoint (separate container, same image). A
   separate package would duplicate every model and service. Recorded in ADR-0009.
2. **Money**: integer minor units everywhere; `Decimal` for intermediate math with
   explicit `ROUND_HALF_UP`.
3. **Sessions**: server-side session rows in Postgres referenced by an HttpOnly
   cookie; CSRF via double-submit token bound to the session.
4. **PDF generation**: `fpdf2` (LGPL, pure-python, free).
5. **Tests never call a live model** — `FakeLLMProvider` is deterministic.

## Risks identified in Phase 0

- **Ollama model availability**: user may not have `qwen3:8b` / `nomic-embed-text`
  pulled. Mitigated by a startup check endpoint that lists missing models and exact
  `ollama pull` commands; all tests and evals run against the fake provider.
- **Apple Silicon + Ollama in Docker** is CPU-only and slow. Compose supports both a
  containerised Ollama and pointing `OLLAMA_BASE_URL` at the host install.
- **Scope size**: the spec is very large. Priority order: correctness of deterministic
  billing logic and tenant isolation first, breadth of UI second.

## Progress log

- 2026-07-14: Phase 0 complete — environment verified, repo skeleton created.
