"""End-to-end tests for the v2→v3 one-shot migration script.

Synthesizes a small v2-shaped DB at runtime, runs migrate_v2_to_v3.migrate,
then asserts the v3 invariants the production cutover will rely on.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

# Add scripts/ to sys.path so we can import the migrate module by name.
_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import migrate_v2_to_v3  # type: ignore[import-not-found]  # noqa: E402
import verify_v3_db  # type: ignore[import-not-found]  # noqa: E402

# --- v2 schema fixture -------------------------------------------------------

_V2_SCHEMA = """
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT,
    mode TEXT DEFAULT 'general',
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE memory_items (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    tags TEXT NOT NULL,
    created_at TEXT NOT NULL,
    pinned INTEGER NOT NULL,
    conversation_id TEXT,
    project_id TEXT,
    source TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE memory_embeddings (
    memory_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    FOREIGN KEY(memory_id) REFERENCES memory_items(id) ON DELETE CASCADE
);

-- Tables that should NOT carry over to v3:
CREATE TABLE tasks (id TEXT PRIMARY KEY, project_id TEXT, type TEXT, status TEXT, payload TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE events (id TEXT PRIMARY KEY, project_id TEXT, type TEXT, payload TEXT, created_at TEXT);
CREATE TABLE webhooks (id TEXT PRIMARY KEY, project_id TEXT, url TEXT, secret TEXT, event_filter TEXT, active INTEGER, created_at TEXT, description TEXT);
"""


def _make_v2_db(path: Path) -> dict[str, int]:
    """Populate `path` with a minimal v2-shaped DB. Returns row counts."""
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(_V2_SCHEMA)

        # Two projects, four memory items (one with conversation_id set,
        # one with project_id None), one embedding.
        conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            ("p1", "Active project", "{}", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            ("p2", "Old project", "{}", "2025-06-01T00:00:00+00:00"),
        )

        conn.execute(
            "INSERT INTO conversations (id, project_id, title, mode, created_at) VALUES (?, ?, ?, ?, ?)",
            ("c1", "p1", "test", "general", "2026-02-01T00:00:00+00:00"),
        )

        rows = [
            ("m1", "alpha", '["tag-a"]', "2026-02-10T00:00:00+00:00", 1, "c1", "p1", "mcp", None),
            ("m2", "beta", '["tag-b"]', "2026-02-11T00:00:00+00:00", 0, None, "p1", "manual", None),
            ("m3", "gamma", "[]", "2025-08-01T00:00:00+00:00", 0, None, "p2", "manual", None),
            ("m4", "delta", '["tag-c"]', "2026-03-01T00:00:00+00:00", 0, None, None, "manual", None),
        ]
        conn.executemany(
            "INSERT INTO memory_items "
            "(id, content, tags, created_at, pinned, conversation_id, project_id, source, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )

        conn.execute(
            "INSERT INTO memory_embeddings "
            "(memory_id, embedding, model, dimensions, generated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("m1", b"\x00\x00\x80\x3f" * 4, "stub", 4, "2026-02-10T00:00:00+00:00"),
        )

        # Noise rows in dropped tables — should NOT carry over.
        conn.execute(
            "INSERT INTO tasks (id, project_id, type, status, payload, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("t1", "p1", "x", "completed", "{}", "2026-01-01", "2026-01-01"),
        )
        conn.commit()
    finally:
        conn.close()

    return {"projects": 2, "memory_items": 4, "embeddings": 1}


def test_migration_preserves_memory_and_projects(tmp_path: Path) -> None:
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    expected = _make_v2_db(src)

    summary = migrate_v2_to_v3.migrate(src, dest)
    assert summary == expected
    assert dest.is_file()


def test_migration_drops_v2_tables(tmp_path: Path) -> None:
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    migrate_v2_to_v3.migrate(src, dest)

    conn = sqlite3.connect(str(dest))
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()

    forbidden = {"tasks", "events", "webhooks", "conversations"}
    assert not (forbidden & names), f"v2 tables leaked into v3: {forbidden & names}"


def test_migration_drops_conversation_id_column(tmp_path: Path) -> None:
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    migrate_v2_to_v3.migrate(src, dest)

    conn = sqlite3.connect(str(dest))
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(memory_items)").fetchall()]
    finally:
        conn.close()
    assert "conversation_id" not in cols


def test_migration_records_schema_version_1(tmp_path: Path) -> None:
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    migrate_v2_to_v3.migrate(src, dest)

    conn = sqlite3.connect(str(dest))
    try:
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    finally:
        conn.close()
    assert version == 1


def test_migration_passes_verify_v3(tmp_path: Path) -> None:
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    migrate_v2_to_v3.migrate(src, dest)

    report = verify_v3_db.verify(dest)
    assert report["ok"], f"verify_v3 failed: {report['failures']}"


def test_migration_refuses_existing_dest_without_force(tmp_path: Path) -> None:
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    dest.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        migrate_v2_to_v3.migrate(src, dest)
    # Existing file untouched.
    assert dest.read_bytes() == b"existing"


def test_migration_force_overwrites_dest(tmp_path: Path) -> None:
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    dest.write_bytes(b"stale content")
    summary = migrate_v2_to_v3.migrate(src, dest, force=True)
    assert summary["projects"] == 2


def test_migration_refuses_orphan_wal_at_destination(tmp_path: Path) -> None:
    """Triage 2026-05-06: orphan -wal/-shm at the dest path can corrupt
    the freshly-placed DB on first open. Migration script must refuse
    rather than silently produce a borderline-broken result."""
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    # Simulate an orphan WAL left over from a prior process or a previous
    # DB that lived at this path stem.
    (tmp_path / "v3.db-wal").write_bytes(b"orphan wal content")

    with pytest.raises(FileExistsError, match="Orphan SQLite sidecar"):
        migrate_v2_to_v3.migrate(src, dest)
    # Orphan untouched without --force.
    assert (tmp_path / "v3.db-wal").exists()


def test_migration_force_scrubs_orphan_sidecars(tmp_path: Path) -> None:
    """With --force, the migration script removes orphan sidecars
    instead of refusing."""
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    (tmp_path / "v3.db-wal").write_bytes(b"orphan wal content")
    (tmp_path / "v3.db-shm").write_bytes(b"orphan shm content")

    summary = migrate_v2_to_v3.migrate(src, dest, force=True)
    assert summary["projects"] == 2
    # Sidecars from the migration's own connection may exist post-write,
    # but the orphan content we seeded is gone (size differs).
    if (tmp_path / "v3.db-wal").exists():
        assert (tmp_path / "v3.db-wal").read_bytes() != b"orphan wal content"


def test_verify_warns_on_orphan_sidecars(tmp_path: Path) -> None:
    """verify_v3_db should surface orphan sidecars as a warning."""
    src = tmp_path / "v2.db"
    dest = tmp_path / "v3.db"
    _make_v2_db(src)
    migrate_v2_to_v3.migrate(src, dest)
    # Seed an orphan sidecar after migration completes.
    (tmp_path / "v3.db-wal").write_bytes(b"unexpected wal")

    report = verify_v3_db.verify(dest)
    assert report["ok"], "DB itself is still valid; orphan is just a warning"
    assert any("orphan" in w.lower() for w in report["warnings"]), (
        f"expected orphan-sidecar warning in report['warnings'], got {report['warnings']!r}"
    )
