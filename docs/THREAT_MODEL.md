# ScopeGuard Threat Model

Structured with STRIDE. This is an MVP threat model for a self-hosted, single-server
deployment; see docs/LIMITATIONS.md and SECURITY.md for hardening steps.

## Protected assets
- Customer contracts and their extracted text (confidential, sometimes privileged).
- Timesheets, invoices, findings and monetary figures.
- User credentials and sessions.
- Tenant boundary (one firm's data must never reach another).
- The audit trail (integrity).

## Trust boundaries
1. Browser ↔ web app (untrusted client input).
2. Web app ↔ API (first-party cookie; CSRF-protected).
3. API ↔ Postgres/Redis/MinIO (internal network).
4. API/worker ↔ Ollama (treated as a separate service; only minimal evidence sent).
5. Uploaded documents / imported tickets = **untrusted data**, never instructions.

## STRIDE analysis

| Threat | Vector | Mitigation |
|--------|--------|------------|
| **Spoofing** | Credential stuffing, session theft | Argon2id, lockout + rate limiting, HttpOnly cookies, only session-token hashes stored |
| **Tampering** | Cross-tenant object mutation, CSRF | `organization_id` scoping + 404 on mismatch, CSRF double-submit, check constraints |
| **Repudiation** | "I didn't approve that finding" | Append-only `audit_events` with actor, request_id, before/after |
| **Information disclosure** | Cross-tenant reads, log leakage, prompt injection exfiltration | Tenant-filtered queries + vector retrieval, log redaction of secrets/PII/full text, minimal evidence to LLM |
| **Denial of service** | Oversized uploads, huge imports, review floods | Upload size limit, request-size limit, import row cap, per-endpoint rate limiting |
| **Elevation of privilege** | read_only performing writes, role bypass | RBAC dependencies (`require_role`, `require_any_role`) on every mutating route |

## LLM-specific threats
- **Prompt injection** in contract/ticket text → prompts declare document content as
  data; instructions inside it are never followed. Covered by
  `tests/security/test_llm_safety.py`.
- **Hallucinated evidence** (fabricated IDs/quotations) → every citation is verified
  verbatim against supplied evidence; fabrications are dropped and confidence
  downgraded.
- **Non-deterministic arithmetic** → the LLM never computes money.

## Out of scope for the MVP threat model
Network-level DDoS, host OS hardening, physical security, supply-chain attacks on
third-party images, and formal key management (see DEPLOYMENT.md for production notes).
