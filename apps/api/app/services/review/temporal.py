"""Deterministic temporal logic: contract precedence, effective windows, rate resolution.

Precedence (highest wins), matching the documented default order:
  change order > amendment > SOW > MSA > rate card > other.
Users can correct results by editing/superseding clauses; that human input always
takes precedence over inference.
"""

import uuid
from datetime import date

from app.models import Contract, ContractClause, RateRule
from app.models.enums import ContractStatus, DocumentType

DOCUMENT_PRECEDENCE: dict[DocumentType, int] = {
    DocumentType.change_order: 6,
    DocumentType.amendment: 5,
    DocumentType.statement_of_work: 4,
    DocumentType.master_service_agreement: 3,
    DocumentType.rate_card: 2,
    DocumentType.other: 1,
    DocumentType.customer_request: 0,
    DocumentType.invoice: 0,
}


def window_overlaps(start_a: date | None, end_a: date | None, start_b: date, end_b: date) -> bool:
    """Does [start_a, end_a] (None = open) overlap [start_b, end_b]?"""
    if start_a is not None and start_a > end_b:
        return False
    if end_a is not None and end_a < start_b:
        return False
    return True


def date_in_window(day: date, start: date | None, end: date | None) -> bool:
    if start is not None and day < start:
        return False
    if end is not None and day > end:
        return False
    return True


def contract_active_on(contract: Contract, day: date) -> bool:
    if contract.status in (ContractStatus.terminated,):
        return False
    return date_in_window(day, contract.effective_from, contract.effective_to)


def clause_applies(
    clause: ContractClause,
    contract: Contract,
    day: date,
    *,
    project_id: uuid.UUID | None = None,
) -> bool:
    """A clause applies only when: not rejected/superseded, its window covers the
    date, and its governing contract is active on that date and scoped to the
    project (contracts without a project_id apply client-wide)."""
    if clause.rejected or clause.superseded_by_clause_id is not None:
        return False
    if not date_in_window(day, clause.effective_from, clause.effective_to):
        return False
    if not contract_active_on(contract, day):
        return False
    if project_id is not None and contract.project_id is not None:
        if contract.project_id != project_id:
            return False
    return True


def resolve_rate(
    rates: list[tuple[RateRule, Contract, DocumentType | None]],
    role_name: str,
    work_day: date,
    *,
    require_verified: bool = True,
) -> RateRule | None:
    """Pick the applicable rate for a role on a given day.

    Candidates must match the role (case-insensitive), be effective on the date,
    and (by default) be human-verified. Among candidates, the highest governing-
    document precedence wins; ties break to the most recent effective_from.
    """
    role_key = role_name.strip().lower()
    candidates: list[tuple[int, date, RateRule]] = []
    for rate, contract, doc_type in rates:
        if rate.role_name.strip().lower() != role_key:
            continue
        if require_verified and not rate.human_verified:
            continue
        if not date_in_window(work_day, rate.effective_from, rate.effective_to):
            continue
        if not contract_active_on(contract, work_day):
            continue
        precedence = DOCUMENT_PRECEDENCE.get(doc_type, 1) if doc_type else 1
        candidates.append((precedence, rate.effective_from or date.min, rate))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return candidates[0][2]
