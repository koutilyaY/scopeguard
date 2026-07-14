"""Existing-invoice reconciliation.

Work already represented on issued/paid/approved-draft invoices is subtracted from
potential findings. Void invoices are NOT treated as billed. Plain draft invoices
are also not treated as billed (they are unapproved).
"""

import uuid
from dataclasses import dataclass, field

from app.models import Invoice, InvoiceLine
from app.models.enums import InvoiceStatus

BILLED_STATUSES = {InvoiceStatus.issued, InvoiceStatus.paid, InvoiceStatus.approved_draft}


@dataclass
class ReconciliationResult:
    billed_work_item_ids: set[uuid.UUID] = field(default_factory=set)
    billed_time_entry_ids: set[uuid.UUID] = field(default_factory=set)
    matches: list[dict] = field(default_factory=list)  # explainable trace


def reconcile_invoices(
    invoices: list[Invoice],
    lines: list[InvoiceLine],
) -> ReconciliationResult:
    """Collect work items and time entries already represented on billed invoices."""
    billed_invoice_ids = {inv.id for inv in invoices if inv.status in BILLED_STATUSES}
    result = ReconciliationResult()
    for line in lines:
        if line.invoice_id not in billed_invoice_ids:
            continue
        if line.linked_work_item_id is not None:
            result.billed_work_item_ids.add(line.linked_work_item_id)
            result.matches.append(
                {
                    "invoice_line_id": str(line.id),
                    "invoice_id": str(line.invoice_id),
                    "matched": "work_item",
                    "entity_id": str(line.linked_work_item_id),
                    "description": line.description,
                }
            )
        if line.linked_time_entry_id is not None:
            result.billed_time_entry_ids.add(line.linked_time_entry_id)
            result.matches.append(
                {
                    "invoice_line_id": str(line.id),
                    "invoice_id": str(line.invoice_id),
                    "matched": "time_entry",
                    "entity_id": str(line.linked_time_entry_id),
                    "description": line.description,
                }
            )
    return result
