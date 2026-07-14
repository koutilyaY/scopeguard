# ADR-0004: Deterministic billing calculations

## Status
Accepted

## Context
LLMs are unreliable at arithmetic and non-reproducible. Monetary figures must be
exact, auditable and identical on every run.

## Decision
All monetary and quantity calculations are performed in application code, never by the
LLM: time valuation, allowance consumption, invoice reconciliation, aggregation, and
currency handling live in `app/services/review/`. Money is stored as integer minor
units; intermediate math uses `Decimal` with explicit `ROUND_HALF_UP`. Currencies are
never combined; a missing verified rate yields "value unavailable", never a fabricated
estimate.

## Consequences
- The evaluation suite asserts 100% financial-calculation accuracy.
- Every aggregate traces to source rows; the same time entry is never counted twice.
- The LLM's role is limited to classification and drafting, both of which are
  source-grounded and human-reviewed.
