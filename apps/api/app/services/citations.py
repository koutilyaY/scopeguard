"""Citation verification: every quotation the model returns must exist verbatim
(after whitespace normalization) in its claimed source. Fabricated quotations or
unknown entity IDs invalidate the evidence."""

import re
from dataclasses import dataclass


def normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def quotation_in_source(quotation: str, source_text: str) -> bool:
    if not quotation or not source_text:
        return False
    return normalize_for_match(quotation) in normalize_for_match(source_text)


@dataclass
class CitationCheck:
    valid: bool
    reason: str | None = None


def verify_citation(
    entity_id: str,
    quotation: str | None,
    known_sources: dict[str, str],
) -> CitationCheck:
    """known_sources: entity_id -> source text supplied to the model."""
    if entity_id not in known_sources:
        return CitationCheck(valid=False, reason=f"Unknown entity id {entity_id}")
    if quotation and not quotation_in_source(quotation, known_sources[entity_id]):
        return CitationCheck(valid=False, reason="Quotation not found verbatim in the cited source")
    return CitationCheck(valid=True)
