# Security Policy

ScopeGuard handles confidential contracts and billing data. This document summarizes
the security posture of the MVP and how to report issues. See
[docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) for the full analysis.

## Protected assets
Customer contracts and extracted text, timesheets, invoices, findings and monetary
figures, user credentials and sessions, the tenant boundary, and the audit trail.

## Trust boundaries
Browser ↔ web app ↔ API ↔ (Postgres / Redis / MinIO) and API/worker ↔ Ollama.
Uploaded documents and imported tickets are **untrusted data**, never instructions.

## Controls implemented
- **AuthN**: Argon2id password hashing; server-side sessions (only the SHA-256 of the
  session token is stored); HttpOnly, SameSite=Lax cookies; account lockout and login
  rate limiting; minimum password policy.
- **AuthZ**: role-based access control on every mutating route; organization isolation
  enforced in the service/dependency layer with 404 on cross-tenant access.
- **Web**: CSRF double-submit tokens; CORS allowlist; security headers
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP-friendly);
  request-size limits.
- **Uploads**: MIME + extension allowlist, magic-byte sniffing, size cap, random
  storage keys, filename sanitisation, SHA-256 dedup; no macro/script execution.
- **Data**: parameterized queries (SQLAlchemy) — no string-built SQL; check constraints
  on money/time; IDOR protection via org-scoped lookups.
- **Secrets**: supplied via environment; none committed; logs redact passwords,
  cookies, tokens, secrets and avoid full document text.
- **LLM**: prompt-injection-resistant prompts, verbatim citation verification,
  fabricated-evidence rejection (see [docs/LLM_SAFETY.md](docs/LLM_SAFETY.md)).
- **Ops**: container health checks; non-root containers; DB least-privilege intent;
  structured audit logging.
- **CI**: dependency vulnerability scanning (pip-audit, npm audit) on every run.

## Known limitations (MVP)
- Single-server Docker Compose is not, by itself, production-grade or a compliance
  boundary.
- No formal secret-management integration (env-var based).
- Rate limiting is per-process/Redis-backed, not a distributed WAF.
- No OCR; scanned documents are rejected rather than processed.
- Local model quality varies; all safety-critical numbers are deterministic regardless.

## Production-hardening checklist
- [ ] Terminate TLS in front of the app; set `COOKIE_SECURE=true`.
- [ ] Generate a strong unique `SECRET_KEY` and real DB/MinIO credentials; store them in
      a secrets manager.
- [ ] Restrict Postgres/Redis/MinIO to the internal network.
- [ ] Set `CORS_ORIGINS` to your real origins only.
- [ ] Run Postgres with a least-privilege application role.
- [ ] Configure off-host, encrypted backups and test restores (see docs/DEPLOYMENT.md).
- [ ] Add centralized log aggregation and alerting.
- [ ] Review dependency-scan output and patch before go-live.
- [ ] Pen-test the tenant boundary and file-upload paths.

## Reporting a vulnerability
Do **not** open a public issue for security problems. Email the maintainers (see repo
metadata) with a description, reproduction steps and impact. We aim to acknowledge
within a few business days. Please allow reasonable time for a fix before public
disclosure.
