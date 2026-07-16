# ScopeGuard — Final Verification

Date of run: 2026-07-14. All commands were executed against the local Docker
infrastructure (Postgres 16 + pgvector, Redis, MinIO) with the deterministic fake LLM
provider. Ollama was **not** required for any test or evaluation.

## Audit re-run (2026-07-14, post-implementation audit)

A full audit of the repository against every mandatory acceptance criterion was
performed (see [REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md)). It found
and fixed one **critical correctness defect** plus three minor defects; every check
below was then re-run green.

| Check | Result |
|-------|--------|
| `ruff check` / `ruff format --check` | clean (1 test file reformatted during audit) |
| `mypy app` | clean (75 files) |
| `pytest tests` | **140 passed, 0 skipped** (was 139; +1 regression test) |
| `evaluations.run --provider fake` | PASS — financial 100% (11/11), citation validity 100% |
| migration up/down/up from empty | OK |
| seed on fresh DB | OK |
| frontend eslint / tsc / prettier --check | clean (17 files formatted during audit) |
| frontend vitest | 13 passed |
| frontend build | OK |
| Playwright e2e | **5 passed, deterministic** (re-ran the fixed test 3× — no flake) |
| `docker compose up` (rebuilt api + worker) | all 7 services healthy; `/health/ready` all true |
| containerized double-count regression | approve + re-run → **1 finding, $6,080** (was 2 / $12,160) |
| backup (container `pg_dump`) | valid PGDMP dump |

**Critical defect fixed — potential-value double-counting.** Before the fix, running a
review, approving the finding for follow-up, then re-running the review created a
second finding for the same evidence, so the dashboard showed **$12,160** for work
worth **$6,080**. Root cause: dedup treated only `pending`/`needs_more_evidence` as
"occupying" the evidence. Fix: `services/review/engine.py` now also treats
`approved_for_followup` and `approved_for_billing` as occupying; only `rejected` /
`already_resolved` free the evidence for a fresh finding. Reproduced before fixing,
covered by `test_rerun_after_approval_does_not_duplicate_finding`, and re-verified on
host, in a unit test, and in the fully containerized stack.

Minor defects fixed: flaky approve→generate e2e test (now deterministic); unlabeled
finding-filter `<select>`s (added `htmlFor`/`aria-label`); unformatted frontend/test
files (prettier/ruff format applied).

## Fresh-clone verification (2026-07-14, third pass — adversarial)

Previous passes tested with a **pre-seeded volume** and hand-set env vars, which hid
first-run defects. This pass cloned the repo to a new directory, used **empty volumes**,
copied `.env.example` unmodified, and followed the README literally. Four defects
surfaced; all are fixed and re-verified.

1. **The documented quick start did not produce a working product.** `.env.example`
   ships `LLM_PROVIDER=ollama`, but the `ollama` service sits behind `profiles: ["ai"]`,
   so `docker compose up` never starts it — while the README called Ollama
   *"(optional)"*. A new user's first review returned `completed_with_errors`, produced
   **no scope findings**, and only the deterministic duplicate finding.
   *Fix*: README now documents two explicit paths (A: no-AI deterministic demo, B: real
   Ollama with the `--profile ai` and `pull` commands); `.env.example` states the
   consequence of each. Verified: Path A on a fresh clone yields `completed`,
   `classification_errors: 0`, and the $6,080 finding.
2. **Review failures were invisible in the UI.** `failure_reason` was returned by the
   API and typed in TS but **never rendered** — users saw a bare `completed with errors`
   badge with no explanation, violating the "user-visible failure message" requirement.
   *Fix*: `ReviewTab` renders an alert with the reason; two regression tests added.
3. **The test suite lied when the database was down.** 44 DB-backed tests (auth, tenant
   isolation, review pipeline) **silently skipped** while pytest still exited 0 — a green
   run proving almost nothing. It produced a false "all clear" twice during this session.
   *Fix*: `conftest.py` now raises loudly (exit 4) with the DSN and underlying error
   unless `SCOPEGUARD_ALLOW_DB_SKIP=1`. Also `test_llm_safety.py` *errored* instead of
   skipping (missing `requires_db`) — fixed.
4. **Infra host ports were hardcoded**, colliding with other projects on the same
   machine and surfacing as a confusing `password authentication failed` (tests were
   silently talking to a *different project's* Postgres on 5433).
   *Fix*: `POSTGRES_HOST_PORT`, `REDIS_HOST_PORT`, `MINIO_HOST_PORT`,
   `MINIO_CONSOLE_HOST_PORT`, `MAILPIT_HOST_PORT`, `MAILPIT_SMTP_HOST_PORT`,
   `OLLAMA_HOST_PORT` — same defaults, now overridable, in both compose files.

Final fresh-clone result (empty volumes, `.env.example` + documented vars only):

| Check | Result |
|-------|--------|
| `docker compose up --build -d` | all 7 services **healthy** |
| `/health/ready` | database, redis, minio, ollama, celery — all `true` |
| seed on empty volume | Northstar demo org created |
| review via web proxy | `completed`, `classification_errors: 0`, duplicate excluded |
| finding | **$6,080 USD**, 4 evidence items, 6 valued entries |
| approve → change-order draft → PDF | all OK (4-page, 5,886 bytes) |
| dashboard | potential $6,080 vs invoiced $85,000, correctly separated |
| Playwright e2e vs fresh-clone stack | **5/5 passed** |
| backend / frontend | **140** + **15** passed; ruff, format, mypy, eslint, tsc, prettier clean |
| evaluation | PASS — financial **100%**, citation validity 100% |

## Docker-deployment verification (2026-07-14, second pass)

Running the **fully containerized** stack (rather than host dev servers) surfaced two
deployment defects that host-mode testing could not have caught. Both are fixed and
re-verified.

1. **Web container could not serve the app at all (login 500).** `next.config.mjs`
   defines the `/api/*` → API rewrite, but **Next evaluates `rewrites()` at build time**
   and freezes the destination into `.next/routes-manifest.json`. `API_INTERNAL_URL` was
   only supplied at *runtime*, so the image had `http://localhost:8000` baked in.
   Container log: `Failed to proxy http://localhost:8000/api/v1/auth/login Error:
   connect ECONNREFUSED 127.0.0.1:8000`. Every request through the web proxy returned
   500 — the app was unusable in Docker.
   *Fix*: `apps/web/Dockerfile` now takes `ARG API_INTERNAL_URL` (default
   `http://api:8000`, matching the compose service) and sets it before `npm run build`;
   `docker-compose.yml` passes it as a build arg. Verified: baked destination is now
   `http://api:8000/api/:path*` and proxied login returns **200**.
2. **Web healthcheck could never pass.** It used `wget`, which does not exist in
   `node:20-slim` (nor does curl) — every probe failed with `wget: not found`, so the
   container would go **unhealthy**. Compounding this, Next's standalone server binds to
   `$HOSTNAME`, which Docker sets to the container name, so it listened only on the
   container's eth0 IP and refused `localhost` connections.
   *Fix*: healthcheck now uses the `node` runtime itself; `HOSTNAME=0.0.0.0` set in the
   Dockerfile so the server binds all interfaces. Verified: `web: Up (healthy)`.

Post-fix containerized results:

| Check | Result |
|-------|--------|
| `docker compose up -d --build` | **all 7 services healthy** (api, web, worker, postgres, redis, minio, mailpit) |
| `/api/v1/health/ready` | `{database, redis, minio, ollama, celery}` all `true` |
| login via web proxy (`:13000`) | 200 |
| Playwright e2e **against the Docker stack** | **5/5 passed** |
| Full workflow via containers | review completed → 1 finding + 1 duplicate excluded → $6,080 (6 valued entries, 4 evidence items) → approve → change-order draft → 4-page PDF |
| Container logs | no ERROR/Traceback |

**Deployment note (documented limitation):** because Next bakes rewrite destinations at
build time, pointing the web app at a different API host requires a rebuild:
`docker build --build-arg API_INTERNAL_URL=https://api.example.com -f apps/web/Dockerfile .`

## Commands executed and results (original build run)

### Repository hygiene search
```
grep -rniE "todo|fixme|not implemented|hardcoded secret"  → 0 matches in app/src
grep "mock"                                               → 0 matches in app/src
grep "placeholder"                                        → only HTML input placeholder attrs
bare `pass` statements                                    → 3, all legitimate:
    LLMUnavailableError / CurrencyMismatchError (empty exception subclasses),
    one intentional json.JSONDecodeError fall-through to the next parse strategy
hardcoded secrets scan                                    → 0 matches
```

### Database migration from empty
```
alembic upgrade head    (fresh DB)  → OK  (-> 15111a3648bd, initial schema)
alembic downgrade base              → OK
alembic upgrade head    (again)     → OK
```

### Backend: lint, types, tests
```
ruff check app tests    → All checks passed!
mypy app                → Success: no issues found in 75 source files
pytest tests -q         → 139 passed, 4 warnings
```
Test breakdown: unit (money, time, allowance, rate dates, precedence, duplicates,
reconciliation, evidence scoring, imports, fake provider, citations), integration
(auth flow, review pipeline, imports/exports, backup/restore), security (tenant
isolation, RBAC + uploads, LLM safety / prompt injection / fabricated evidence).

### Deterministic evaluation suite
```
python -m evaluations.run --provider fake  → RESULT: PASS
  Financial-calculation accuracy : 100.0% (11/11)   [required 100%]
  Duplicate-counting failures    : 0
  Classification accuracy        : 100.0% (fake provider, deterministic)
  Citation validity              : 100.0%
  Unsupported-claim rate         : 0.0%
  Insufficient-information rate  : 28.6%
  Authorization detection acc.   : 100.0%
```

### Frontend: lint, types, tests, build
```
npm run lint      → ✔ No ESLint warnings or errors
tsc --noEmit      → clean (strict mode)
vitest run        → 13 passed
npm run build     → ✓ Compiled successfully (11 routes)
```

### End-to-end (Playwright, Chromium)
```
playwright test   → 5 passed
```
Covers: log in as seeded admin → value-stage dashboard → open project & Reviews tab →
open finding → verify exclusion-clause quotation + Jira evidence + deterministic
calculation → approve for follow-up → generate internal review summary → evidence-report
export link → audit-log entries.

### Docker Compose full stack
```
docker compose build api web  → both images built (api 591MB, web 241MB)
docker compose up -d          → postgres, redis, minio, mailpit, worker, api, web all Healthy
  /api/v1/health        → {"status":"ok","version":"0.1.0"}
  /api/v1/health/ready  → {database:true, redis:true, minio:true, celery:true, ollama:false*}
  web /login            → 200
containerized review run (July period) → completed
  dashboard: potential 608000 USD (=$6,080), invoiced 8500000 USD (=$85,000), separated
```
\* ollama:false is honest — no Ollama container was running in this verification; the
app uses the fake provider or the `--profile ai` Ollama service when present.

### Backup / restore
```
docker compose exec postgres pg_dump -Fc scopeguard  → valid 97KB PGDMP dump
tests/integration/test_backup_restore.py             → passed (pg_dump/pg_restore round-trip)
```

## Demo scenario verification (acceptance)
Running a June-2025 review on the seeded Northstar → Acme → Snowflake project produces:
- **One `potentially_out_of_scope` finding** — Salesforce sixth-source onboarding.
- **Potential value $6,080.00** = 21h @ $175 + 13h @ $185 (mid-period amendment rate),
  computed by deterministic code; the intentional duplicate row is excluded (only 6 of
  7 entries valued).
- **Evidence cited**: the exclusion clause (verbatim quotation, page/section), the Jira
  work item, and the customer-request email.
- **Missing evidence** flags absent written authorization.
- **One `possible_duplicate` finding** with no monetary value (excluded from totals).
- Finding created `pending`; no invoice created; no email sent.
- Re-running the same period creates **no duplicate findings** (dedup by evidence).

## Tests passed
- Backend: 139 (unit + integration + security)
- Frontend unit: 13
- E2E: 5
- Evaluation cases: 11 financial (100%) + 7 classification (100% on fake)

## Tests skipped (and why)
- `test_backup_restore.py` **skips** only when the host `pg_dump` binary is absent or
  its major version cannot dump the pg16 server. In this run it passed. The production
  backup path (`scripts/backup.sh`) always runs `pg_dump` inside the Postgres
  container, where versions match by construction — verified separately above.
- `eval-ollama` / live-Ollama evaluation is **optional and not run in CI** by design
  (requires a running local model). The deterministic fake-provider evaluation is the
  gating suite.

## Known defects
- None blocking. The web `dev` script hardcodes port 3000 (`next dev -p 3000`), so a
  custom `PORT` env is ignored in dev mode; compose maps host ports via
  `WEB_PORT`/`API_PORT` and works around any host conflict.
- `StarletteDeprecationWarning` about httpx in the test client is a library-level
  deprecation notice, not a failure.

## Security limitations (MVP)
- Single-server Compose is not, by itself, a production/compliance boundary.
- Env-var secret management (no external secrets manager integration).
- Rate limiting is Redis/in-process, not a distributed WAF.
- No OCR — scanned PDFs are rejected, never hallucinated.
See [SECURITY.md](../SECURITY.md) and [THREAT_MODEL.md](THREAT_MODEL.md).

## Production limitations
No live Jira/QuickBooks sync, no mailbox ingestion, no automatic invoicing or emailing,
no legal/accounting conclusions, local-model quality variance. See
[LIMITATIONS.md](LIMITATIONS.md) and [DEPLOYMENT.md](DEPLOYMENT.md).

## Exact next steps before a real customer pilot
1. Terminate TLS in front of the app; set `COOKIE_SECURE=true`, unique `SECRET_KEY`,
   real DB/MinIO credentials from a secrets manager.
2. Provision Ollama with a vetted `OLLAMA_CHAT_MODEL` and benchmark classification
   quality on the firm's own (anonymized) contracts.
3. Configure off-host encrypted backups and rehearse a full restore.
4. Add centralized log aggregation + alerting on the health/readiness endpoints.
5. Pen-test the tenant boundary and file-upload paths with a second organization.
