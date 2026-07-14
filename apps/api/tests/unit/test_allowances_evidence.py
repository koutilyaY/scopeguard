"""Allowance consumption and evidence scoring."""

import uuid
from datetime import date

import pytest

from app.models import Allowance
from app.models.enums import AllowanceRecurrence, AllowanceType
from app.services.review.allowances import apply_allowance, period_bounds_for
from app.services.review.evidence import DEFAULT_WEIGHTS, score_evidence


def make_allowance(minutes: int, recurrence=AllowanceRecurrence.monthly) -> Allowance:
    return Allowance(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        contract_id=uuid.uuid4(),
        allowance_type=AllowanceType.support_hours,
        included_quantity=minutes,
        unit="minutes",
        recurrence=recurrence,
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
    )


class TestAllowance:
    def test_work_within_allowance(self):
        allowance = make_allowance(20 * 60)
        usage = apply_allowance(allowance, 0, 600, date(2025, 6, 15))
        assert usage.applied_minutes == 600
        assert usage.excess_minutes == 0

    def test_exhaustion_only_excess_billable(self):
        allowance = make_allowance(20 * 60)
        usage = apply_allowance(allowance, 900, 600, date(2025, 6, 15))
        # remaining = 1200 - 900 = 300; applied 300, excess 300
        assert usage.applied_minutes == 300
        assert usage.excess_minutes == 300

    def test_already_exhausted(self):
        allowance = make_allowance(20 * 60)
        usage = apply_allowance(allowance, 1300, 240, date(2025, 6, 15))
        assert usage.applied_minutes == 0
        assert usage.excess_minutes == 240

    def test_negative_rejected(self):
        allowance = make_allowance(1200)
        with pytest.raises(ValueError):
            apply_allowance(allowance, -1, 100, date(2025, 6, 15))

    def test_monthly_period_bounds(self):
        allowance = make_allowance(1200)
        start, end, label = period_bounds_for(allowance, date(2025, 6, 15))
        assert start == date(2025, 6, 1)
        assert end == date(2025, 7, 1)
        assert "June" in label

    def test_december_rollover(self):
        allowance = make_allowance(1200)
        start, end, _ = period_bounds_for(allowance, date(2025, 12, 5))
        assert end == date(2026, 1, 1)

    def test_quarterly_bounds(self):
        allowance = make_allowance(1200, AllowanceRecurrence.quarterly)
        start, end, label = period_bounds_for(allowance, date(2025, 5, 10))
        assert start == date(2025, 4, 1)
        assert end == date(2025, 7, 1)
        assert label == "Q2 2025"


class TestEvidenceScore:
    def test_weights_sum_to_one(self):
        assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9

    def test_full_evidence_scores_one(self):
        score = score_evidence(
            has_verified_clause=True,
            has_work_item=True,
            has_time_entries=True,
            has_customer_request=True,
            has_verified_rate=True,
            absent_from_invoices=True,
            has_written_authorization=True,
            work_completed=True,
        )
        assert score.score == 1.0

    def test_no_evidence_scores_zero(self):
        score = score_evidence(
            has_verified_clause=False,
            has_work_item=False,
            has_time_entries=False,
            has_customer_request=False,
            has_verified_rate=False,
            absent_from_invoices=False,
            has_written_authorization=False,
            work_completed=False,
        )
        assert score.score == 0.0

    def test_breakdown_is_transparent_and_labelled(self):
        score = score_evidence(
            has_verified_clause=True,
            has_work_item=True,
            has_time_entries=True,
            has_customer_request=True,
            has_verified_rate=True,
            absent_from_invoices=True,
            has_written_authorization=False,
            work_completed=True,
        )
        breakdown = score.breakdown()
        assert breakdown["label"] == "Evidence completeness"
        assert "not a legal probability" in breakdown["disclaimer"].lower()
        contributions = {c["component"]: c["contribution"] for c in breakdown["components"]}
        assert contributions["written_authorization"] == 0.0
        assert score.score == pytest.approx(0.95)
