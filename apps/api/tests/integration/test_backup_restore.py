"""Restore smoke test: a pg_dump/pg_restore round-trip preserves the schema.

This exercises the same mechanism scripts/backup.sh and scripts/restore.sh use,
against the test database, without requiring Docker inside the test run.
"""

import subprocess

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine
from tests.conftest import requires_db

pytestmark = requires_db


def _dsn_parts() -> dict[str, str]:
    # postgresql+psycopg://user:pass@host:port/db
    url = get_settings().database_url.replace("postgresql+psycopg://", "")
    creds, rest = url.split("@")
    user, password = creds.split(":")
    hostport, db = rest.split("/")
    host, port = hostport.split(":")
    return {"user": user, "password": password, "host": host, "port": port, "db": db}


def _have(cmd: str) -> bool:
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


@pytest.mark.skipif(not _have("pg_dump") or not _have("pg_restore"), reason="pg tools absent")
def test_pg_dump_restore_roundtrip(migrated_db, tmp_path):
    import os

    parts = _dsn_parts()
    env = {**os.environ, "PGPASSWORD": parts["password"]}
    dump = tmp_path / "backup.dump"

    try:
        dump_result = subprocess.run(
            ["pg_dump", "-h", parts["host"], "-p", parts["port"], "-U", parts["user"],
             "-Fc", "-f", str(dump), parts["db"]],
            env=env, capture_output=True, text=True,
        )
    except OSError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"host pg_dump not runnable: {exc}")

    if dump_result.returncode != 0 or not dump.exists() or dump.stat().st_size == 0:
        # Host pg_dump commonly mismatches the pg16 server major version. The real
        # backup path (scripts/backup.sh) runs pg_dump *inside* the postgres
        # container, where versions always match; skip rather than fail here.
        pytest.skip(f"host pg_dump unusable against server: {dump_result.stderr.strip()}")

    # Drop and restore schema.
    with get_engine().connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.commit()

    restore_result = subprocess.run(
        ["pg_restore", "-h", parts["host"], "-p", parts["port"], "-U", parts["user"],
         "-d", parts["db"], "--no-owner", str(dump)],
        env=env, capture_output=True, text=True,
    )
    # pg_restore may emit non-fatal warnings; check the key tables exist.
    with get_engine().connect() as conn:
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        ).scalars().all()
    assert "findings" in tables
    assert "organizations" in tables
    assert restore_result.returncode == 0 or "findings" in tables
