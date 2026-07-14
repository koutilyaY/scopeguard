"""Contract precedence, effective windows, rate resolution."""

import uuid
from datetime import date

from app.models import Contract, ContractClause, RateRule
from app.models.enums import ClauseType, ContractStatus, DocumentType
from app.services.review.temporal import (
    clause_applies,
    date_in_window,
    resolve_rate,
    window_overlaps,
)

ORG = uuid.uuid4()
CLIENT = uuid.uuid4()
PROJECT = uuid.uuid4()


def make_contract(
    effective_from=date(2025, 1, 1),
    effective_to=date(2025, 12, 31),
    status=ContractStatus.active,
    project_id=PROJECT,
) -> Contract:
    return Contract(
        id=uuid.uuid4(),
        organization_id=ORG,
        client_id=CLIENT,
        project_id=project_id,
        title="test",
        effective_from=effective_from,
        effective_to=effective_to,
        currency="USD",
        status=status,
    )


def make_clause(contract, effective_from=None, effective_to=None, **kwargs) -> ContractClause:
    return ContractClause(
        id=uuid.uuid4(),
        organization_id=ORG,
        contract_id=contract.id,
        clause_type=ClauseType.excluded_service,
        title="c",
        source_text="text",
        effective_from=effective_from,
        effective_to=effective_to,
        human_verified=True,
        rejected=kwargs.get("rejected", False),
        superseded_by_clause_id=kwargs.get("superseded_by_clause_id"),
    )


def make_rate(
    contract,
    role="Data Engineer",
    rate_minor=17500,
    effective_from=None,
    effective_to=None,
    verified=True,
) -> RateRule:
    return RateRule(
        id=uuid.uuid4(),
        organization_id=ORG,
        contract_id=contract.id,
        role_name=role,
        hourly_rate_minor=rate_minor,
        currency="USD",
        effective_from=effective_from,
        effective_to=effective_to,
        human_verified=verified,
    )


class TestWindows:
    def test_overlap_open_ended(self):
        assert window_overlaps(None, None, date(2025, 6, 1), date(2025, 6, 30))

    def test_no_overlap_before(self):
        assert not window_overlaps(
            date(2025, 1, 1), date(2025, 5, 31), date(2025, 6, 1), date(2025, 6, 30)
        )

    def test_date_in_window_bounds_inclusive(self):
        assert date_in_window(date(2025, 6, 1), date(2025, 6, 1), date(2025, 6, 30))
        assert date_in_window(date(2025, 6, 30), date(2025, 6, 1), date(2025, 6, 30))
        assert not date_in_window(date(2025, 7, 1), date(2025, 6, 1), date(2025, 6, 30))


class TestClauseApplies:
    def test_applies_in_window(self):
        contract = make_contract()
        clause = make_clause(contract)
        assert clause_applies(clause, contract, date(2025, 6, 15), project_id=PROJECT)

    def test_expired_sow_does_not_apply(self):
        contract = make_contract(effective_to=date(2025, 5, 31))
        clause = make_clause(contract)
        assert not clause_applies(clause, contract, date(2025, 6, 15), project_id=PROJECT)

    def test_work_before_contract_effective_date(self):
        contract = make_contract(effective_from=date(2025, 6, 1))
        clause = make_clause(contract)
        assert not clause_applies(clause, contract, date(2025, 5, 15), project_id=PROJECT)

    def test_superseded_clause_does_not_apply(self):
        contract = make_contract()
        clause = make_clause(contract, superseded_by_clause_id=uuid.uuid4())
        assert not clause_applies(clause, contract, date(2025, 6, 15), project_id=PROJECT)

    def test_rejected_clause_does_not_apply(self):
        contract = make_contract()
        clause = make_clause(contract, rejected=True)
        assert not clause_applies(clause, contract, date(2025, 6, 15), project_id=PROJECT)

    def test_terminated_contract_clause_does_not_apply(self):
        contract = make_contract(status=ContractStatus.terminated)
        clause = make_clause(contract)
        assert not clause_applies(clause, contract, date(2025, 6, 15), project_id=PROJECT)

    def test_amendment_scoped_to_other_project_does_not_apply(self):
        other_project = uuid.uuid4()
        contract = make_contract(project_id=other_project)
        clause = make_clause(contract)
        assert not clause_applies(clause, contract, date(2025, 6, 15), project_id=PROJECT)

    def test_client_wide_contract_applies_to_any_project(self):
        contract = make_contract(project_id=None)
        clause = make_clause(contract)
        assert clause_applies(clause, contract, date(2025, 6, 15), project_id=PROJECT)


class TestRateResolution:
    def test_rate_change_mid_period(self):
        """A rate change halfway through a billing period resolves per work date."""
        sow = make_contract()
        amendment = make_contract(effective_from=date(2025, 6, 16))
        old_rate = make_rate(sow, rate_minor=17500, effective_to=date(2025, 6, 15))
        new_rate = make_rate(amendment, rate_minor=18500, effective_from=date(2025, 6, 16))
        rates = [
            (old_rate, sow, DocumentType.statement_of_work),
            (new_rate, amendment, DocumentType.amendment),
        ]
        assert resolve_rate(rates, "Data Engineer", date(2025, 6, 10)).hourly_rate_minor == 17500
        assert resolve_rate(rates, "Data Engineer", date(2025, 6, 20)).hourly_rate_minor == 18500

    def test_precedence_change_order_beats_amendment(self):
        amendment = make_contract()
        change_order = make_contract()
        rate_a = make_rate(amendment, rate_minor=18500)
        rate_co = make_rate(change_order, rate_minor=19500)
        rates = [
            (rate_a, amendment, DocumentType.amendment),
            (rate_co, change_order, DocumentType.change_order),
        ]
        assert resolve_rate(rates, "Data Engineer", date(2025, 6, 20)).hourly_rate_minor == 19500

    def test_two_conflicting_amendments_latest_effective_wins(self):
        amendment1 = make_contract(effective_from=date(2025, 3, 1))
        amendment2 = make_contract(effective_from=date(2025, 5, 1))
        rate1 = make_rate(amendment1, rate_minor=18000, effective_from=date(2025, 3, 1))
        rate2 = make_rate(amendment2, rate_minor=19000, effective_from=date(2025, 5, 1))
        rates = [
            (rate1, amendment1, DocumentType.amendment),
            (rate2, amendment2, DocumentType.amendment),
        ]
        assert resolve_rate(rates, "Data Engineer", date(2025, 6, 1)).hourly_rate_minor == 19000

    def test_unverified_rate_excluded_by_default(self):
        contract = make_contract()
        rate = make_rate(contract, verified=False)
        assert (
            resolve_rate(
                [(rate, contract, DocumentType.statement_of_work)],
                "Data Engineer",
                date(2025, 6, 1),
            )
            is None
        )

    def test_unknown_role_returns_none(self):
        contract = make_contract()
        rate = make_rate(contract)
        assert (
            resolve_rate(
                [(rate, contract, DocumentType.statement_of_work)], "Astrologer", date(2025, 6, 1)
            )
            is None
        )

    def test_role_match_is_case_insensitive(self):
        contract = make_contract()
        rate = make_rate(contract, role="data engineer")
        resolved = resolve_rate(
            [(rate, contract, DocumentType.statement_of_work)], "Data Engineer", date(2025, 6, 1)
        )
        assert resolved is rate

    def test_work_outside_contract_dates_gets_no_rate(self):
        contract = make_contract(effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31))
        rate = make_rate(contract)
        assert (
            resolve_rate(
                [(rate, contract, DocumentType.statement_of_work)],
                "Data Engineer",
                date(2026, 1, 15),
            )
            is None
        )
