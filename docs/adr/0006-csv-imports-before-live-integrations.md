# ADR-0006: CSV imports before live integrations

## Status
Accepted

## Context
Firms keep work items in Jira and invoices in QuickBooks. Live integrations require
credentials, OAuth, rate-limit handling and per-vendor maintenance — too much for an
MVP, and impossible to exercise without accounts.

## Decision
Ship CSV/XLSX imports with documented templates, column mapping and per-row validation
with a preview step. Provide provider *interfaces* (`external_system` field on work
items, invoice `external_reference`) so live Jira/QuickBooks connectors can be added
later without schema changes. Do not implement unofficial scraping.

## Consequences
- The product is usable immediately with exports every firm can produce.
- Import validation (negative time, impossible dates, duplicates, unknown roles) is a
  first-class, tested feature.
- Live Jira/QuickBooks sync is explicitly out of scope for the MVP.
