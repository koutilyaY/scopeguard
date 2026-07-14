"""Deterministic monetary calculations. LLMs never touch these numbers.

All amounts are integer minor units (cents). Intermediate math uses Decimal with
explicit ROUND_HALF_UP. Currencies are never mixed: helpers raise if asked to
combine amounts in different currencies.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


class CurrencyMismatchError(ValueError):
    pass


def minutes_to_value_minor(minutes: int, hourly_rate_minor: int) -> int:
    """value = minutes / 60 × rate, rounded half-up to the nearest minor unit."""
    if minutes < 0:
        raise ValueError("minutes must be non-negative")
    if hourly_rate_minor < 0:
        raise ValueError("rate must be non-negative")
    value = Decimal(minutes) * Decimal(hourly_rate_minor) / Decimal(60)
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_minor(amount_minor: int, currency: str) -> str:
    major = Decimal(amount_minor) / Decimal(100)
    return f"{currency} {major:,.2f}"


@dataclass
class MoneyTotal:
    """Single-currency accumulator that refuses to mix currencies."""

    currency: str | None = None
    amount_minor: int = 0

    def add(self, amount_minor: int, currency: str) -> None:
        if self.currency is None:
            self.currency = currency
        elif self.currency != currency:
            raise CurrencyMismatchError(
                f"Cannot combine {currency} with existing total in {self.currency}"
            )
        self.amount_minor += amount_minor
