# ADR-0009: Worker shares the API codebase

## Status
Accepted

## Context
The spec's monorepo sketch lists `apps/worker` as a sibling of `apps/api`. The worker
needs every SQLAlchemy model and every review/extraction service the API uses.

## Decision
Keep a single Python package under `apps/api` (`app/`) that contains both the FastAPI
app (`app.main`) and the Celery app (`app.worker`). The worker runs from the **same
Docker image** as the API with a different entrypoint (`celery -A app.worker
celery_app worker`). There is no separate `apps/worker` Python package.

## Consequences
- No duplication of models or services; one migration history, one dependency set.
- `docker-compose.yml` defines separate `api` and `worker` services built from the
  same context — satisfying the "apps/worker" separation at the deployment level.
- This deviation from the literal directory sketch is recorded here as required by the
  brief.
