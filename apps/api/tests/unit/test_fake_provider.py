"""The deterministic fake provider: extraction, classification, embeddings."""

from app.services.llm.fake import FakeLLMProvider
from app.services.llm.schemas import ContractExtractionOut, ScopeClassificationOut

provider = FakeLLMProvider()

DOC = """[page 1]
1. Scope of Services
Provider will design, build and deploy five (5) Snowflake ingestion pipelines.
2. Exclusions
Onboarding of new source systems is excluded from the fixed fee and requires a separate change order.
3. Support
The fixed fee includes 20 support hours per month for production incident response.
4. Rates
The Data Engineer rate is $175 per hour for authorized time-and-materials work.
5. Approvals
Additional engineering effort requires prior written approval from the Client.
"""


def _extract():
    out, result = provider.generate_structured(
        "system",
        f"TASK: CONTRACT_EXTRACTION\n<<<DOCUMENT>>>\n{DOC}\n<<<END DOCUMENT>>>",
        ContractExtractionOut,
    )
    return out


class TestFakeExtraction:
    def test_finds_expected_clause_types(self):
        out = _extract()
        types = {c.clause_type for c in out.clauses}
        assert "excluded_service" in types
        assert "support_allowance" in types
        assert "hourly_rate" in types
        assert "approval_requirement" in types

    def test_quotations_are_verbatim(self):
        out = _extract()
        for clause in out.clauses:
            assert clause.source_quotation in DOC

    def test_rate_value_extracted(self):
        out = _extract()
        rates = [c for c in out.clauses if c.clause_type == "hourly_rate"]
        assert rates and rates[0].hourly_rate == 175.0
        assert rates[0].role_name == "Data Engineer"

    def test_pages_tracked(self):
        out = _extract()
        assert all(c.page_number == 1 for c in out.clauses)


CLASSIFY_PROMPT = """TASK: SCOPE_CLASSIFICATION
BILLING PERIOD: 2025-06-01 to 2025-06-30
PROJECT: Snowflake Modernization

=== CONTRACT CLAUSES (cite by id; quote exactly) ===
CLAUSE id=clause-1 type=excluded_service verified=true
QUOTE: Onboarding of new source systems is excluded from the fixed fee and requires a separate change order.
---
CLAUSE id=clause-2 type=approval_requirement verified=true
QUOTE: Additional engineering effort requires prior written approval from the Client.
---
=== WORK ITEMS ===
WORK_ITEM id=work-1 external=DE-106 status=done
TITLE: Salesforce source onboarding - sixth ingestion pipeline
DESCRIPTION: Onboarding new Salesforce source systems: build the ingestion pipeline for the sixth source.
---
=== TIME ENTRIES ===
TIME_ENTRY id=time-1 employee=Priya role=Data Engineer date=2025-06-05 minutes=360
DESCRIPTION: Salesforce onboarding auth setup
---
=== CUSTOMER REQUESTS ===
CUSTOMER_REQUEST id=req-1 date=2025-06-02 authorization=none
SUBJECT: Salesforce as a sixth source
BODY: Could your team start onboarding Salesforce as a sixth source system?
---
"""


class TestFakeClassification:
    def test_out_of_scope_detected(self):
        out, _ = provider.generate_structured("s", CLASSIFY_PROMPT, ScopeClassificationOut)
        assert out.classification.value in ("potentially_out_of_scope", "clearly_out_of_scope")

    def test_only_known_ids_cited(self):
        out, _ = provider.generate_structured("s", CLASSIFY_PROMPT, ScopeClassificationOut)
        known = {"clause-1", "clause-2", "work-1", "time-1", "req-1"}
        for ref in out.supporting_evidence:
            assert ref.entity_id in known

    def test_missing_authorization_flagged(self):
        out, _ = provider.generate_structured("s", CLASSIFY_PROMPT, ScopeClassificationOut)
        assert out.requires_customer_authorization is True

    def test_no_clauses_means_insufficient_information(self):
        prompt = (
            CLASSIFY_PROMPT.split("=== CONTRACT CLAUSES")[0]
            + "=== WORK ITEMS ===\n"
            + CLASSIFY_PROMPT.split("=== WORK ITEMS ===\n")[1]
        )
        out, _ = provider.generate_structured("s", prompt, ScopeClassificationOut)
        assert out.classification.value == "insufficient_information"


class TestFakeEmbeddings:
    def test_deterministic(self):
        a = provider.create_embeddings(["support hours allowance"])
        b = provider.create_embeddings(["support hours allowance"])
        assert a == b

    def test_similar_text_more_similar_than_unrelated(self):
        def cos(u, v):
            return sum(x * y for x, y in zip(u, v, strict=True))

        vectors = provider.create_embeddings(
            [
                "onboarding new source systems excluded",
                "new source system onboarding excluded from fee",
                "payment terms net 30 days invoice",
            ]
        )
        assert cos(vectors[0], vectors[1]) > cos(vectors[0], vectors[2])

    def test_dimension(self):
        assert len(provider.create_embeddings(["x"])[0]) == 768
