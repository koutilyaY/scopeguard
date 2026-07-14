"""Deterministic allowance consumption.

remaining = included − previously consumed eligible minutes (never below zero).
If work exceeds an allowance, only the excess is potentially billable.
"""

from dataclasses import dataclass
from datetime import date

from app.models import Allowance
from app.models.enums import AllowanceRecurrence


@dataclass
class AllowanceUsage:
    allowance_id: str
    included_minutes: int
    consumed_before_minutes: int
    applied_minutes: int  # minutes of *this* work absorbed by the allowance
    excess_minutes: int  # minutes of this work beyond the allowance
    period_label: str

    @property
    def remaining_before(self) -> int:
        return max(0, self.included_minutes - self.consumed_before_minutes)


def period_bounds_for(allowance: Allowance, day: date) -> tuple[date, date, str]:
    """The allowance period containing `day` (calendar month/quarter/year or total)."""
    if allowance.recurrence == AllowanceRecurrence.monthly:
        start = day.replace(day=1)
        end = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
        return start, end, f"{start:%B %Y}"
    if allowance.recurrence == AllowanceRecurrence.quarterly:
        quarter = (day.month - 1) // 3
        start = date(day.year, quarter * 3 + 1, 1)
        end = date(day.year + 1, 1, 1) if quarter == 3 else date(day.year, quarter * 3 + 4, 1)
        return start, end, f"Q{quarter + 1} {day.year}"
    if allowance.recurrence == AllowanceRecurrence.annual:
        return date(day.year, 1, 1), date(day.year + 1, 1, 1), str(day.year)
    # total: entire allowance effectivity window
    start = allowance.effective_from or date.min
    end = allowance.effective_to or date.max
    return start, end, "entire engagement"


def apply_allowance(
    allowance: Allowance,
    consumed_before_minutes: int,
    new_work_minutes: int,
    day: date,
) -> AllowanceUsage:
    """Split new work into allowance-covered minutes and billable excess."""
    if new_work_minutes < 0 or consumed_before_minutes < 0:
        raise ValueError("minutes must be non-negative")
    _, _, label = period_bounds_for(allowance, day)
    remaining = max(0, allowance.included_quantity - consumed_before_minutes)
    applied = min(remaining, new_work_minutes)
    excess = new_work_minutes - applied
    return AllowanceUsage(
        allowance_id=str(allowance.id),
        included_minutes=allowance.included_quantity,
        consumed_before_minutes=consumed_before_minutes,
        applied_minutes=applied,
        excess_minutes=excess,
        period_label=label,
    )
