"""Deterministic money math."""

import pytest

from app.services.review.money import (
    CurrencyMismatchError,
    MoneyTotal,
    format_minor,
    minutes_to_value_minor,
)


class TestMinutesToValue:
    def test_whole_hours(self):
        assert minutes_to_value_minor(120, 17500) == 35000  # 2h × $175

    def test_fractional_hour_rounds_half_up(self):
        # 50 min × $175/h = 145.833… → 14583.33 minor → 14583
        assert minutes_to_value_minor(50, 17500) == 14583

    def test_rounding_half_up_boundary(self):
        # 30 min × $0.01/h = 0.5 minor → rounds up to 1
        assert minutes_to_value_minor(30, 1) == 1

    def test_zero_minutes(self):
        assert minutes_to_value_minor(0, 17500) == 0

    def test_negative_minutes_rejected(self):
        with pytest.raises(ValueError):
            minutes_to_value_minor(-10, 17500)

    def test_negative_rate_rejected(self):
        with pytest.raises(ValueError):
            minutes_to_value_minor(10, -5)

    def test_demo_scenario_34_hours_split_rates(self):
        """21h @ $175 + 13h @ $185 = $6,080.00 exactly."""
        before = minutes_to_value_minor(21 * 60, 17500)
        after = minutes_to_value_minor(13 * 60, 18500)
        assert before == 367_500
        assert after == 240_500
        assert before + after == 608_000

    def test_no_floating_point_drift(self):
        # 1 minute at $175/h → 291.666... cents → 292
        assert minutes_to_value_minor(1, 17500) == 292
        # Sum of 60 one-minute entries ≠ one 60-minute entry (documented rounding
        # semantics: rounding happens per aggregation call, not per minute)
        assert minutes_to_value_minor(60, 17500) == 17500


class TestMoneyTotal:
    def test_accumulates_single_currency(self):
        total = MoneyTotal()
        total.add(100, "USD")
        total.add(250, "USD")
        assert total.amount_minor == 350
        assert total.currency == "USD"

    def test_rejects_mixed_currencies(self):
        total = MoneyTotal()
        total.add(100, "USD")
        with pytest.raises(CurrencyMismatchError):
            total.add(100, "EUR")


def test_format_minor():
    assert format_minor(608_000, "USD") == "USD 6,080.00"
