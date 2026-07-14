"""Seed the Northstar Data Consulting demonstration organization.

Run with: python -m app.seed
Idempotent: re-running detects the existing organization and exits.

Demo scenario (June 2025 billing period):
- Fixed fee covers five Snowflake ingestion pipelines; onboarding new source
  systems is excluded and additional engineering needs written approval.
- The client emails a request for a sixth (Salesforce) source; Jira contains the
  work; engineers record 34 h (plus one intentional duplicate timesheet row).
- An amendment raises the Data Engineer rate from $175 to $185 on 2025-06-16.
- The existing issued invoice contains only the fixed project fee.
- 12 h of the 20 h monthly support allowance are already consumed.
"""

import hashlib
import logging
from datetime import UTC, date, datetime

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import (
    Allowance,
    Client,
    Contract,
    ContractClause,
    CustomerRequest,
    Document,
    Invoice,
    InvoiceLine,
    Organization,
    Project,
    RateRule,
    TimeEntry,
    User,
    WorkItem,
)
from app.models.enums import (
    AllowanceRecurrence,
    AllowanceType,
    AuthorizationStatus,
    BillableStatus,
    ClauseType,
    ClientStatus,
    ContractStatus,
    DocumentType,
    ExtractionStatus,
    InvoiceStatus,
    ProjectStatus,
    UserRole,
    WorkItemStatus,
)
from app.security.passwords import hash_password
from app.services.review.duplicates import time_entry_content_hash

logger = logging.getLogger("scopeguard.seed")

# Development-only credentials — documented in the README. Do not use in production.
ADMIN_EMAIL = "admin@northstar.example"
ADMIN_PASSWORD = "Northstar-Demo-2025"
REVIEWER_EMAIL = "reviewer@northstar.example"
REVIEWER_PASSWORD = "Reviewer-Demo-2025"

SOW_TEXT = """[page 1]
STATEMENT OF WORK SOW-2025-014
Northstar Data Consulting LLC ("Provider") and Acme Retail Corporation ("Client")
Effective: January 6, 2025 through December 31, 2025

1. Scope of Services
Provider will design, build and deploy five (5) Snowflake ingestion pipelines for the
following source systems: Oracle ERP, Shopify, Zendesk, Google Analytics, and SAP Concur.
Provider will deliver pipeline documentation and a handover workshop for each pipeline.

2. Fixed Fee
The fixed fee for the Scope of Services in Section 1 is $85,000 and covers the five
Snowflake ingestion pipelines described above.

[page 2]
3. Exclusions
Onboarding of new source systems is excluded from the fixed fee and requires a separate
change order. Historical data re-platforming and machine-learning model development are
also excluded.

4. Support Allowance
The fixed fee includes 20 support hours per month for production incident response and
minor configuration changes. Unused support hours do not roll over.

5. Change Control
Additional engineering effort beyond Section 1 requires prior written approval from the
Client and must be documented in a change order before work begins.

[page 3]
6. Rates
Where time-and-materials work is authorized, the Data Engineer rate is $175 per hour and
the Solution Architect rate is $225 per hour.

7. Payment Terms
Invoices are payable net 30 days from the invoice date.
"""

AMENDMENT_TEXT = """[page 1]
AMENDMENT NO. 1 TO STATEMENT OF WORK SOW-2025-014
Effective June 16, 2025.

1. Rate Adjustment
Effective June 16, 2025, the Data Engineer rate is $185 per hour. All other rates and
terms of SOW-2025-014 remain unchanged.
"""

REQUEST_EMAIL_BODY = """Hi Priya,

Great progress on the five pipelines so far. Our operations team now also needs our
Salesforce data in Snowflake. Could your team start onboarding Salesforce as a sixth
source system? Ideally the ingestion pipeline would be live before the end of the
quarter. Let us know what you need from us for access.

Thanks,
Dana Whitfield
Director of Data, Acme Retail Corporation
"""


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def seed() -> None:
    db = get_sessionmaker()()
    try:
        existing = db.execute(
            select(Organization).where(Organization.slug == "northstar")
        ).scalar_one_or_none()
        if existing is not None:
            logger.info("Demo organization already seeded; nothing to do.")
            print("Demo organization already seeded; nothing to do.")
            return

        org = Organization(name="Northstar Data Consulting", slug="northstar")
        db.add(org)
        db.flush()

        admin = User(
            organization_id=org.id,
            email=ADMIN_EMAIL,
            full_name="Avery Nguyen",
            hashed_password=hash_password(ADMIN_PASSWORD),
            role=UserRole.organization_admin,
            active=True,
            must_change_password=False,
        )
        reviewer = User(
            organization_id=org.id,
            email=REVIEWER_EMAIL,
            full_name="Sam Okafor",
            hashed_password=hash_password(REVIEWER_PASSWORD),
            role=UserRole.reviewer,
            active=True,
            must_change_password=False,
        )
        db.add_all([admin, reviewer])

        client = Client(
            organization_id=org.id,
            legal_name="Acme Retail Corporation",
            display_name="Acme Retail",
            external_reference="ACME",
            status=ClientStatus.active,
        )
        db.add(client)
        db.flush()

        project = Project(
            organization_id=org.id,
            client_id=client.id,
            name="Snowflake Modernization",
            external_reference="SNOW-MOD",
            description="Migration of Acme Retail's analytics stack to Snowflake.",
            status=ProjectStatus.active,
            start_date=date(2025, 1, 6),
            end_date=date(2025, 12, 31),
            currency="USD",
        )
        db.add(project)
        db.flush()

        # --- documents (metadata + extracted text; bytes also stored if MinIO is up)
        def make_document(filename: str, doc_type: DocumentType, text: str) -> Document:
            data = text.encode()
            storage_key = f"{org.id}/seed-{_hash(filename)[:16]}.txt"
            document = Document(
                organization_id=org.id,
                client_id=client.id,
                project_id=project.id,
                document_type=doc_type,
                original_filename=filename,
                storage_key=storage_key,
                sha256=hashlib.sha256(data).hexdigest(),
                mime_type="text/plain",
                file_size=len(data),
                extraction_status=ExtractionStatus.completed,
                extracted_text=text,
                uploaded_by=admin.id,
            )
            try:
                from app.services.storage import put_object

                put_object(storage_key, data, "text/plain")
            except Exception:
                logger.warning("MinIO unavailable during seed; stored metadata only.")
            db.add(document)
            db.flush()
            return document

        sow_doc = make_document("acme-sow-2025-014.txt", DocumentType.statement_of_work, SOW_TEXT)
        amendment_doc = make_document(
            "acme-sow-amendment-1.txt", DocumentType.amendment, AMENDMENT_TEXT
        )
        email_doc = make_document(
            "acme-salesforce-request.txt",
            DocumentType.customer_request,
            f"Subject: Salesforce as a sixth source\n\n{REQUEST_EMAIL_BODY}",
        )

        # --- contracts
        sow = Contract(
            organization_id=org.id,
            client_id=client.id,
            project_id=project.id,
            contract_number="SOW-2025-014",
            title="Snowflake Modernization — Statement of Work",
            effective_from=date(2025, 1, 6),
            effective_to=date(2025, 12, 31),
            currency="USD",
            status=ContractStatus.active,
            governing_document_id=sow_doc.id,
            verified_by_user=admin.id,
            verified_at=datetime(2025, 1, 10, tzinfo=UTC),
        )
        amendment = Contract(
            organization_id=org.id,
            client_id=client.id,
            project_id=project.id,
            contract_number="SOW-2025-014-A1",
            title="Amendment No. 1 — Data Engineer rate",
            effective_from=date(2025, 6, 16),
            effective_to=date(2025, 12, 31),
            currency="USD",
            status=ContractStatus.active,
            governing_document_id=amendment_doc.id,
            verified_by_user=admin.id,
            verified_at=datetime(2025, 6, 16, tzinfo=UTC),
        )
        db.add_all([sow, amendment])
        db.flush()

        # --- clauses (quotes are verbatim from the documents above)
        def clause(
            contract: Contract,
            clause_type: ClauseType,
            title: str,
            quote: str,
            page: int,
            section: str,
            verified: bool,
            interpretation: str,
        ) -> ContractClause:
            row = ContractClause(
                organization_id=org.id,
                contract_id=contract.id,
                clause_type=clause_type,
                title=title,
                source_text=quote,
                normalized_interpretation=interpretation,
                page_number=page,
                section_reference=section,
                effective_from=contract.effective_from,
                effective_to=contract.effective_to,
                confidence=0.9,
                human_verified=verified,
                verified_by=admin.id if verified else None,
            )
            db.add(row)
            db.flush()
            return row

        clause(
            sow,
            ClauseType.included_service,
            "Five Snowflake ingestion pipelines",
            "Provider will design, build and deploy five (5) Snowflake ingestion pipelines for the\n"
            "following source systems: Oracle ERP, Shopify, Zendesk, Google Analytics, and SAP Concur.",
            1,
            "1",
            True,
            "The fixed scope covers exactly five named source-system pipelines.",
        )
        clause(
            sow,
            ClauseType.fixed_fee,
            "Fixed fee $85,000",
            "The fixed fee for the Scope of Services in Section 1 is $85,000 and covers the five\n"
            "Snowflake ingestion pipelines described above.",
            1,
            "2",
            True,
            "US$85,000 fixed fee covering the five pipelines only.",
        )
        clause(  # exclusion (unverified for demo walkthrough)
            sow,
            ClauseType.excluded_service,
            "New source-system onboarding excluded",
            "Onboarding of new source systems is excluded from the fixed fee and requires a separate\n"
            "change order.",
            2,
            "3",
            False,  # left unverified so the demo walkthrough exercises clause approval
            "Any new source system beyond the five named ones is out of the fixed-fee scope.",
        )
        support_clause = clause(
            sow,
            ClauseType.support_allowance,
            "20 support hours per month",
            "The fixed fee includes 20 support hours per month for production incident response and\n"
            "minor configuration changes.",
            2,
            "4",
            True,
            "Monthly allowance of 20 support hours; unused hours do not roll over.",
        )
        clause(  # approval requirement
            sow,
            ClauseType.approval_requirement,
            "Written approval for additional engineering",
            "Additional engineering effort beyond Section 1 requires prior written approval from the\n"
            "Client and must be documented in a change order before work begins.",
            2,
            "5",
            True,
            "Extra engineering work needs prior written client approval via change order.",
        )
        de_rate_clause = clause(
            sow,
            ClauseType.hourly_rate,
            "Data Engineer $175/h",
            "the Data Engineer rate is $175 per hour",
            3,
            "6",
            True,
            "Data Engineer time-and-materials rate: $175/hour.",
        )
        architect_rate_clause = clause(
            sow,
            ClauseType.hourly_rate,
            "Solution Architect $225/h",
            "the Solution Architect rate is $225 per hour",
            3,
            "6",
            True,
            "Solution Architect time-and-materials rate: $225/hour.",
        )
        amended_rate_clause = clause(
            amendment,
            ClauseType.hourly_rate,
            "Data Engineer $185/h (Amendment 1)",
            "Effective June 16, 2025, the Data Engineer rate is $185 per hour.",
            1,
            "1",
            True,
            "Amendment raises the Data Engineer rate to $185/hour from 2025-06-16.",
        )

        # --- rates (verified so deterministic value computation is possible)
        db.add_all(
            [
                RateRule(
                    organization_id=org.id,
                    contract_id=sow.id,
                    role_name="Data Engineer",
                    service_category="engineering",
                    hourly_rate_minor=17500,
                    currency="USD",
                    effective_from=date(2025, 1, 6),
                    effective_to=date(2025, 6, 15),
                    source_clause_id=de_rate_clause.id,
                    human_verified=True,
                ),
                RateRule(
                    organization_id=org.id,
                    contract_id=amendment.id,
                    role_name="Data Engineer",
                    service_category="engineering",
                    hourly_rate_minor=18500,
                    currency="USD",
                    effective_from=date(2025, 6, 16),
                    effective_to=date(2025, 12, 31),
                    source_clause_id=amended_rate_clause.id,
                    human_verified=True,
                ),
                RateRule(
                    organization_id=org.id,
                    contract_id=sow.id,
                    role_name="Solution Architect",
                    service_category="engineering",
                    hourly_rate_minor=22500,
                    currency="USD",
                    effective_from=date(2025, 1, 6),
                    effective_to=date(2025, 12, 31),
                    source_clause_id=architect_rate_clause.id,
                    human_verified=True,
                ),
            ]
        )

        db.add(
            Allowance(
                organization_id=org.id,
                contract_id=sow.id,
                allowance_type=AllowanceType.support_hours,
                included_quantity=20 * 60,
                unit="minutes",
                recurrence=AllowanceRecurrence.monthly,
                effective_from=date(2025, 1, 6),
                effective_to=date(2025, 12, 31),
                source_clause_id=support_clause.id,
            )
        )

        # --- work items: five contracted pipelines + salesforce + support bucket
        def work_item(
            external_id: str,
            title: str,
            description: str,
            status: WorkItemStatus,
            work_type: str,
            completed: date | None,
        ) -> WorkItem:
            row = WorkItem(
                organization_id=org.id,
                project_id=project.id,
                external_system="jira_csv",
                external_id=external_id,
                title=title,
                description=description,
                status=status,
                work_type=work_type,
                assignee="Priya Raman",
                created_at_external=datetime(2025, 2, 1, tzinfo=UTC),
                completed_at_external=(
                    datetime.combine(completed, datetime.min.time(), UTC) if completed else None
                ),
                source_url=f"https://jira.example/browse/{external_id}",
                content_hash=_hash(external_id, title),
            )
            db.add(row)
            db.flush()
            return row

        pipelines = [
            ("DE-101", "Oracle ERP ingestion pipeline", date(2025, 3, 14)),
            ("DE-102", "Shopify ingestion pipeline", date(2025, 4, 2)),
            ("DE-103", "Zendesk ingestion pipeline", date(2025, 4, 28)),
            ("DE-104", "Google Analytics ingestion pipeline", date(2025, 5, 21)),
            ("DE-105", "SAP Concur ingestion pipeline", date(2025, 6, 6)),
        ]
        for ext_id, title, done in pipelines:
            work_item(
                ext_id,
                title,
                f"Contracted pipeline delivery: {title} into Snowflake with documentation.",
                WorkItemStatus.done,
                "feature",
                done,
            )
        salesforce = work_item(
            "DE-106",
            "Salesforce source onboarding — sixth ingestion pipeline",
            "Onboarding new Salesforce source systems per Dana Whitfield's email: build the "
            "ingestion pipeline for the sixth source, including auth setup, schema mapping "
            "and incremental sync into Snowflake.",
            WorkItemStatus.done,
            "feature",
            date(2025, 6, 25),
        )
        support_item = work_item(
            "SUP-12",
            "June production support",
            "Production incident response and minor configuration changes for June.",
            WorkItemStatus.done,
            "support",
            date(2025, 6, 30),
        )

        # --- time entries
        def entry(
            work: WorkItem | None,
            employee: str,
            role: str,
            day: date,
            minutes: int,
            description: str,
            external_id: str | None = None,
        ) -> TimeEntry:
            row = TimeEntry(
                organization_id=org.id,
                project_id=project.id,
                work_item_id=work.id if work else None,
                external_id=external_id,
                employee_name=employee,
                employee_role=role,
                work_date=day,
                minutes=minutes,
                billable_status=BillableStatus.unknown,
                description=description,
                source="seed",
                content_hash=time_entry_content_hash(
                    str(project.id), employee, str(day), minutes, description
                ),
            )
            db.add(row)
            return row

        # 34 hours on the Salesforce source (21h before the rate change, 13h after)
        salesforce_entries = [
            (
                "Priya Raman",
                date(2025, 6, 5),
                360,
                "Salesforce onboarding: API auth and connected app setup",
            ),
            ("Priya Raman", date(2025, 6, 9), 420, "Salesforce onboarding: object schema mapping"),
            (
                "Marco Diaz",
                date(2025, 6, 10),
                480,
                "Salesforce ingestion pipeline: incremental sync build",
            ),
            (
                "Priya Raman",
                date(2025, 6, 17),
                360,
                "Salesforce ingestion pipeline: transformation logic",
            ),
            (
                "Marco Diaz",
                date(2025, 6, 20),
                240,
                "Salesforce ingestion pipeline: testing and data validation",
            ),
            (
                "Priya Raman",
                date(2025, 6, 24),
                180,
                "Salesforce ingestion pipeline: deployment and handover prep",
            ),
        ]
        for employee, day, minutes, description in salesforce_entries:
            entry(salesforce, employee, "Data Engineer", day, minutes, description)
        # intentional exact duplicate of the June 10 row (double-submitted timesheet)
        entry(
            salesforce,
            "Marco Diaz",
            "Data Engineer",
            date(2025, 6, 10),
            480,
            "Salesforce ingestion pipeline: incremental sync build",
        )

        # 12 of 20 monthly support hours already consumed in June
        support_entries = [
            ("Priya Raman", date(2025, 6, 3), 240, "Support: Oracle ERP pipeline incident triage"),
            ("Marco Diaz", date(2025, 6, 12), 300, "Support: Shopify schema drift fix"),
            (
                "Priya Raman",
                date(2025, 6, 26),
                180,
                "Support: warehouse resize configuration change",
            ),
        ]
        for employee, day, minutes, description in support_entries:
            entry(support_item, employee, "Data Engineer", day, minutes, description)

        # --- existing invoice: fixed fee only, issued
        invoice = Invoice(
            organization_id=org.id,
            project_id=project.id,
            invoice_number="INV-2025-0142",
            billing_period_start=date(2025, 6, 1),
            billing_period_end=date(2025, 6, 30),
            issue_date=date(2025, 6, 28),
            currency="USD",
            status=InvoiceStatus.issued,
            subtotal_minor=8_500_000,
            tax_minor=0,
            total_minor=8_500_000,
            external_reference="QB-8841",
        )
        db.add(invoice)
        db.flush()
        db.add(
            InvoiceLine(
                organization_id=org.id,
                invoice_id=invoice.id,
                description="Snowflake Modernization — fixed project fee (SOW-2025-014)",
                service_category="fixed_fee",
                quantity=1,
                unit_price_minor=8_500_000,
                amount_minor=8_500_000,
            )
        )

        # --- customer request email (no written authorization; request only)
        db.add(
            CustomerRequest(
                organization_id=org.id,
                project_id=project.id,
                subject="Salesforce as a sixth source",
                sender="dana.whitfield@acmeretail.example",
                recipients="priya.raman@northstar.example",
                request_date=date(2025, 6, 2),
                body=REQUEST_EMAIL_BODY,
                source_document_id=email_doc.id,
                linked_work_item_id=salesforce.id,
                customer_authorization_status=AuthorizationStatus.none,
            )
        )

        # --- a second, empty-ish organization for cross-tenant sanity checks
        other_org = Organization(name="Blue Peak Consulting", slug="bluepeak")
        db.add(other_org)
        db.flush()
        db.add(
            User(
                organization_id=other_org.id,
                email="admin@bluepeak.example",
                full_name="Jordan Lee",
                hashed_password=hash_password("BluePeak-Demo-2025"),
                role=UserRole.organization_admin,
                active=True,
                must_change_password=False,
            )
        )

        db.commit()

        # embeddings for clause retrieval (best-effort; requires provider)
        try:
            from app.models import ContractClause as CC
            from app.services.retrieval import embed_clauses

            clauses = list(db.execute(select(CC).where(CC.organization_id == org.id)).scalars())
            embed_clauses(db, clauses)
            db.commit()
        except Exception:
            logger.warning(
                "Skipping clause embeddings during seed (LLM provider unavailable); "
                "lexical retrieval fallback will be used."
            )
            db.rollback()

        print("Seeded demo organization 'Northstar Data Consulting'.")
        print(f"  admin:    {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print(f"  reviewer: {REVIEWER_EMAIL} / {REVIEWER_PASSWORD}")
        print("  second org (cross-tenant checks): admin@bluepeak.example / BluePeak-Demo-2025")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
