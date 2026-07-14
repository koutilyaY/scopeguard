"""Deterministic duplicate detection for time entries.

Exact duplicates: identical (employee, date, minutes, normalized description).
Fuzzy duplicates: same employee + date + minutes with highly similar descriptions.
No LLM involvement — results are reproducible and explainable.
"""

import hashlib
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.models import TimeEntry

FUZZY_SIMILARITY_THRESHOLD = 0.9


def normalize_description(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def time_entry_content_hash(
    project_id: str, employee_name: str, work_date: str, minutes: int, description: str | None
) -> str:
    """Stable hash of the fields that define an exact duplicate."""
    payload = "|".join(
        [
            str(project_id),
            employee_name.strip().lower(),
            str(work_date),
            str(minutes),
            normalize_description(description),
        ]
    )
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass
class DuplicateGroup:
    kind: str  # "exact" | "fuzzy"
    kept_entry_id: str
    duplicate_entry_ids: list[str]
    explanation: str


@dataclass
class DuplicateAnalysis:
    groups: list[DuplicateGroup] = field(default_factory=list)
    # entries excluded from any financial aggregate (the *duplicates*, not the kept rows)
    excluded_entry_ids: set[str] = field(default_factory=set)


def find_duplicates(entries: list[TimeEntry]) -> DuplicateAnalysis:
    """Detect exact and fuzzy duplicates within a set of time entries.

    The earliest-created entry in each duplicate cluster is kept; the rest are
    excluded from financial aggregation.
    """
    analysis = DuplicateAnalysis()
    ordered = sorted(entries, key=lambda e: (e.created_at, str(e.id)))

    # --- exact duplicates by content hash ---
    by_hash: dict[str, list[TimeEntry]] = {}
    for entry in ordered:
        by_hash.setdefault(entry.content_hash, []).append(entry)

    exact_dupes: set[str] = set()
    for cluster in by_hash.values():
        if len(cluster) > 1:
            kept, *dupes = cluster
            dupe_ids = [str(d.id) for d in dupes]
            exact_dupes.update(dupe_ids)
            analysis.groups.append(
                DuplicateGroup(
                    kind="exact",
                    kept_entry_id=str(kept.id),
                    duplicate_entry_ids=dupe_ids,
                    explanation=(
                        f"{len(dupes)} entr{'y' if len(dupes) == 1 else 'ies'} identical to the "
                        f"kept entry ({kept.employee_name}, {kept.work_date}, "
                        f"{kept.minutes} min, same description)."
                    ),
                )
            )
    analysis.excluded_entry_ids.update(exact_dupes)

    # --- fuzzy duplicates: same employee/date/minutes, similar description ---
    remaining = [e for e in ordered if str(e.id) not in exact_dupes]
    by_key: dict[tuple, list[TimeEntry]] = {}
    for entry in remaining:
        key = (entry.employee_name.strip().lower(), entry.work_date, entry.minutes)
        by_key.setdefault(key, []).append(entry)

    for cluster in by_key.values():
        if len(cluster) < 2:
            continue
        kept = cluster[0]
        kept_desc = normalize_description(kept.description)
        fuzzy_ids = []
        for candidate in cluster[1:]:
            cand_desc = normalize_description(candidate.description)
            similarity = SequenceMatcher(None, kept_desc, cand_desc).ratio()
            if similarity >= FUZZY_SIMILARITY_THRESHOLD:
                fuzzy_ids.append(str(candidate.id))
        if fuzzy_ids:
            analysis.excluded_entry_ids.update(fuzzy_ids)
            analysis.groups.append(
                DuplicateGroup(
                    kind="fuzzy",
                    kept_entry_id=str(kept.id),
                    duplicate_entry_ids=fuzzy_ids,
                    explanation=(
                        f"Same employee, date and duration as the kept entry with ≥"
                        f"{int(FUZZY_SIMILARITY_THRESHOLD * 100)}% description similarity."
                    ),
                )
            )
    return analysis
