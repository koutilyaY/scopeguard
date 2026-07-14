# ADR-0007: Session-cookie authentication

## Status
Accepted

## Context
We need authentication for a browser SPA that is secure by default and avoids common
token-storage pitfalls.

## Decision
Use server-side sessions referenced by an opaque token in an **HttpOnly**, SameSite=Lax
cookie. Only the SHA-256 of the token is stored in Postgres. CSRF protection uses a
double-submit token (readable cookie echoed in the `X-CSRF-Token` header, verified
against the session). No JWTs are stored in `localStorage`. Passwords are hashed with
Argon2id; repeated failures trigger lockout.

## Consequences
- XSS cannot read the session token (HttpOnly); a DB leak does not expose usable
  sessions (only hashes are stored).
- The Next.js app proxies `/api/*` to the backend so cookies stay first-party in every
  environment.
- Logout and password change invalidate server-side sessions immediately.
