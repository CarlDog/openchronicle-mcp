"""Tests for the SQLite migration framework."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from openchronicle.core.domain.exceptions import ConfigError
from openchronicle.core.infrastructure.persistence import migrator


def _new_conn(tmp_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "test.db"), isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def test_apply_pending_creates_schema_version_on_fresh_db(tmp_path: Path) -> None:
    conn = _new_conn(tmp_path)
    try:
        applied = migrator.apply_pending(conn)
        assert applied == [1, 2, 3, 4], "001 baseline + 002/003 embedding identity + 004 status on a fresh DB"

        version = migrator.current_version(conn)
        assert version == 4

        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        assert [r["version"] for r in rows] == [1, 2, 3, 4]
    finally:
        conn.close()


def test_apply_pending_is_idempotent(tmp_path: Path) -> None:
    conn = _new_conn(tmp_path)
    try:
        first = migrator.apply_pending(conn)
        second = migrator.apply_pending(conn)
        assert first == [1, 2, 3, 4]
        assert second == [], "second pass should be a no-op"
        assert migrator.current_version(conn) == 4
    finally:
        conn.close()


def test_baseline_schema_creates_expected_tables(tmp_path: Path) -> None:
    conn = _new_conn(tmp_path)
    try:
        migrator.apply_pending(conn)
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        names = {r["name"] for r in rows}
        assert {"projects", "memory_items", "memory_embeddings", "schema_version"} <= names
    finally:
        conn.close()


def test_failure_rolls_back_via_savepoint(tmp_path: Path) -> None:
    """A bad migration must not leave a partial schema or an applied row."""
    bad_dir = tmp_path / "migrations"
    bad_dir.mkdir()
    (bad_dir / "001_initial.sql").write_text(
        "CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY, applied_at TEXT NOT NULL);"
        "CREATE TABLE good (id INTEGER);"
    )

    conn = _new_conn(tmp_path)
    try:
        # First pass — only 001 present, succeeds.
        migrator.apply_pending(conn, migrations_dir=bad_dir)
        assert migrator.current_version(conn) == 1

        # Now drop a broken migration in and re-run.
        (bad_dir / "002_broken.sql").write_text("CREATE TABLE another (id INTEGER);INTENTIONAL SYNTAX ERROR;")

        with pytest.raises(ConfigError, match="002_broken.sql failed"):
            migrator.apply_pending(conn, migrations_dir=bad_dir)

        # 002 must NOT be recorded; the savepoint rolled back.
        assert migrator.current_version(conn) == 1
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='another'").fetchall()
        assert rows == [], "partial migration leaked the 'another' table"
    finally:
        conn.close()


def test_split_sql_handles_comments_and_blanks() -> None:
    script = """
    -- Header comment
    CREATE TABLE foo (id INTEGER);

    -- Another section
    CREATE TABLE bar (id INTEGER);
    """
    parts = migrator._split_sql(script)
    assert len(parts) == 2
    assert parts[0].startswith("CREATE TABLE foo")
    assert parts[1].startswith("CREATE TABLE bar")


def test_migration_004_applies_to_a_populated_db(tmp_path: Path) -> None:
    """ADR 0009: a pre-004 database with real embedding rows migrates in
    place — every existing row gets status='ok' — and a re-run is a
    no-op."""
    import shutil

    pre_004_dir = tmp_path / "pre_004"
    pre_004_dir.mkdir()
    real_dir = Path(migrator.__file__).parent / "migrations"
    for name in ("001_initial.sql", "002_embedding_identity.sql", "003_embedding_space_fingerprint.sql"):
        shutil.copy(real_dir / name, pre_004_dir / name)

    conn = _new_conn(tmp_path)
    try:
        # A populated pre-004 database (no status column yet).
        assert migrator.apply_pending(conn, migrations_dir=pre_004_dir) == [1, 2, 3]
        conn.execute("INSERT INTO projects (id, name, metadata, created_at) VALUES ('p', 'p', '{}', '2026-01-01')")
        conn.execute(
            "INSERT INTO memory_items (id, content, tags, created_at, pinned, source, project_id)"
            " VALUES ('m1', 'alpha', '[]', '2026-01-01', 0, 'test', 'p')"
        )
        conn.execute(
            "INSERT INTO memory_embeddings (memory_id, embedding, model, dimensions, generated_at,"
            " provider, content_hash, model_revision, settings_fingerprint)"
            " VALUES ('m1', X'0000803F', 'test-model', 1, '2026-01-01', 'test-provider', 'hash', NULL, 'fp')"
        )

        applied = migrator.apply_pending(conn)
        assert applied == [4]
        row = conn.execute("SELECT status FROM memory_embeddings WHERE memory_id = 'm1'").fetchone()
        assert row["status"] == "ok", "existing rows default to 'ok' — real vectors, not tombstones"

        assert migrator.apply_pending(conn) == [], "re-run is a no-op"
        assert migrator.current_version(conn) == 4
    finally:
        conn.close()


def test_unknown_filenames_are_skipped(tmp_path: Path) -> None:
    custom_dir = tmp_path / "migrations"
    custom_dir.mkdir()
    (custom_dir / "001_initial.sql").write_text(
        "CREATE TABLE schema_version (version INTEGER NOT NULL PRIMARY KEY, applied_at TEXT NOT NULL);"
    )
    (custom_dir / "ignored.txt").write_text("not a migration")
    (custom_dir / "no-version.sql").write_text("oops")

    conn = _new_conn(tmp_path)
    try:
        applied = migrator.apply_pending(conn, migrations_dir=custom_dir)
        assert applied == [1]
    finally:
        conn.close()
