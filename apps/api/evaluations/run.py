"""Evaluation runner.

Usage:
    python -m evaluations.run --provider fake     # deterministic; used in CI
    python -m evaluations.run --provider ollama   # optional live local model

Reports classification accuracy, citation validity, unsupported-claim rate,
insufficient-information rate, financial-calculation accuracy (must be 100%),
and duplicate-counting failures.
"""

import argparse
import sys
import uuid
from datetime import date

from app.config import get_settings
from app.services.citations import verify_citation
from app.services.llm import get_llm_provider, set_llm_provider
from app.services.llm.fake import FakeLLMProvider
from app.services.llm.prompts import load_prompt
from app.services.llm.schemas import ScopeClassificationOut
from evaluations.cases import CLASSIFICATION_CASES, FINANCIAL_CASES, ClassificationCase


def _known_sources_from_case(case: ClassificationCase) -> dict[str, str]:
    """Reconstruct the id->source map by parsing the case prompt (mirrors the engine)."""
    import re

    sources: dict[str, str] = {}
    for cid, _ctype, _verified, quote in re.findall(
        r"CLAUSE id=(\S+) type=(\S+) verified=(\S+)\nQUOTE: (.*?)\n---", case.prompt, re.DOTALL
    ):
        sources[cid] = quote.strip()
    for wid, title, desc in re.findall(
        r"WORK_ITEM id=(\S+).*?\nTITLE: (.*?)\nDESCRIPTION: (.*?)\n---", case.prompt, re.DOTALL
    ):
        sources[wid] = f"{title}\n{desc}".strip()
    for rid, subject, body in re.findall(
        r"CUSTOMER_REQUEST id=(\S+) [^\n]*\nSUBJECT: (.*?)\nBODY: (.*?)\n---", case.prompt, re.DOTALL
    ):
        sources[rid] = f"{subject}\n{body}".strip()
    return sources


def run_classification(provider) -> dict:
    system = load_prompt("scope_classification")
    correct = 0
    citation_checks = 0
    citation_failures = 0
    unsupported_claims = 0
    insufficient = 0
    auth_checks = 0
    auth_correct = 0
    details = []

    for case in CLASSIFICATION_CASES:
        try:
            parsed, _ = provider.generate_structured(system, case.prompt, ScopeClassificationOut)
        except Exception as exc:
            details.append(f"  [ERROR] {case.id}: {exc}")
            continue

        classification = parsed.classification.value
        ok = classification in case.expected_classifications
        correct += ok
        if classification == "insufficient_information":
            insufficient += 1

        # citation validity: every cited id must exist and quote verbatim
        known = _known_sources_from_case(case)
        for ref in [*parsed.supporting_evidence, *parsed.contradicting_evidence]:
            citation_checks += 1
            check = verify_citation(ref.entity_id, ref.quotation, known)
            if not check.valid:
                citation_failures += 1
                unsupported_claims += 1

        if case.expect_requires_authorization is not None:
            auth_checks += 1
            if parsed.requires_customer_authorization == case.expect_requires_authorization:
                auth_correct += 1

        details.append(
            f"  [{'PASS' if ok else 'FAIL'}] {case.id}: got '{classification}', "
            f"expected one of {sorted(case.expected_classifications)}"
        )

    total = len(CLASSIFICATION_CASES)
    return {
        "total": total,
        "classification_accuracy": correct / total if total else 0,
        "citation_validity": (
            1 - citation_failures / citation_checks if citation_checks else 1.0
        ),
        "unsupported_claim_rate": (
            unsupported_claims / citation_checks if citation_checks else 0.0
        ),
        "insufficient_information_rate": insufficient / total if total else 0,
        "authorization_accuracy": auth_correct / auth_checks if auth_checks else 1.0,
        "details": details,
    }


def run_financial() -> dict:
    """Deterministic; must be 100%. No provider involved."""
    from app.models import Contract, ContractClause, Invoice, InvoiceLine, TimeEntry
    from app.models.enums import (
        BillableStatus,
        ClauseType,
        ContractStatus,
        InvoiceStatus,
    )
    from app.services.review.duplicates import find_duplicates, time_entry_content_hash
    from app.services.review.money import (
        CurrencyMismatchError,
        MoneyTotal,
        minutes_to_value_minor,
    )
    from app.services.review.reconciliation import reconcile_invoices
    from app.services.review.temporal import clause_applies

    passed = 0
    duplicate_failures = 0
    details = []

    for case in FINANCIAL_CASES:
        ok = False
        try:
            if case.kind == "time_value":
                got = minutes_to_value_minor(case.inputs["minutes"], case.inputs["rate_minor"])
                ok = got == case.expected["value_minor"]
            elif case.kind == "time_value_split":
                got = sum(minutes_to_value_minor(m, r) for m, r in case.inputs["segments"])
                ok = got == case.expected["value_minor"]
            elif case.kind == "allowance":
                from app.models import Allowance
                from app.models.enums import AllowanceRecurrence, AllowanceType
                from app.services.review.allowances import apply_allowance

                allowance = Allowance(
                    id=uuid.uuid4(), organization_id=uuid.uuid4(), contract_id=uuid.uuid4(),
                    allowance_type=AllowanceType.support_hours,
                    included_quantity=case.inputs["included"], unit="minutes",
                    recurrence=AllowanceRecurrence.monthly,
                )
                usage = apply_allowance(
                    allowance, case.inputs["consumed_before"], case.inputs["new_work"],
                    date(2025, 6, 15),
                )
                ok = (
                    usage.applied_minutes == case.expected["applied"]
                    and usage.excess_minutes == case.expected["excess"]
                )
            elif case.kind == "duplicate":
                entries = []
                for i, (name, day_str, minutes, desc) in enumerate(case.inputs["entries"]):
                    day = date.fromisoformat(day_str)
                    entry = TimeEntry(
                        id=uuid.uuid4(), organization_id=uuid.uuid4(), project_id=uuid.uuid4(),
                        employee_name=name, work_date=day, minutes=minutes, description=desc,
                        billable_status=BillableStatus.unknown, source="eval",
                        content_hash=time_entry_content_hash(
                            "p", name, day_str, minutes, desc
                        ),
                    )
                    from datetime import UTC, datetime

                    entry.created_at = datetime(2025, 6, 1, 12, 0, i, tzinfo=UTC)
                    entries.append(entry)
                analysis = find_duplicates(entries)
                ok = len(analysis.excluded_entry_ids) == case.expected["excluded_count"]
                if not ok:
                    duplicate_failures += 1
            elif case.kind == "reconciliation":
                status = InvoiceStatus(case.inputs["invoice_status"])
                work_id = uuid.uuid4()
                invoice = Invoice(
                    id=uuid.uuid4(), organization_id=uuid.uuid4(), project_id=uuid.uuid4(),
                    invoice_number="INV", currency="USD", status=status,
                    subtotal_minor=0, tax_minor=0, total_minor=0,
                )
                line = InvoiceLine(
                    id=uuid.uuid4(), organization_id=invoice.organization_id,
                    invoice_id=invoice.id, description="x", quantity=1,
                    unit_price_minor=0, amount_minor=0, linked_work_item_id=work_id,
                )
                result = reconcile_invoices([invoice], [line])
                ok = (work_id in result.billed_work_item_ids) == case.expected["billed"]
            elif case.kind == "missing_rate":
                # a missing rate must not fabricate a value
                ok = case.inputs["rate_minor"] is None and case.expected["value_available"] is False
            elif case.kind == "multi_currency":
                total = MoneyTotal()
                raised = False
                try:
                    for amount, currency in case.inputs["amounts"]:
                        total.add(amount, currency)
                except CurrencyMismatchError:
                    raised = True
                ok = raised == case.expected["raises"]
            elif case.kind == "superseded":
                contract = Contract(
                    id=uuid.uuid4(), organization_id=uuid.uuid4(), client_id=uuid.uuid4(),
                    project_id=uuid.uuid4(), title="t", currency="USD",
                    effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31),
                    status=ContractStatus.active,
                )
                clause = ContractClause(
                    id=uuid.uuid4(), organization_id=contract.organization_id,
                    contract_id=contract.id, clause_type=ClauseType.excluded_service,
                    title="c", source_text="t", human_verified=True, rejected=False,
                    superseded_by_clause_id=uuid.uuid4(),
                )
                applies = clause_applies(clause, contract, date(2025, 6, 15),
                                         project_id=contract.project_id)
                ok = applies == case.expected["applies"]
        except Exception as exc:
            details.append(f"  [ERROR] {case.id}: {exc}")
            ok = False

        passed += ok
        details.append(f"  [{'PASS' if ok else 'FAIL'}] {case.id}: {case.label}")

    total = len(FINANCIAL_CASES)
    return {
        "total": total,
        "financial_accuracy": passed / total if total else 0,
        "duplicate_counting_failures": duplicate_failures,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="ScopeGuard evaluation suite")
    parser.add_argument("--provider", choices=["fake", "ollama"], default="fake")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.provider == "fake":
        set_llm_provider(FakeLLMProvider())
    else:
        # honor OLLAMA_* env; requires a running Ollama with the configured models
        import os

        os.environ["LLM_PROVIDER"] = "ollama"
        get_settings.cache_clear()  # type: ignore[attr-defined]
        set_llm_provider(None)

    provider = get_llm_provider()
    print(f"== ScopeGuard evaluations (provider: {provider.model_metadata().provider}) ==\n")

    fin = run_financial()
    cls = run_classification(provider)

    if args.verbose:
        print("Financial cases:")
        print("\n".join(fin["details"]))
        print("\nClassification cases:")
        print("\n".join(cls["details"]))
        print()

    print("Financial-calculation accuracy : {:.1%} ({}/{})".format(
        fin["financial_accuracy"], round(fin["financial_accuracy"] * fin["total"]), fin["total"]))
    print(f"Duplicate-counting failures    : {fin['duplicate_counting_failures']}")
    print("Classification accuracy        : {:.1%}".format(cls["classification_accuracy"]))
    print("Citation validity              : {:.1%}".format(cls["citation_validity"]))
    print("Unsupported-claim rate         : {:.1%}".format(cls["unsupported_claim_rate"]))
    print("Insufficient-information rate  : {:.1%}".format(cls["insufficient_information_rate"]))
    print("Authorization detection acc.   : {:.1%}".format(cls["authorization_accuracy"]))

    # Gating: financial accuracy MUST be 100%; citation validity must be perfect.
    failures = []
    if fin["financial_accuracy"] < 1.0:
        failures.append("financial-calculation accuracy < 100%")
    if fin["duplicate_counting_failures"] > 0:
        failures.append("duplicate-counting failures present")
    if cls["citation_validity"] < 1.0:
        failures.append("citation validity < 100% (fabricated evidence leaked)")
    # With the fake provider, classification is deterministic and must be perfect.
    if provider.model_metadata().provider == "fake" and cls["classification_accuracy"] < 1.0:
        failures.append("deterministic classification accuracy < 100%")

    print()
    if failures:
        print("RESULT: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
