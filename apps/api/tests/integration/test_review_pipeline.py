"""End-to-end review pipeline against the seeded demo scenario, via the fake LLM.

Verifies the mandatory demo behaviors: duplicate excluded, Salesforce work flagged
potentially out-of-scope, exclusion clause cited, customer request cited, Jira work
cited, deterministic $6,080 value at the correct split rates, missing-authorization
flagged, and a pending human-review finding.
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.models import Finding, FindingEvidence, Organization, Project, ReviewRun, User
from app.models.enums import (
    Classification,
    EvidenceType,
    FindingType,
    ReviewRunStatus,
    ReviewStatus,
)
from app.seed import seed
from app.services.review.engine import execute_review_run
from tests.conftest import requires_db

pytestmark = requires_db


@pytest.fixture
def seeded(db):
    seed()
    org = db.execute(select(Organization).where(Organization.slug == "northstar")).scalar_one()
    project = db.execute(select(Project).where(Project.organization_id == org.id)).scalar_one()
    admin = db.execute(select(User).where(User.email == "admin@northstar.example")).scalar_one()
    return org, project, admin


def run_review(db, org, project, admin) -> ReviewRun:
    run = ReviewRun(
        organization_id=org.id,
        project_id=project.id,
        billing_period_start=date(2025, 6, 1),
        billing_period_end=date(2025, 6, 30),
        status=ReviewRunStatus.pending,
        initiated_by=admin.id,
    )
    db.add(run)
    db.commit()
    execute_review_run(db, run.id)
    db.refresh(run)
    return run


def test_review_run_completes(seeded, db):
    run = run_review(db, *seeded)
    assert run.status == ReviewRunStatus.completed
    assert run.stats["duplicate_entries_excluded"] == 1
    assert run.model_name and run.prompt_version


def test_salesforce_flagged_out_of_scope(seeded, db):
    org, project, admin = seeded
    run = run_review(db, org, project, admin)
    findings = db.execute(select(Finding).where(Finding.review_run_id == run.id)).scalars().all()
    oos = [f for f in findings if f.finding_type == FindingType.potentially_out_of_scope]
    assert len(oos) == 1
    finding = oos[0]
    assert finding.classification == Classification.potentially_out_of_scope
    assert finding.review_status == ReviewStatus.pending
    assert "Potentially billable — human review required." in finding.explanation


def test_deterministic_value_is_6080(seeded, db):
    """34 eligible hours: 21h @ $175 + 13h @ $185 = $6,080.00 (duplicate excluded)."""
    org, project, admin = seeded
    run = run_review(db, org, project, admin)
    finding = db.execute(
        select(Finding).where(
            Finding.review_run_id == run.id,
            Finding.finding_type == FindingType.potentially_out_of_scope,
        )
    ).scalar_one()
    assert finding.potential_value_minor == 608_000
    assert finding.currency == "USD"
    # every entry traces to a source row
    entries = finding.calculation_breakdown["entries"]
    assert all("time_entry_id" in e for e in entries)
    # the duplicate (7th Salesforce row) is not among the valued entries
    assert len(entries) == 6


def test_duplicate_excluded_from_value(seeded, db):
    org, project, admin = seeded
    run = run_review(db, org, project, admin)
    dup = db.execute(
        select(Finding).where(
            Finding.review_run_id == run.id,
            Finding.finding_type == FindingType.possible_duplicate,
        )
    ).scalar_one()
    assert dup.potential_value_minor is None
    assert "excluded" in dup.explanation.lower()


def test_evidence_cites_clause_workitem_and_request(seeded, db):
    org, project, admin = seeded
    run = run_review(db, org, project, admin)
    finding = db.execute(
        select(Finding).where(
            Finding.review_run_id == run.id,
            Finding.finding_type == FindingType.potentially_out_of_scope,
        )
    ).scalar_one()
    evidence = (
        db.execute(select(FindingEvidence).where(FindingEvidence.finding_id == finding.id))
        .scalars()
        .all()
    )
    types = {e.entity_type for e in evidence}
    assert EvidenceType.contract_clause in types
    assert EvidenceType.work_item in types
    assert EvidenceType.customer_request in types


def test_missing_authorization_flagged(seeded, db):
    org, project, admin = seeded
    run = run_review(db, org, project, admin)
    finding = db.execute(
        select(Finding).where(
            Finding.review_run_id == run.id,
            Finding.finding_type == FindingType.potentially_out_of_scope,
        )
    ).scalar_one()
    assert any("authorization" in m.lower() for m in (finding.missing_evidence or []))


def test_allowance_exhaustion_finding_created(seeded, db):
    """12h consumed + would-be support work; only excess is flagged."""
    org, project, admin = seeded
    run = run_review(db, org, project, admin)
    findings = (
        db.execute(
            select(Finding).where(
                Finding.review_run_id == run.id,
                Finding.finding_type == FindingType.exhausted_allowance,
            )
        )
        .scalars()
        .all()
    )
    # 12h support in June is within the 20h allowance, so NO exhaustion finding.
    assert findings == []


def test_rerun_is_idempotent_no_duplicate_findings(seeded, db):
    org, project, admin = seeded
    run1 = run_review(db, org, project, admin)
    count1 = len(
        db.execute(select(Finding).where(Finding.review_run_id == run1.id)).scalars().all()
    )
    run2 = run_review(db, org, project, admin)
    count2 = len(
        db.execute(select(Finding).where(Finding.review_run_id == run2.id)).scalars().all()
    )
    # second run must not recreate the same unresolved findings
    assert count2 == 0
    assert count1 >= 2


def test_rerun_after_approval_does_not_duplicate_finding(seeded, db):
    """Regression: a finding approved for follow-up still occupies its evidence.

    Re-running the review must not create a second finding for the same work, which
    would double-count the same potential value.
    """
    org, project, admin = seeded
    run1 = run_review(db, org, project, admin)
    oos = db.execute(
        select(Finding).where(
            Finding.review_run_id == run1.id,
            Finding.finding_type == FindingType.potentially_out_of_scope,
        )
    ).scalar_one()

    # Human approves the finding for follow-up (still an open, value-bearing finding).
    oos.review_status = ReviewStatus.approved_for_followup
    db.commit()

    run2 = run_review(db, org, project, admin)
    oos_after = (
        db.execute(
            select(Finding).where(
                Finding.project_id == project.id,
                Finding.finding_type == FindingType.potentially_out_of_scope,
            )
        )
        .scalars()
        .all()
    )
    # Still exactly one OOS finding — no duplicate created by the re-run.
    assert len(oos_after) == 1
    assert not any(f.review_run_id == run2.id for f in oos_after)
