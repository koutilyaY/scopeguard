"""Cross-tenant access must always look like 404/403, never leak data."""

import uuid
from datetime import UTC, date, datetime

from app.models import (
    Client,
    Contract,
    Document,
    Finding,
    Project,
    ReviewRun,
)
from app.models.enums import (
    Classification,
    ClientStatus,
    DocumentType,
    ExtractionStatus,
    FindingType,
    ProjectStatus,
    ReviewRunStatus,
    ReviewStatus,
    RiskLevel,
)
from tests.conftest import auth_headers, create_org_with_admin, login, requires_db

pytestmark = requires_db


def seed_org_data(db, org, user):
    client_row = Client(
        organization_id=org.id,
        legal_name="Secret Client Ltd",
        display_name="Secret Client",
        status=ClientStatus.active,
    )
    db.add(client_row)
    db.flush()
    project = Project(
        organization_id=org.id,
        client_id=client_row.id,
        name="Secret Project",
        status=ProjectStatus.active,
        currency="USD",
    )
    db.add(project)
    db.flush()
    document = Document(
        organization_id=org.id,
        client_id=client_row.id,
        project_id=project.id,
        document_type=DocumentType.statement_of_work,
        original_filename="secret.pdf",
        storage_key=f"{org.id}/{uuid.uuid4().hex}.pdf",
        sha256="0" * 64,
        mime_type="application/pdf",
        file_size=10,
        extraction_status=ExtractionStatus.completed,
        extracted_text="secret text",
    )
    contract = Contract(
        organization_id=org.id,
        client_id=client_row.id,
        project_id=project.id,
        title="Secret Contract",
        currency="USD",
    )
    db.add_all([document, contract])
    db.flush()
    run = ReviewRun(
        organization_id=org.id,
        project_id=project.id,
        billing_period_start=date(2025, 6, 1),
        billing_period_end=date(2025, 6, 30),
        status=ReviewRunStatus.completed,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.flush()
    finding = Finding(
        organization_id=org.id,
        review_run_id=run.id,
        project_id=project.id,
        finding_type=FindingType.potentially_out_of_scope,
        title="Secret finding",
        explanation="secret",
        classification=Classification.potentially_out_of_scope,
        review_status=ReviewStatus.pending,
        risk_level=RiskLevel.medium,
        dedup_key=uuid.uuid4().hex,
    )
    db.add(finding)
    db.commit()
    return {
        "client": client_row,
        "project": project,
        "document": document,
        "contract": contract,
        "run": run,
        "finding": finding,
    }


def test_cross_tenant_object_access_denied(client, db):
    org_a, user_a = create_org_with_admin(db, "tenant-a")
    org_b, user_b = create_org_with_admin(db, "tenant-b")
    data_a = seed_org_data(db, org_a, user_a)

    login(client, user_b)  # user B tries to read org A's records

    for path in [
        f"/api/v1/clients/{data_a['client'].id}",
        f"/api/v1/projects/{data_a['project'].id}",
        f"/api/v1/documents/{data_a['document'].id}",
        f"/api/v1/documents/{data_a['document'].id}/text",
        f"/api/v1/documents/{data_a['document'].id}/download",
        f"/api/v1/contracts/{data_a['contract'].id}",
        f"/api/v1/review-runs/{data_a['run'].id}",
        f"/api/v1/findings/{data_a['finding'].id}",
        f"/api/v1/reports/findings/{data_a['finding'].id}.json",
        f"/api/v1/reports/findings/{data_a['finding'].id}.pdf",
    ]:
        response = client.get(path)
        assert response.status_code == 404, f"{path} leaked: {response.status_code}"
        assert "Secret" not in response.text


def test_list_endpoints_scoped_to_own_org(client, db):
    org_a, user_a = create_org_with_admin(db, "tenant-c")
    org_b, user_b = create_org_with_admin(db, "tenant-d")
    seed_org_data(db, org_a, user_a)

    login(client, user_b)
    # Tenant B has no business records; org A's rows must never appear.
    for path in [
        "/api/v1/clients",
        "/api/v1/projects",
        "/api/v1/documents",
        "/api/v1/findings",
        "/api/v1/review-runs",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["total"] == 0, f"{path} leaked rows across tenants"

    # Tenant B's audit log contains only its OWN events (its login), never org A's.
    audit = client.get("/api/v1/audit-events")
    assert audit.status_code == 200
    assert all(e["action"].startswith("auth.") for e in audit.json()["items"]), (
        "audit log leaked another tenant's events"
    )


def test_cannot_mutate_other_orgs_finding(client, db):
    org_a, user_a = create_org_with_admin(db, "tenant-e")
    org_b, user_b = create_org_with_admin(db, "tenant-f")
    data_a = seed_org_data(db, org_a, user_a)

    csrf = login(client, user_b)
    response = client.post(
        "/api/v1/decisions",
        json={
            "finding_id": str(data_a["finding"].id),
            "new_status": "rejected",
            "reason": "cross-tenant attack attempt",
        },
        headers=auth_headers(csrf),
    )
    assert response.status_code == 404
    db.refresh(data_a["finding"])
    assert data_a["finding"].review_status == ReviewStatus.pending


def test_cannot_create_project_under_other_orgs_client(client, db):
    org_a, user_a = create_org_with_admin(db, "tenant-g")
    org_b, user_b = create_org_with_admin(db, "tenant-h")
    data_a = seed_org_data(db, org_a, user_a)

    csrf = login(client, user_b)
    response = client.post(
        "/api/v1/projects",
        json={"client_id": str(data_a["client"].id), "name": "hijack"},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 404


def test_org_export_only_contains_own_data(client, db):
    org_a, user_a = create_org_with_admin(db, "tenant-i")
    org_b, user_b = create_org_with_admin(db, "tenant-j")
    seed_org_data(db, org_a, user_a)

    login(client, user_b)
    response = client.get("/api/v1/organizations/current/export")
    assert response.status_code == 200
    export = response.json()
    assert export["clients"] == []
    assert export["findings"] == []
