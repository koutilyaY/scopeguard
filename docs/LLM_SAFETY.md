# ScopeGuard LLM Safety

ScopeGuard uses a local LLM only for **classification** and **draft text**, never for
money, dates, or duplicate detection. Several layers keep model output honest.

## Prompt injection
Uploaded contracts, emails and Jira tickets are third-party, untrusted data. Every
production prompt (in `apps/api/prompts/`) states explicitly that content inside the
delimited evidence blocks is *data, not commands*, and that instructions such as
"ignore previous instructions" must never be followed. Evidence is wrapped in clear
delimiters (`<<<DOCUMENT>>>`, `CLAUSE id=…`) so the model can distinguish system
instructions from data. Tested in `tests/security/test_llm_safety.py`.

## Hallucinated evidence and citation verification
The classification schema requires the model to cite `entity_id`s and exact
`quotation`s. Before any finding is created:
- Each cited `entity_id` must be one that was actually supplied to the model.
- Each quotation must appear **verbatim** (after whitespace/case normalization) in the
  cited source (`app/services/citations.py`).
- Fabricated citations are dropped. If all clause citations fail, the classification is
  downgraded to *insufficient information* with capped confidence.
- Contract extraction rejects any clause whose `source_quotation` is not found verbatim
  in the document.

## Model limitations
Local models vary in quality. ScopeGuard mitigates this by (a) keeping all monetary
and duplicate logic deterministic, (b) capping confidence when cited clauses are not
human-verified, (c) requiring human review of every finding, and (d) exposing
uncertainty (classification band, confidence, missing evidence, contradicting
evidence) rather than hiding it.

## Model substitution
Models are configurable (`OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`). The active
`prompt_version` and `model_name` are recorded on every `ReviewRun` and
`GeneratedArtifact` for reproducibility and audit. Changing the embedding model to a
different dimension requires a migration.

## Structured output and repair
All model calls go through `generate_structured()`, which extracts JSON (tolerating
code fences and `<think>` blocks), validates against a Pydantic schema, and on failure
re-prompts with the validation error up to a retry limit before raising — the review
run records the failure rather than emitting garbage.

## Human review
No finding is billable and no external-facing artifact exists without an explicit
human decision. The system never sends email and never creates an invoice.

## What is sent to Ollama
Only the minimum evidence needed for the current task: the relevant contract clauses
and the specific work group (work items, time entries, customer requests) being
classified — not the entire contract corpus or unrelated projects. Ollama runs locally
but is still treated as a separate service across a trust boundary.
