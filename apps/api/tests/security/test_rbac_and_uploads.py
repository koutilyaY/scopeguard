"""RBAC restrictions and file-upload security via the API."""

import io

from app.models.enums import UserRole
from tests.conftest import auth_headers, create_org_with_admin, login, requires_db

pytestmark = requires_db

PDF = b"%PDF-1.4 " + b"x" * 200


def _make_project(client, csrf):
    c = client.post(
        "/api/v1/clients", json={"legal_name": "C", "display_name": "C"}, headers=auth_headers(csrf)
    )
    client_id = c.json()["id"]
    p = client.post(
        "/api/v1/projects", json={"client_id": client_id, "name": "P"}, headers=auth_headers(csrf)
    )
    return p.json()["id"]


def test_read_only_cannot_create_client(client, db):
    org, user = create_org_with_admin(db, "ro1", role=UserRole.read_only)
    csrf = login(client, user)
    response = client.post(
        "/api/v1/clients", json={"legal_name": "X", "display_name": "X"}, headers=auth_headers(csrf)
    )
    assert response.status_code == 403


def test_reviewer_cannot_upload_document(client, db):
    org, user = create_org_with_admin(db, "rev1", role=UserRole.reviewer)
    csrf = login(client, user)
    response = client.post(
        "/api/v1/documents/upload",
        data={"document_type": "statement_of_work"},
        files={"file": ("c.pdf", io.BytesIO(PDF), "application/pdf")},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 403


def test_read_only_cannot_create_review_run(client, db):
    org, user = create_org_with_admin(db, "ro2", role=UserRole.read_only)
    csrf = login(client, user)
    # read_only also can't create a project, so this tests the decision-role gate
    response = client.post(
        "/api/v1/review-runs",
        json={
            "project_id": "00000000-0000-0000-0000-000000000000",
            "billing_period_start": "2025-06-01",
            "billing_period_end": "2025-06-30",
        },
        headers=auth_headers(csrf),
    )
    assert response.status_code == 403


def test_only_admin_can_create_users(client, db):
    org, user = create_org_with_admin(db, "fm1", role=UserRole.finance_manager)
    csrf = login(client, user)
    response = client.post(
        "/api/v1/users",
        json={"email": "new@testmail.dev", "full_name": "N", "role": "reviewer"},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 403


class TestUploadSecurity:
    def test_oversized_upload_rejected(self, client, db):
        org, user = create_org_with_admin(db, "up1")
        csrf = login(client, user)
        big = b"%PDF-1.4 " + b"x" * (26 * 1024 * 1024)
        response = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "other"},
            files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
            headers=auth_headers(csrf),
        )
        assert response.status_code == 413

    def test_unsupported_type_rejected(self, client, db):
        org, user = create_org_with_admin(db, "up2")
        csrf = login(client, user)
        response = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "other"},
            files={"file": ("evil.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
            headers=auth_headers(csrf),
        )
        assert response.status_code == 415

    def test_mime_extension_mismatch_rejected(self, client, db):
        org, user = create_org_with_admin(db, "up3")
        csrf = login(client, user)
        response = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "other"},
            files={"file": ("c.pdf", io.BytesIO(PDF), "text/html")},
            headers=auth_headers(csrf),
        )
        assert response.status_code == 415

    def test_malicious_filename_sanitized(self, client, db):
        org, user = create_org_with_admin(db, "up4")
        csrf = login(client, user)
        response = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "other"},
            files={"file": ("../../etc/passwd.pdf", io.BytesIO(PDF), "application/pdf")},
            headers=auth_headers(csrf),
        )
        assert response.status_code == 201
        assert "/" not in response.json()["document"]["original_filename"]

    def test_duplicate_file_detected(self, client, db):
        org, user = create_org_with_admin(db, "up5")
        csrf = login(client, user)
        payload = {
            "data": {"document_type": "other"},
            "files": {"file": ("c.pdf", io.BytesIO(PDF), "application/pdf")},
            "headers": auth_headers(csrf),
        }
        first = client.post("/api/v1/documents/upload", **payload)
        assert first.status_code == 201
        assert first.json()["duplicate_of"] is None
        payload["files"] = {"file": ("c.pdf", io.BytesIO(PDF), "application/pdf")}
        second = client.post("/api/v1/documents/upload", **payload)
        assert second.status_code == 201
        assert second.json()["duplicate_of"] == first.json()["document"]["id"]

    def test_stored_xss_string_preserved_not_executed(self, client, db):
        """XSS payload in a filename is stored literally (escaping is the client's
        job; the API must not execute or reflect it as HTML)."""
        org, user = create_org_with_admin(db, "up6")
        csrf = login(client, user)
        response = client.post(
            "/api/v1/documents/upload",
            data={"document_type": "other"},
            files={"file": ("<script>alert(1)</script>.pdf", io.BytesIO(PDF), "application/pdf")},
            headers=auth_headers(csrf),
        )
        assert response.status_code == 201
        name = response.json()["document"]["original_filename"]
        assert "<script>" not in name  # sanitized to safe characters
