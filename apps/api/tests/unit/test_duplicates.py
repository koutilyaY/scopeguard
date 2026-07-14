"""Duplicate detection on transient TimeEntry objects (no database needed)."""

import uuid
from datetime import UTC, date, datetime

from app.models import TimeEntry
from app.models.enums import BillableStatus
from app.services.review.duplicates import (
    find_duplicates,
    normalize_description,
    time_entry_content_hash,
)

PROJECT_ID = uuid.uuid4()


def make_entry(
    employee: str,
    day: date,
    minutes: int,
    description: str,
    created_offset: int = 0,
) -> TimeEntry:
    entry = TimeEntry(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        project_id=PROJECT_ID,
        employee_name=employee,
        work_date=day,
        minutes=minutes,
        description=description,
        billable_status=BillableStatus.unknown,
        source="test",
        content_hash=time_entry_content_hash(
            str(PROJECT_ID), employee, str(day), minutes, description
        ),
    )
    entry.created_at = datetime(2025, 6, 1, 12, 0, created_offset, tzinfo=UTC)
    return entry


def test_exact_duplicate_detected_and_excluded():
    a = make_entry("Marco Diaz", date(2025, 6, 10), 480, "Salesforce sync build", 0)
    b = make_entry("Marco Diaz", date(2025, 6, 10), 480, "Salesforce sync build", 1)
    analysis = find_duplicates([a, b])
    assert analysis.excluded_entry_ids == {str(b.id)}
    assert len(analysis.groups) == 1
    assert analysis.groups[0].kind == "exact"
    assert analysis.groups[0].kept_entry_id == str(a.id)


def test_exact_duplicate_ignores_case_and_whitespace():
    a = make_entry("Marco Diaz", date(2025, 6, 10), 480, "Salesforce  Sync Build", 0)
    b = make_entry("Marco Diaz", date(2025, 6, 10), 480, "salesforce sync build", 1)
    assert a.content_hash == b.content_hash
    analysis = find_duplicates([a, b])
    assert len(analysis.excluded_entry_ids) == 1


def test_fuzzy_duplicate_same_key_similar_description():
    a = make_entry("Priya Raman", date(2025, 6, 9), 420, "Salesforce object schema mapping", 0)
    b = make_entry("Priya Raman", date(2025, 6, 9), 420, "Salesforce object schema mapping.", 1)
    analysis = find_duplicates([a, b])
    assert str(b.id) in analysis.excluded_entry_ids
    assert analysis.groups[0].kind in ("exact", "fuzzy")


def test_different_days_not_duplicates():
    a = make_entry("Priya Raman", date(2025, 6, 9), 420, "schema mapping", 0)
    b = make_entry("Priya Raman", date(2025, 6, 10), 420, "schema mapping", 1)
    analysis = find_duplicates([a, b])
    assert analysis.excluded_entry_ids == set()


def test_different_descriptions_not_fuzzy_duplicates():
    a = make_entry("Priya Raman", date(2025, 6, 9), 420, "Salesforce auth setup", 0)
    b = make_entry("Priya Raman", date(2025, 6, 9), 420, "Zendesk incident response", 1)
    analysis = find_duplicates([a, b])
    assert analysis.excluded_entry_ids == set()


def test_triple_duplicate_keeps_earliest_only():
    a = make_entry("Marco Diaz", date(2025, 6, 10), 480, "sync build", 0)
    b = make_entry("Marco Diaz", date(2025, 6, 10), 480, "sync build", 1)
    c = make_entry("Marco Diaz", date(2025, 6, 10), 480, "sync build", 2)
    analysis = find_duplicates([c, a, b])  # order-independent
    assert analysis.excluded_entry_ids == {str(b.id), str(c.id)}


def test_normalize_description():
    assert normalize_description("  Fix   THE bug\n") == "fix the bug"
    assert normalize_description(None) == ""
