"""Import preview/commit, document extraction to MinIO, artifacts, exports."""

import io

from sqlalchemy import select

from app.models import Finding, Organization, Project, ReviewRun, TimeEntry, User
from app.models.enums import ReviewRunStatus
from app.seed import seed
from tests.conftest import auth_headers, create_org_with_admin, login, requires_db

pytestmark = requires_db

TIMESHEET_CSV = b"""Employee,Role,Date,Hours,Description,Billable,Work Item
Priya Raman,Data Engineer,2025-06-05,6,Salesforce auth,yes,DE-106
Marco Diaz,Data Engineer,2025-06-06,-2,Bad negative row,yes,DE-106
Priya Raman,Data Engineer,not-a-date,3,Bad date row,yes,DE-106
"""


def _project(client, csrf):
    c = client.post(
        "/api/v1/clients", json={"legal_name": "C", "display_name": "C"}, headers=auth_headers(csrf)
    ).json()
    p = client.post(
        "/api/v1/projects", json={"client_id": c["id"], "name": "P"}, headers=auth_headers(csrf)
    ).json()
    return p["id"]


def test_timesheet_preview_reports_row_errors(client, db):
    org, user = create_org_with_admin(db, "imp1")
    csrf = login(client, user)
    response = client.post(
        "/api/v1/imports/time_entries/preview",
        files={"file": ("ts.csv", io.BytesIO(TIMESHEET_CSV), "text/csv")},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_rows"] == 3
    assert body["valid_rows"] == 1
    error_rows = {e["row"] for e in body["errors"]}
    assert error_rows == {3, 4}  # negative time and bad date (header is row 1)


def test_timesheet_commit_creates_valid_rows_only(client, db):
    org, user = create_org_with_admin(db, "imp2")
    csrf = login(client, user)
    project_id = _project(client, csrf)
    response = client.post(
        "/api/v1/imports/time_entries/commit",
        data={"project_id": project_id},
        files={"file": ("ts.csv", io.BytesIO(TIMESHEET_CSV), "text/csv")},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert len(response.json()["errors"]) == 2
    stored = (
        db.execute(select(TimeEntry).where(TimeEntry.organization_id == org.id)).scalars().all()
    )
    assert len(stored) == 1


def test_document_upload_extracts_text_via_worker(client, db):
    """Eager Celery runs extraction inline; a text file yields readable text."""
    org, user = create_org_with_admin(db, "imp3")
    csrf = login(client, user)
    txt = b"This is the master service agreement body with enough text to be readable."
    response = client.post(
        "/api/v1/documents/upload",
        data={"document_type": "master_service_agreement"},
        files={"file": ("msa.txt", io.BytesIO(txt), "text/plain")},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 201
    doc_id = response.json()["document"]["id"]
    text_response = client.get(f"/api/v1/documents/{doc_id}/text")
    assert text_response.status_code == 200
    assert text_response.json()["extraction_status"] == "completed"
    assert "master service agreement" in text_response.json()["extracted_text"].lower()


def _seed_and_review(db):
    seed()
    org = db.execute(select(Organization).where(Organization.slug == "northstar")).scalar_one()
    project = db.execute(select(Project).where(Project.organization_id == org.id)).scalar_one()
    admin = db.execute(select(User).where(User.email == "admin@northstar.example")).scalar_one()
    from datetime import date

    from app.services.review.engine import execute_review_run

    run = ReviewRun(
        organization_id=org.id,
        project_id=project.id,
        billing_period_start=date(2025, 6, 1),
        billing_period_end=date(2025, 6, 30),
        status=ReviewRunStatus.pending,
        initiated_by=admin.id,
    )
    db.add(run)
    db.commit()
    execute_review_run(db, run.id)
    return org, admin


def _login_seed_admin(client) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@northstar.example", "password": "Northstar-Demo-2025"},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_artifact_generation_requires_approval(client, db):
    org, admin = _seed_and_review(db)
    finding = db.execute(
        select(Finding).where(Finding.finding_type == "potentially_out_of_scope")
    ).scalar_one()
    csrf = _login_seed_admin(client)

    # Before approval: generation is blocked
    blocked = client.post(
        "/api/v1/generated-artifacts",
        json={"finding_id": str(finding.id), "artifact_type": "internal_review_summary"},
        headers=auth_headers(csrf),
    )
    assert blocked.status_code == 409

    # Approve for follow-up
    decided = client.post(
        "/api/v1/decisions",
        json={
            "finding_id": str(finding.id),
            "new_status": "approved_for_followup",
            "reason": "Looks genuinely out of scope; pursue a change order.",
        },
        headers=auth_headers(csrf),
    )
    assert decided.status_code == 200

    # Now generation succeeds
    ok = client.post(
        "/api/v1/generated-artifacts",
        json={"finding_id": str(finding.id), "artifact_type": "change_order_draft"},
        headers=auth_headers(csrf),
    )
    assert ok.status_code == 201
    assert "DRAFT" in ok.json()["content"]


def test_exports_include_evidence_and_disclaimer(client, db):
    org, admin = _seed_and_review(db)
    finding = db.execute(
        select(Finding).where(Finding.finding_type == "potentially_out_of_scope")
    ).scalar_one()
    csrf = _login_seed_admin(client)

    csv_response = client.get("/api/v1/reports/findings.csv")
    assert csv_response.status_code == 200
    assert "potentially_out_of_scope" in csv_response.text

    json_response = client.get(f"/api/v1/reports/findings/{finding.id}.json")
    assert json_response.status_code == 200
    body = json_response.json()
    assert "disclaimer" in body
    assert body["finding"]["potential_value_minor"] == 608_000
    assert "evidence" in body and len(body["evidence"]) > 0

    pdf_response = client.get(f"/api/v1/reports/findings/{finding.id}.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.content[:4] == b"%PDF"


def test_decision_requires_reason(client, db):
    org, admin = _seed_and_review(db)
    finding = db.execute(
        select(Finding).where(Finding.finding_type == "potentially_out_of_scope")
    ).scalar_one()
    csrf = _login_seed_admin(client)
    response = client.post(
        "/api/v1/decisions",
        json={"finding_id": str(finding.id), "new_status": "rejected", "reason": "no"},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 422  # reason too short (min_length=5)


def test_dashboard_separates_value_stages(client, db):
    org, admin = _seed_and_review(db)
    csrf = _login_seed_admin(client)
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["pending_review_count"] >= 1
    # potential value present; approved/invoiced tracked separately
    assert "potential_value" in body
    assert "approved_for_billing_value" in body
    assert "invoiced_value" in body
    assert "does not represent" in body["value_disclaimer"]
