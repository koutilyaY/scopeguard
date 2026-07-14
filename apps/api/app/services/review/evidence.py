"""Deterministic evidence-completeness scoring.

This is an operational completeness measure — NOT a legal probability. Each
component is independently checkable and the breakdown is stored with the finding.
"""

from dataclasses import dataclass

# component -> weight; weights sum to 1.0
DEFAULT_WEIGHTS: dict[str, float] = {
    "verified_contract_clause": 0.25,
    "work_item_present": 0.15,
    "time_entries_present": 0.15,
    "customer_request_present": 0.15,
    "verified_rate": 0.10,
    "not_on_existing_invoice": 0.10,
    "written_authorization": 0.05,
    "work_completed": 0.05,
}


@dataclass
class EvidenceScore:
    score: float
    components: dict[str, bool]
    weights: dict[str, float]

    def breakdown(self) -> dict:
        return {
            "label": "Evidence completeness",
            "disclaimer": (
                "Deterministic completeness of available evidence. "
                "Not a legal probability or a likelihood of collectability."
            ),
            "score": round(self.score, 4),
            "components": [
                {
                    "component": name,
                    "present": present,
                    "weight": self.weights[name],
                    "contribution": self.weights[name] if present else 0.0,
                }
                for name, present in self.components.items()
            ],
        }


def score_evidence(
    *,
    has_verified_clause: bool,
    has_work_item: bool,
    has_time_entries: bool,
    has_customer_request: bool,
    has_verified_rate: bool,
    absent_from_invoices: bool,
    has_written_authorization: bool,
    work_completed: bool,
    weights: dict[str, float] | None = None,
) -> EvidenceScore:
    w = weights or DEFAULT_WEIGHTS
    components = {
        "verified_contract_clause": has_verified_clause,
        "work_item_present": has_work_item,
        "time_entries_present": has_time_entries,
        "customer_request_present": has_customer_request,
        "verified_rate": has_verified_rate,
        "not_on_existing_invoice": absent_from_invoices,
        "written_authorization": has_written_authorization,
        "work_completed": work_completed,
    }
    score = sum(w[name] for name, present in components.items() if present)
    return EvidenceScore(score=round(score, 4), components=components, weights=dict(w))
