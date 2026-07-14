# ScopeGuard Deployment

> **Local Docker Compose is for evaluation and single-server pilots only. It is not
> automatically suitable for regulated or enterprise production.** Treat the steps
> below as a starting point, not a compliance boundary.

## Local Docker Compose

```bash
cp .env.example .env
# edit .env: set a strong SECRET_KEY (openssl rand -hex 32) and real passwords
docker compose up --build -d
docker compose run --rm api python -m app.seed   # optional demo data
```

Services bind to `127.0.0.1` on the host. The API runs migrations on start
(`alembic upgrade head`) before serving.

## Single-server self-hosting

1. Provision a Linux VM with Docker + Docker Compose.
2. Put ScopeGuard behind a reverse proxy (Caddy or Nginx) terminating **TLS** — do not
   expose the app over plaintext HTTP. Set `COOKIE_SECURE=true` and
   `CORS_ORIGINS`/`API_INTERNAL_URL` to your real hostnames.
3. Generate secrets outside the repo and inject via environment or a secrets manager;
   never commit `.env`.
4. Restrict database/MinIO ports to the internal network.
5. Consider running Ollama on a host with a GPU for acceptable latency, or keep
   `LLM_PROVIDER` pointed at a local install.

### Reverse proxy (Caddy example)
```
scopeguard.example.com {
    reverse_proxy web:3000
}
```
The web container proxies `/api/*` to the API internally, so only the web port needs to
be public.

## TLS requirement
Sessions use cookies; without TLS, credentials and session tokens can be intercepted.
Always terminate TLS in front of the app in any networked deployment and set
`COOKIE_SECURE=true`.

## Secret management
`SECRET_KEY`, database and MinIO credentials must come from the environment or a
secrets manager. Rotate them on personnel changes. Logs redact passwords, cookies,
tokens and secrets.

## Backups and restore test
```bash
make backup                        # postgres dump + MinIO mirror → ./backups/<ts>
make restore FROM=backups/<ts>     # restore into a running stack
```
An automated restore smoke test (`tests/integration/test_backup_restore.py`) verifies a
`pg_dump`/`pg_restore` round-trip preserves the schema. Test your restore procedure on
a staging copy before relying on it.

## Upgrade procedure
1. `make backup`.
2. Pull the new code; review new migrations.
3. `docker compose build`.
4. `docker compose up -d` — the API applies `alembic upgrade head` on start.
5. Verify `/api/v1/health/ready` reports all dependencies healthy.

## Observability
- Structured JSON logs with request IDs (and user/org IDs where safe).
- `/api/v1/health` (liveness), `/api/v1/health/ready` (DB/Redis/MinIO/Ollama/Celery),
  `/api/v1/health/ollama` (model install check).
- Container health checks are defined for every service in `docker-compose.yml`.
