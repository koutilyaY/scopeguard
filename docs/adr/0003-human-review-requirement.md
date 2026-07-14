# ADR-0003: Human review is mandatory

## Status
Accepted

## Context
ScopeGuard influences billing decisions between a firm and its client. Incorrect
automated conclusions could damage client relationships or misstate revenue.

## Decision
Every AI-derived finding is created with `review_status = pending` and cannot become
`approved_for_billing` without an explicit human decision that records a reason.
External-facing artifacts (change-order drafts, clarification emails) can only be
generated after a human approves the finding. No email is ever sent and no invoice is
ever created by the system.

## Consequences
- The product is decision-support, not automation. UI and copy consistently say
  "Potentially billable — human review required."
- Extra review steps are enforced in code (`ArtifactService`, decision transitions),
  not merely in documentation.
- Findings track four distinct value stages: potential identified, approved for
  billing, invoiced, collected.
