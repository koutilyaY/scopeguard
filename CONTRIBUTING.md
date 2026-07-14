# Contributing to ScopeGuard

Thanks for your interest. ScopeGuard is licensed under AGPL-3.0; contributions are
accepted under the same license.

## Ground rules that are non-negotiable
These reflect the product's core principles — PRs that violate them will not be merged:
1. **Human approval stays mandatory.** No automatic invoicing, no automatic email.
2. **Money, dates, duplicates and reconciliation are deterministic code** — never the
   LLM.
3. **Every AI conclusion cites verifiable source evidence**; citations are verified
   verbatim.
4. **No legal or accounting conclusions.**
5. **No paid APIs or SaaS**; everything runs locally and free.
6. Preserve the **audit log** and **tenant isolation**.

## Development setup
```bash
make setup        # backend venv + frontend deps
make dev          # infra containers (postgres, redis, minio, mailpit)
make dev-api / make dev-worker / make dev-web   # hot-reload processes
```

## Before you open a PR
```bash
make lint         # ruff + eslint
make typecheck    # mypy + tsc (strict)
make test         # backend + frontend unit/integration/security
make eval         # deterministic evaluation (financial accuracy must stay 100%)
```
- Add or update tests for any behavior change. New review-engine logic needs unit tests;
  new API routes need tenant-isolation and RBAC coverage.
- Keep modules small and focused; no business logic in route handlers or React
  components (use the service/hook layers).
- Don't disable strict typing or add broad `except:` blocks that hide failures.
- Document *why*, not *what*, in comments.

## Code style
- Python: Ruff-formatted, fully typed, `Decimal`/minor-units for money.
- TypeScript: strict mode, ESLint + Prettier, Zod for input validation.

## Commit / PR
- Keep changes focused and logically committed.
- Describe user-visible impact and any migration in the PR body.
- CI (lint, typecheck, tests, build, dependency scan, docker build) must be green; it
  requires no repository secrets.

## Reporting security issues
See [SECURITY.md](SECURITY.md) — do not use public issues for vulnerabilities.
