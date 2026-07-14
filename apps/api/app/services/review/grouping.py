"""Deterministic work grouping.

Evidence is grouped by explainable keys so the LLM classifies coherent units of
work instead of individual timesheet rows. A time entry belongs to exactly one
group, so no entry is double-counted across financial findings.
"""

import hashlib
import uuid
from dataclasses import dataclass, field

from app.models import CustomerRequest, TimeEntry, WorkItem


@dataclass
class WorkGroup:
    key: str  # human-readable grouping key
    work_items: list[WorkItem] = field(default_factory=list)
    time_entries: list[TimeEntry] = field(default_factory=list)
    customer_requests: list[CustomerRequest] = field(default_factory=list)
    rationale: str = ""

    @property
    def total_minutes(self) -> int:
        return sum(e.minutes for e in self.time_entries)

    @property
    def dedup_key(self) -> str:
        """Stable identity for finding deduplication across review runs."""
        parts = sorted(str(w.id) for w in self.work_items) + sorted(
            str(t.id) for t in self.time_entries
        )
        return hashlib.sha256("|".join(parts).encode()).hexdigest()


def group_evidence(
    work_items: list[WorkItem],
    time_entries: list[TimeEntry],
    customer_requests: list[CustomerRequest],
) -> list[WorkGroup]:
    """Group by work item; entries without a work item fall into a per-employee-role
    ungrouped bucket. Customer requests attach to groups via linked_work_item_id."""
    groups: dict[str, WorkGroup] = {}
    items_by_id: dict[uuid.UUID, WorkItem] = {w.id: w for w in work_items}

    for item in work_items:
        key = f"work_item:{item.external_id}"
        groups[key] = WorkGroup(
            key=key,
            work_items=[item],
            rationale=f"All evidence linked to work item {item.external_id} ({item.title}).",
        )

    for entry in time_entries:
        if entry.work_item_id and entry.work_item_id in items_by_id:
            key = f"work_item:{items_by_id[entry.work_item_id].external_id}"
            groups[key].time_entries.append(entry)
        else:
            role = (entry.employee_role or "unspecified").strip().lower()
            key = f"unlinked:{role}"
            if key not in groups:
                groups[key] = WorkGroup(
                    key=key,
                    rationale=(f"Time entries with no linked work item, grouped by role '{role}'."),
                )
            groups[key].time_entries.append(entry)

    for request in customer_requests:
        attached = False
        if request.linked_work_item_id and request.linked_work_item_id in items_by_id:
            key = f"work_item:{items_by_id[request.linked_work_item_id].external_id}"
            groups[key].customer_requests.append(request)
            attached = True
        if not attached:
            # keep unattached requests visible to every group's classification later
            continue

    # drop empty groups (a work item with no time and no requests still matters, keep it)
    return [g for g in groups.values() if g.work_items or g.time_entries]
