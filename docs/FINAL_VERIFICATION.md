# ScopeGuard — Final Verification

Date of run: 2026-07-14. All commands were executed against the local Docker
infrastructure (Postgres 16 + pgvector, Redis, MinIO) with the deterministic fake LLM
provider. Ollama was **not** required for any test or evaluation.

## Commands executed and results

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
