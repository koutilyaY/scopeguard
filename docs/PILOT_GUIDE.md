# ScopeGuard Pilot Guide

How to run a low-risk pilot of ScopeGuard with a consulting firm using anonymized data.

## Goals of a pilot
Answer, for one or two real billing periods: *did the firm perform potentially
out-of-scope work with enough evidence to pursue a change order?* — and measure how much
reviewer time ScopeGuard saves versus a manual review.

## Before you start
- Pick a **single project** with a reasonably complete paper trail (a signed SOW, some
  Jira/timesheet data, at least one prior invoice).
- Decide who the **reviewers** are (finance manager / PM) and give them the `reviewer`
  or `finance_manager` role. Keep `organization_admin` to one or two people.
- Agree that ScopeGuard output is **advisory** — no invoice or email goes out because of
  it without the firm's normal approval process.

## Anonymizing data for a pilot
1. Replace client and employee names with pseudonyms before upload (e.g. "Client A",
   "Engineer 1"). ScopeGuard treats these as opaque strings.
2. Redact rates you consider sensitive, or scale them by a constant factor — the math is
   deterministic, so relative results are preserved.
3. Use the CSV/XLSX templates so you control exactly which columns are ingested; the
   preview step shows precisely what will be stored before you commit.
4. Because everything runs locally with a local model, **no data leaves the machine** by
   default (see docs/LLM_SAFETY.md).

## Suggested pilot flow
1. Create the org, client and project.
2. Upload the SOW/MSA/amendments; run clause extraction; **verify the extracted
   clauses** (this is the human-in-the-loop step that anchors everything else).
3. Import Jira work items, timesheets and the existing invoice(s).
4. Run a review for the target billing period.
5. In the finding inbox, work each finding: confirm the evidence, check the deterministic
   calculation, and record a decision with a reason.
6. For anything approved for follow-up, generate an internal review summary and a
   change-order draft, and export the evidence report (PDF/JSON).
7. Review the audit log together.

## What to measure
- Reviewer minutes per finding vs. a manual pass.
- Precision: of findings marked "potentially out of scope," how many the firm agreed
  warranted follow-up.
- False negatives you can spot: known out-of-scope work the review missed (often a data
  or clause-verification gap — fix the input and re-run).
- Dollar value **identified** vs. **approved** vs. eventually **invoiced** — keep these
  separate, exactly as the dashboard does.

## Exit criteria
A successful pilot ends with the firm able to say: "ScopeGuard surfaced at least one
reviewable, evidence-backed finding we would otherwise have missed or spent
significantly longer finding, and it never pushed us toward an action we hadn't
approved." See the top-level completion notes for the first five tasks to do before a
production pilot.
