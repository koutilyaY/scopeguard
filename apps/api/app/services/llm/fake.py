"""Deterministic fake LLM provider for tests and offline evaluation.

It parses the same delimited prompt format the real prompts use and applies
transparent keyword heuristics, so pipeline behavior is reproducible without a
model. It NEVER invents entity IDs — it only echoes IDs present in the prompt.
"""

import hashlib
import json
import re

from app.services.llm.base import LLMProvider, ModelMetadata

STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "for",
    "to",
    "in",
    "on",
    "with",
    "is",
    "are",
    "be",
    "as",
    "by",
    "at",
    "from",
    "this",
    "that",
    "it",
    "its",
    "any",
    "all",
    "per",
    "new",
    "work",
    "hours",
    "hour",
    "will",
    "shall",
    "not",
    "does",
    "do",
    "into",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9\-]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


class FakeLLMProvider(LLMProvider):
    """Rule-based stand-in for a local model. Deterministic by construction."""

    def _generate_text(self, system_prompt: str, user_prompt: str) -> str:
        if "TASK: CONTRACT_EXTRACTION" in user_prompt:
            return self._extract_contract(user_prompt)
        if "TASK: SCOPE_CLASSIFICATION" in user_prompt:
            return self._classify_scope(user_prompt)
        if "TASK: ARTIFACT_DRAFT" in user_prompt:
            return self._draft_artifact(user_prompt)
        return json.dumps({"error": "unknown task"})

    # ------------------------------------------------------------------ extraction
    def _extract_contract(self, prompt: str) -> str:
        match = re.search(r"<<<DOCUMENT>>>\n(.*?)\n<<<END DOCUMENT>>>", prompt, re.DOTALL)
        text = match.group(1) if match else ""
        clauses = []
        current_page = 1
        current_section = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            page_marker = re.match(r"\[page (\d+)\]", line)
            if page_marker:
                current_page = int(page_marker.group(1))
                continue
            section_marker = re.match(r"^(?:##\s*)?(\d+(?:\.\d+)*)[.\s]+(.+)", line)
            if section_marker and len(line) < 90:
                current_section = section_marker.group(1)

            sentence = line
            lowered = sentence.lower()

            rate = re.search(
                r"([A-Za-z][A-Za-z ]*?(?:engineer|architect|consultant|analyst|manager|developer))"
                r"[^.$]*\$(\d[\d,]*(?:\.\d{2})?)\s*per hour",
                sentence,
                re.IGNORECASE,
            )
            if rate:
                role = re.sub(r"^(?:the|a|an)\s+", "", rate.group(1).strip(), flags=re.IGNORECASE)
                clauses.append(
                    {
                        "clause_type": "hourly_rate",
                        "title": f"Hourly rate — {role}",
                        "source_quotation": sentence,
                        "normalized_interpretation": (
                            f"{role} billed at ${rate.group(2)} per hour."
                        ),
                        "page_number": current_page,
                        "section_reference": current_section,
                        "confidence": 0.9,
                        "role_name": role,
                        "hourly_rate": float(rate.group(2).replace(",", "")),
                        "currency": "USD",
                    }
                )
                continue
            allowance = re.search(
                r"(\d+)\s*(?:\(\w+\))?\s*(support|implementation)\s+hours", lowered
            )
            if allowance and (
                "include" in lowered or "allowance" in lowered or "per month" in lowered
            ):
                clauses.append(
                    {
                        "clause_type": "support_allowance",
                        "title": f"{allowance.group(2).title()} hours allowance",
                        "source_quotation": sentence,
                        "normalized_interpretation": (
                            f"{allowance.group(1)} {allowance.group(2)} hours included"
                            + (" per month." if "month" in lowered else ".")
                        ),
                        "page_number": current_page,
                        "section_reference": current_section,
                        "confidence": 0.85,
                        "included_quantity": float(allowance.group(1)),
                        "unit": "hours",
                        "recurrence": "monthly" if "month" in lowered else "total",
                    }
                )
                continue
            if (
                "excluded" in lowered or "not included" in lowered or "out of scope" in lowered
            ) and len(sentence) > 30:
                clauses.append(
                    {
                        "clause_type": "excluded_service",
                        "title": "Excluded service",
                        "source_quotation": sentence,
                        "normalized_interpretation": sentence,
                        "page_number": current_page,
                        "section_reference": current_section,
                        "confidence": 0.85,
                    }
                )
                continue
            if "fixed fee" in lowered and re.search(r"\$\d", sentence):
                clauses.append(
                    {
                        "clause_type": "fixed_fee",
                        "title": "Fixed fee",
                        "source_quotation": sentence,
                        "normalized_interpretation": sentence,
                        "page_number": current_page,
                        "section_reference": current_section,
                        "confidence": 0.85,
                    }
                )
                continue
            if "written approval" in lowered or "prior written" in lowered:
                clauses.append(
                    {
                        "clause_type": "approval_requirement",
                        "title": "Written approval requirement",
                        "source_quotation": sentence,
                        "normalized_interpretation": sentence,
                        "page_number": current_page,
                        "section_reference": current_section,
                        "confidence": 0.85,
                    }
                )
                continue
            if "change order" in lowered and ("must" in lowered or "require" in lowered):
                clauses.append(
                    {
                        "clause_type": "change_control",
                        "title": "Change control",
                        "source_quotation": sentence,
                        "normalized_interpretation": sentence,
                        "page_number": current_page,
                        "section_reference": current_section,
                        "confidence": 0.8,
                    }
                )
                continue
            if (
                "scope of services" in lowered or "provider will" in lowered or "deliver" in lowered
            ) and len(sentence) > 40:
                clauses.append(
                    {
                        "clause_type": "included_service",
                        "title": "Included service",
                        "source_quotation": sentence,
                        "normalized_interpretation": sentence,
                        "page_number": current_page,
                        "section_reference": current_section,
                        "confidence": 0.7,
                    }
                )
        return json.dumps({"clauses": clauses, "notes": "fake-provider extraction"})

    # -------------------------------------------------------------- classification
    def _classify_scope(self, prompt: str) -> str:
        clause_pattern = re.compile(
            r"CLAUSE id=(\S+) type=(\S+) verified=(\S+)\nQUOTE: (.*?)(?:\n---|\Z)", re.DOTALL
        )
        work_pattern = re.compile(
            r"WORK_ITEM id=(\S+).*?\nTITLE: (.*?)\nDESCRIPTION: (.*?)(?:\n---|\Z)", re.DOTALL
        )
        time_pattern = re.compile(
            r"TIME_ENTRY id=(\S+)[^\n]*\nDESCRIPTION: (.*?)(?:\n---|\Z)", re.DOTALL
        )
        request_pattern = re.compile(
            r"CUSTOMER_REQUEST id=(\S+) [^\n]*authorization=(\S+)\nSUBJECT: (.*?)\nBODY: (.*?)(?:\n---|\Z)",
            re.DOTALL,
        )

        clauses = clause_pattern.findall(prompt)
        work_items = work_pattern.findall(prompt)
        time_entries = time_pattern.findall(prompt)
        requests = request_pattern.findall(prompt)

        work_text = (
            " ".join(f"{t} {d}" for _, t, d in work_items)
            + " "
            + " ".join(d for _, d in time_entries)
        )
        work_tokens = _tokens(work_text)

        supporting = []
        applicable = []
        best_excluded_overlap = 0
        best_included_overlap = 0

        for clause_id, clause_type, _verified, quote in clauses:
            quote = quote.strip()
            overlap = len(_tokens(quote) & work_tokens)
            if clause_type == "excluded_service" and overlap >= 2:
                best_excluded_overlap = max(best_excluded_overlap, overlap)
                applicable.append(clause_id)
                supporting.append(
                    {
                        "entity_type": "contract_clause",
                        "entity_id": clause_id,
                        "quotation": quote,
                        "reason": "Excluded-service clause overlaps the delivered work description.",
                    }
                )
            elif clause_type == "included_service" and overlap >= 2:
                best_included_overlap = max(best_included_overlap, overlap)
                applicable.append(clause_id)

        for item_id, title, _description in work_items:
            supporting.append(
                {
                    "entity_type": "work_item",
                    "entity_id": item_id,
                    "quotation": title.strip(),
                    "reason": "Work item shows the work was performed.",
                }
            )
        for request_id, _authorization, subject, _body in requests:
            supporting.append(
                {
                    "entity_type": "customer_request",
                    "entity_id": request_id,
                    "quotation": subject.strip(),
                    "reason": "Customer explicitly requested this work.",
                }
            )

        has_written_auth = any(auth == "written" for _, auth, _, _ in requests)
        requires_auth = "approval_requirement" in {c[1] for c in clauses} and not has_written_auth

        if not clauses:
            classification, confidence = "insufficient_information", 0.4
            summary = "No applicable contract clauses were provided; scope cannot be assessed."
        elif best_excluded_overlap >= 4:
            classification, confidence = "clearly_out_of_scope", 0.85
            summary = "The work closely matches an explicit exclusion in the contract."
        elif best_excluded_overlap >= 2:
            classification, confidence = "potentially_out_of_scope", 0.75
            summary = (
                "The delivered work overlaps an excluded-service clause; human review is "
                "required to confirm whether it falls outside the contracted scope."
            )
        elif best_included_overlap >= 2:
            classification, confidence = "in_scope", 0.8
            summary = "The work matches services included in the contract."
        else:
            classification, confidence = "insufficient_information", 0.5
            summary = "Evidence does not clearly match included or excluded services."

        missing = []
        if not has_written_auth:
            missing.append("Written customer authorization for the additional work")
        if not time_entries:
            missing.append("Time entries substantiating the effort")

        return json.dumps(
            {
                "classification": classification,
                "confidence": confidence,
                "summary": summary,
                "applicable_clause_ids": applicable,
                "supporting_evidence": supporting,
                "contradicting_evidence": [],
                "missing_evidence": missing,
                "requires_customer_authorization": requires_auth,
                "recommended_review_action": (
                    "Review the cited clauses and evidence, then decide whether a change "
                    "order or additional invoice is appropriate."
                ),
            }
        )

    # ------------------------------------------------------------------- artifacts
    def _draft_artifact(self, prompt: str) -> str:
        kind = re.search(r"ARTIFACT_TYPE: (\S+)", prompt)
        context = re.search(r"<<<CONTEXT>>>\n(.*?)\n<<<END CONTEXT>>>", prompt, re.DOTALL)
        body = context.group(1)[:2000] if context else ""
        artifact_type = kind.group(1) if kind else "internal_review_summary"
        content = (
            f"[DRAFT — {artifact_type} — generated by the deterministic fake provider; "
            "requires human review]\n\n" + body
        )
        return json.dumps({"content": content})

    # ------------------------------------------------------------------ embeddings
    def create_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Deterministic pseudo-embeddings: seeded from token hashes so similar
        token sets produce similar vectors (adequate for retrieval tests)."""
        dimension = 768
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * dimension
            for token in _tokens(text):
                digest = hashlib.sha256(token.encode()).digest()
                index = int.from_bytes(digest[:4], "big") % dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
            norm = sum(v * v for v in vector) ** 0.5 or 1.0
            vectors.append([v / norm for v in vector])
        return vectors

    def health_check(self) -> bool:
        return True

    def model_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider="fake", chat_model="fake-rules-v1", embed_model="fake-hash-v1"
        )
