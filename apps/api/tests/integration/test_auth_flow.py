"""Authentication: login, session cookies, CSRF, lockout, password change."""

from sqlalchemy import select

from app.config import get_settings
from app.models import AuditEvent
from tests.conftest import PASSWORD, auth_headers, create_org_with_admin, login, requires_db

pytestmark = requires_db


def test_login_sets_httponly_cookie_and_csrf(client, db):
    org, user = create_org_with_admin(db, "acme1")
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200
    settings = get_settings()
    set_cookie = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookie if settings.session_cookie_name in c)
    assert "HttpOnly" in session_cookie
    assert response.json()["user"]["email"] == user.email
    assert response.json()["csrf_token"]


def test_wrong_password_rejected_generically(client, db):
    org, user = create_org_with_admin(db, "acme2")
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "WrongPass123"}
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_unknown_email_same_error(client, db):
    response = client.post(
        "/api/v1/auth/login", json={"email": "ghost@testmail.dev", "password": "Whatever123"}
    )
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_me_requires_session(client, db):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_after_login(client, db):
    org, user = create_org_with_admin(db, "acme3")
    login(client, user)
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["organization_id"] == str(org.id)


def test_account_lockout_after_failed_attempts(client, db):
    org, user = create_org_with_admin(db, "acme4")
    for _ in range(get_settings().login_max_attempts):
        client.post("/api/v1/auth/login", json={"email": user.email, "password": "Bad-Pass-1"})
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 423
    lock_events = (
        db.execute(select(AuditEvent).where(AuditEvent.action == "auth.account_locked"))
        .scalars()
        .all()
    )
    assert lock_events


def test_mutation_without_csrf_header_rejected(client, db):
    org, user = create_org_with_admin(db, "acme5")
    login(client, user)
    response = client.post("/api/v1/clients", json={"legal_name": "X Corp", "display_name": "X"})
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_mutation_with_wrong_csrf_rejected(client, db):
    org, user = create_org_with_admin(db, "acme6")
    login(client, user)
    response = client.post(
        "/api/v1/clients",
        json={"legal_name": "X Corp", "display_name": "X"},
        headers={"X-CSRF-Token": "f" * 64},
    )
    assert response.status_code == 403


def test_mutation_with_csrf_succeeds(client, db):
    org, user = create_org_with_admin(db, "acme7")
    csrf = login(client, user)
    response = client.post(
        "/api/v1/clients",
        json={"legal_name": "X Corp", "display_name": "X"},
        headers=auth_headers(csrf),
    )
    assert response.status_code == 201


def test_logout_invalidates_session(client, db):
    org, user = create_org_with_admin(db, "acme8")
    csrf = login(client, user)
    assert client.post("/api/v1/auth/logout", headers=auth_headers(csrf)).status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_change_password_rejects_weak_and_invalidates_sessions(client, db):
    org, user = create_org_with_admin(db, "acme9")
    csrf = login(client, user)
    weak = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=auth_headers(csrf),
    )
    assert weak.status_code == 422
    ok = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "An0ther-Great-Password"},
        headers=auth_headers(csrf),
    )
    assert ok.status_code == 200
    # old session is gone
    assert client.get("/api/v1/auth/me").status_code == 401


def test_passwords_are_argon2_hashed(db):
    org, user = create_org_with_admin(db, "acme10")
    assert user.hashed_password.startswith("$argon2id$")
    assert PASSWORD not in user.hashed_password
