# ADR-0005: Uploaded email files instead of mailbox access

## Status
Accepted

## Context
Customer requests are important evidence, but full mailbox access (Gmail/Outlook) adds
OAuth complexity, broad data exposure and scope creep for an MVP.

## Decision
Support customer requests via uploaded `.eml`/`.txt` files, PDF/DOCX documents, or
manual entry. Parse EML with the stdlib `email` module (HTML bodies via BeautifulSoup).
Do not connect to live mailboxes.

## Consequences
- Only the specific emails a user chooses are ingested — minimal data exposure.
- No OAuth, no background mailbox polling, no per-provider integration to maintain.
- Full mailbox ingestion is explicitly out of scope (see docs/LIMITATIONS.md).
