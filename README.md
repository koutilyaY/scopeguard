# ScopeGuard

**Evidence-backed scope and billing review for consulting firms.**

Before a consulting firm issues an invoice, ScopeGuard compares the customer
contract, statements of work, amendments, change orders, Jira work items, timesheets,
customer-request emails, existing invoices and rate cards to answer one question:

> *Did we perform potentially out-of-scope work during this billing period, and is
> there enough evidence to review it for a change order or additional invoice?*

Every finding cites its source evidence and must be reviewed by a human. ScopeGuard
**never** auto-invoices a customer, never sends email automatically, and never
presents its conclusions as legal or accounting advice. Monetary math, duplicate
detection and contract-date logic are all deterministic application code — the local
LLM only classifies and drafts, and every quotation it returns is verified verbatim
against the source before it is trusted.

> ScopeGuard provides operational review assistance. Findings are not legal advice
> and are not accounting advice. Potential value does not equal invoiced or collected
> revenue. Human verification is required.

---

## Architecture at a glance

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router), TypeScript strict, Tailwind, TanStack Query, React Hook Form + Zod |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16 + pgvector |
| Jobs | Celery + Redis |
| Storage | MinIO (S3-compatible) |
| Local AI | Ollama (configurable chat + embedding models) with a deterministic fake provider for tests |
| Email (test only) | Mailpit — the app never sends automatically |

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full picture and the
deterministic-vs-LLM boundary.

## Prerequisites

- Docker + Docker Compose
- [Ollama](https://ollama.com) — **required for scope classification** (path B below).
  Not required for tests, the deterministic evaluation, or the no-AI demo (path A):
  those use a built-in deterministic provider.

## Quick start (Docker)

You must pick a provider. `LLM_PROVIDER` decides whether Ollama is needed — with the
shipped default (`ollama`), reviews **will not classify anything** until Ollama is
running with the configured models pulled.

### Path A — demo without AI (fastest, no model download)

Uses the built-in deterministic provider. Every monetary figure, duplicate check and
date rule is identical to path B (that logic never uses an LLM); only the scope
*classification* and draft text come from rules instead of a model.

```bash
cp .env.example .env
sed -i '' 's/^LLM_PROVIDER=ollama/LLM_PROVIDER=fake/' .env   # Linux: sed -i 's/.../.../'
docker compose up --build -d
docker compose run --rm api python -m app.seed
```
Running a June-2025 review on the demo project then yields the $6,080 finding described
below.

### Path B — real local AI (Ollama)

```bash
cp .env.example .env                      # keeps LLM_PROVIDER=ollama
docker compose --profile ai up --build -d # NOTE: --profile ai also starts Ollama
docker compose exec ollama ollama pull qwen3:8b          # ~5 GB, one-time
docker compose exec ollama ollama pull nomic-embed-text  # ~275 MB, one-time
docker compose run --rm api python -m app.seed
```
Check readiness before running a review:
```bash
curl -s localhost:8000/api/v1/health/ollama   # lists missing models + exact pull commands
```

> If `LLM_PROVIDER=ollama` and Ollama is unreachable, a review still completes and still
> returns its **deterministic** findings (duplicates, allowances, reconciliation), but it
> is marked `completed_with_errors` and the UI shows exactly which groups could not be
> classified. It does not fail silently, and it does not invent results.

Then open:

| URL | What |
|-----|------|
| http://localhost:3000 | ScopeGuard web app |
| http://localhost:8000/docs | API (OpenAPI) docs |
| http://localhost:9003 | MinIO console |
| http://localhost:8025 | Mailpit |

### Seeded demo credentials (development only)

| Role | Email | Password |
|------|-------|----------|
| Organization admin | `admin@northstar.example` | `Northstar-Demo-2025` |
| Reviewer | `reviewer@northstar.example` | `Reviewer-Demo-2025` |

The seed builds the **Northstar Data Consulting → Acme Retail → Snowflake
Modernization** scenario: five contracted pipelines, a customer email requesting a
sixth (Salesforce) source, Jira work and 34 recorded hours (with one intentional
duplicate row), a mid-period rate change via amendment, and an existing invoice
containing only the fixed fee. Running a June 2025 review produces a
*potentially out-of-scope* finding worth **$6,080.00** (21h @ $175 + 13h @ $185, the
duplicate excluded), citing the exclusion clause and the customer request, plus a
deterministic duplicate finding — all pending human review.

## Ollama setup (required when `LLM_PROVIDER=ollama`, the shipped default)

```bash
# containerized:
docker compose --profile ai up -d ollama
docker compose exec ollama ollama pull qwen3:8b
docker compose exec ollama ollama pull nomic-embed-text
# then set LLM_PROVIDER=ollama in .env and restart api + worker
```

Visit **Settings → Check Ollama models** in the app (or `GET /api/v1/health/ollama`)
for a list of missing models and the exact `ollama pull` commands. Change models via
`OLLAMA_CHAT_MODEL` / `OLLAMA_EMBED_MODEL`. Note: changing the embedding model to one
with a different dimension requires a new migration (see
[docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

## Development workflow (hot reload)

```bash
make dev            # start postgres, redis, minio, mailpit only
make dev-api        # uvicorn --reload on :8000   (separate terminal)
make dev-worker     # celery worker              (separate terminal)
make dev-web        # next dev on :3000          (separate terminal)
```

`make setup` creates the backend venv and installs frontend deps.

## Environment variables

All configuration is via environment variables; see [.env.example](.env.example) for
the full annotated list. Key ones: `DATABASE_URL`, `REDIS_URL`, `MINIO_*`,
`OLLAMA_*`, `LLM_PROVIDER` (`ollama` | `fake`), `SESSION_TTL_MINUTES`,
`MAX_UPLOAD_BYTES`.

## Testing

```bash
make test            # backend unit+integration+security, then frontend unit
make test-unit       # backend pytest tests/unit
make test-integration# backend pytest tests/integration + tests/security
make test-e2e        # Playwright (requires app + seeded data running)
make lint            # ruff + eslint
make typecheck       # mypy + tsc
```

The backend suite runs against the compose Postgres (`scopeguard_test` database) and
uses the deterministic fake LLM provider — no live model is required.

## Evaluation

```bash
make eval            # deterministic suite (fake provider) — financial accuracy must be 100%
make eval-ollama     # optional: same suite against a live local Ollama model
```

Reports classification accuracy, citation validity, unsupported-claim rate,
insufficient-information rate, financial-calculation accuracy and duplicate-counting
failures. See [evaluations/](apps/api/evaluations).

## Backups

```bash
make backup                       # dumps postgres + MinIO into ./backups/<timestamp>
make restore FROM=backups/<timestamp>
```

An automated restore smoke test lives in
`apps/api/tests/integration/test_backup_restore.py`.

## Screenshots

Generate screenshots by running the stack and driving the demo workflow (login →
dashboard → finding detail). The Playwright config captures screenshots on failure;
to capture deliberately, add `await page.screenshot({ path: "docs/img/<name>.png" })`
to an `e2e/` spec and run `make test-e2e`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `api` unhealthy on first boot | It waits for Postgres/Redis/MinIO health; give it ~30s. Check `docker compose logs api`. |
| Ollama findings look weak | Local model quality varies; the deterministic financial numbers are unaffected. Try a stronger `OLLAMA_CHAT_MODEL`. |
| "does not contain sufficient machine-readable text" | The PDF is scanned; OCR is not enabled in this version. |
| Port already in use | Compose binds to `127.0.0.1` on non-default host ports (5433, 6380, 9002/3, 8025); the app ports are 8000/3000. |

## Known limitations

No OCR, no live Jira/QuickBooks integration, no mailbox ingestion, no automatic
invoicing or emailing, no legal conclusions. Full list:
[docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Production warning

Local Docker Compose is for evaluation and single-server pilots. It is **not**
automatically suitable for regulated or enterprise production. See
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) and [SECURITY.md](SECURITY.md) before any
real deployment.

## License

GNU Affero General Public License v3.0 — see [LICENSE](LICENSE).
