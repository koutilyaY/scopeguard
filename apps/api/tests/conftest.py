"""Shared test fixtures.

Integration tests run against a real Postgres (scopeguard_test database on the
compose postgres container). The schema is migrated once per session via Alembic;
each test gets a clean slate through table truncation. The LLM provider is always
the deterministic fake; Celery runs eagerly in-process.
"""

import os
import uuid

# Must be set before app modules import settings.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://scopeguard:scopeguard-dev-password@localhost:5433/scopeguard_test",
)
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9002")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/9")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("MINIO_BUCKET", "scopeguard-test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.models import Base, Organization, User
from app.models.enums import UserRole
from app.security.passwords import hash_password
from app.security.rate_limit import reset_memory_limits
from app.services.llm import set_llm_provider
from app.services.llm.fake import FakeLLMProvider


def _database_error() -> str | None:
    """Return None when the test database is usable, else the reason it is not."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return None
    except Exception as exc:  # surfaced loudly below — never silently skipped
        return f"{type(exc).__name__}: {exc}"


_DB_ERROR = _database_error()

# A DB-less run silently skips ~1/3 of the suite (tenant isolation, auth, the review
# pipeline) while still exiting 0 — a green run that proves almost nothing. Fail loudly
# by default; set SCOPEGUARD_ALLOW_DB_SKIP=1 only for a deliberate offline unit-only run.
if _DB_ERROR and os.environ.get("SCOPEGUARD_ALLOW_DB_SKIP") != "1":
    raise RuntimeError(
        "Test database is not reachable, so database-backed tests would be silently "
        f"skipped.\n  DATABASE_URL: {os.environ.get('DATABASE_URL')}\n  Error: {_DB_ERROR}\n"
        "Start it with `make dev` (or set SCOPEGUARD_ALLOW_DB_SKIP=1 to run unit tests only "
        "and accept the skips)."
    )

requires_db = pytest.mark.skipif(
    _DB_ERROR is not None,
    reason=f"Postgres test database not reachable ({_DB_ERROR})",
)


@pytest.fixture(scope="session")
def migrated_db():
    """Migrate the test database from empty via Alembic (also tests migrations)."""
    from alembic.config import Config

    from alembic import command

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    config = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    config.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "alembic")
    )
    command.upgrade(config, "head")
    yield engine


@pytest.fixture
def db(migrated_db):
    """Clean database session; truncates all tables after each test."""
    session = get_sessionmaker()()
    yield session
    session.rollback()
    session.close()
    with migrated_db.connect() as conn:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        conn.commit()


@pytest.fixture(autouse=True)
def fake_llm():
    provider = FakeLLMProvider()
    set_llm_provider(provider)
    yield provider
    set_llm_provider(None)


@pytest.fixture(autouse=True)
def eager_celery():
    from app.worker import celery_app

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield


@pytest.fixture(autouse=True)
def clean_rate_limits():
    reset_memory_limits()
    # The limiter prefers Redis when reachable; clear its state between tests too.
    try:
        import redis as _redis

        _redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1).flushdb()
    except Exception:
        pass
    yield


@pytest.fixture
def client(db):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


PASSWORD = "Sup3r-Secure-Passw0rd"


def create_org_with_admin(db, slug: str, role: UserRole = UserRole.organization_admin):
    org = Organization(name=f"{slug} Org", slug=slug)
    db.add(org)
    db.flush()
    user = User(
        organization_id=org.id,
        email=f"admin-{slug}-{uuid.uuid4().hex[:6]}@testmail.dev",
        full_name=f"{slug} admin",
        hashed_password=hash_password(PASSWORD),
        role=role,
        active=True,
    )
    db.add(user)
    db.commit()
    return org, user


def login(client: TestClient, user: User) -> str:
    """Log in and return the CSRF token; cookies persist on the client."""
    response = client.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def auth_headers(csrf: str) -> dict[str, str]:
    return {"X-CSRF-Token": csrf}
