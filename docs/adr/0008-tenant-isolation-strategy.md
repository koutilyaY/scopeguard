# ADR-0008: Tenant isolation strategy

## Status
Accepted

## Context
Multiple consulting firms (organizations) share one deployment. One org must never
access another's documents, projects, findings, users or exports.

## Decision
Single database, shared schema, **row-level scoping**: every org-owned table has a
non-null `organization_id`. Access is enforced in the dependency/service layer:
`get_org_object()` returns 404 for any object whose `organization_id` does not match
the caller's, and all list queries filter on `organization_id`. Vector retrieval
applies the org filter in SQL before similarity ordering. Cross-tenant attempts return
404 (not 403) so existence is not confirmed.

## Consequences
- Simpler ops than database-per-tenant; adequate for an MVP/pilot.
- Isolation correctness is covered by dedicated security tests
  (`tests/security/test_tenant_isolation.py`).
- A future move to Postgres Row-Level Security or schema-per-tenant remains possible
  without changing the domain model.
