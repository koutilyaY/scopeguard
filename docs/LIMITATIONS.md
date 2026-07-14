# ScopeGuard Known Limitations

ScopeGuard is an evidence-gathering, decision-support MVP. It is deliberately narrow.

## It does not
- **Give legal advice.** Findings never state legal conclusions; contract
  interpretation may be ambiguous and is flagged as such.
- **Give accounting advice.** Monetary figures are operational estimates for human
  review, not accounting determinations.
- **Automatically invoice.** No invoice is ever created by the system.
- **Automatically send email.** Clarification emails are drafts only; nothing is sent.
- **OCR scanned documents.** PDFs without machine-readable text are rejected with a
  clear message; content is never hallucinated from unreadable files.

## Not in the MVP
- Live Jira synchronization (CSV import + a connector interface only).
- Live QuickBooks/NetSuite/accounting integration (CSV import + interface only).
- Full Gmail/Outlook mailbox ingestion (uploaded `.eml`/`.txt`/PDF/DOCX or manual
  entry only).
- Slack ingestion, mobile/native apps, multiple UI languages, custom model training,
  Kubernetes, SOC 2 / HIPAA claims.

## Quality and operational caveats
- **Local model quality varies.** Classification and draft quality depend on the chosen
  Ollama model and hardware. The deterministic financial and duplicate logic is
  unaffected by model quality.
- **Unverified clauses are weak evidence.** Clauses the model extracts but a human has
  not verified cannot drive high-confidence recommendations; confidence is capped.
- **Contract ambiguity is real.** Where clauses conflict or are unclear, ScopeGuard
  reports *contract ambiguity* / *insufficient information* rather than guessing.
- **Human verification is required** for every finding and before any external-facing
  draft is generated.
- **Embedding dimension is fixed** at migration time (768 by default). Switching to an
  embedding model with a different dimension requires a new Alembic migration and
  re-embedding existing clauses.
- **Single-server Compose is not production-grade.** It is suitable for evaluation and
  pilots, not for regulated or enterprise production without the hardening in
  docs/DEPLOYMENT.md and SECURITY.md.

## Explicitly deferred
Automatic invoice creation, automatic email sending, legal conclusions, OCR, live
integrations, mailbox-wide ingestion, and fully autonomous contract decisions are all
out of scope by design — not oversights.
