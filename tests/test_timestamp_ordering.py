"""UTC storage, chronological readers, and timestamp migration."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import add_memory, export_memory, import_memory
from openchronicle.core.domain.content_hash import hash_content
from openchronicle.core.domain.exceptions import ConfigError, ValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.persistence import migrator
from openchronicle.core.infrastructure.persistence.backup import backup_from_connection
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

CENTRAL = timezone(-timedelta(hours=5))


def _pre_005_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SqliteStore:
    migration_dir = Path(migrator.__file__).parent / "migrations"
    old_dir = tmp_path / "pre_005"
    old_dir.mkdir()
    for version in range(1, 5):
        source = next(migration_dir.glob(f"{version:03d}_*.sql"))
        shutil.copy(source, old_dir / source.name)
    monkeypatch.setattr(migrator, "_MIGRATIONS_DIR", old_dir)
    store = SqliteStore(str(tmp_path / "legacy.db"))
    store.init_schema()
    assert migrator.current_version(store._conn) == 4
    monkeypatch.setattr(migrator, "_MIGRATIONS_DIR", migration_dir)
    return store


def test_aware_writes_order_by_instant_across_readers_and_round_trip(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "current.db"))
    store.init_schema()
    try:
        store.add_project(Project(id="p-a", name="A", created_at=datetime(2026, 9, 23, 4, 0, tzinfo=CENTRAL)))
        store.add_project(Project(id="p-b", name="B", created_at=datetime(2026, 9, 23, 7, 0, tzinfo=UTC)))
        assert [p.id for p in store.list_projects()] == ["p-a", "p-b"]

        latest = datetime(2026, 9, 23, 4, 41, 37, 123456, tzinfo=CENTRAL)
        for item in (
            MemoryItem(id="b", content="needle", project_id="p-a", source="git", created_at=latest),
            MemoryItem(
                id="a",
                content="needle",
                project_id="p-a",
                source="git",
                created_at=datetime(2026, 9, 23, 7, 4, 17, tzinfo=UTC),
            ),
            MemoryItem(id="c", content="needle", project_id="p-a", source="git", created_at=latest),
        ):
            saved = add_memory.execute(store, item)
            assert saved.created_at.utcoffset() == timedelta(0)

        assert store.get_memory("b").created_at.isoformat() == "2026-09-23T09:41:37.123456+00:00"  # type: ignore[union-attr]
        assert [m.id for m in store.list_memory(order_by="created_at")] == ["c", "b", "a"]
        assert [m.id for m in store.list_memory(order_by="created_at", limit=1, offset=1)] == ["b"]
        assert [m.id for m in store.list_memory(limit=2, project_id="p-a")] == ["c", "b"]
        assert [m.id for m in store.list_memory_by_source("git")] == ["c", "b", "a"]
        assert {m.id for m in store.search_memory("needle")[:2]} == {"b", "c"}

        store._fts5_active = False
        assert {m.id for m in store.search_memory("needle")[:2]} == {"b", "c"}
        envelope = export_memory.execute(store, store)
        assert all(m["created_at"].endswith("+00:00") for m in envelope["memory_items"])

        restored = SqliteStore(str(tmp_path / "restored.db"))
        restored.init_schema()
        try:
            import_memory.execute(restored, restored, envelope, mode="replace")
            assert [m.id for m in restored.list_memory(order_by="created_at")] == ["c", "b", "a"]
        finally:
            restored.close()
    finally:
        store.close()


def test_direct_store_and_import_refuse_naive_timestamps(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "current.db"))
    store.init_schema()
    try:
        with pytest.raises(ValidationError, match="created_at must include a UTC offset"):
            store.add_project(Project(id="bad", name="bad", created_at=datetime(2026, 1, 1)))
        store.add_project(Project(id="p", name="P"))
        with pytest.raises(ValidationError, match="created_at must include a UTC offset"):
            store.add_memory(MemoryItem(id="bad", content="bad", project_id="p", created_at=datetime(2026, 1, 1)))
        with pytest.raises(ValidationError, match="updated_at must include a UTC offset"):
            store.add_memory(MemoryItem(id="bad", content="bad", project_id="p", updated_at=datetime(2026, 1, 1)))
        assert store.count_memory() == 0

        envelope = export_memory.execute(store, store)
        envelope["projects"][0]["created_at"] = "2026-01-01T00:00:00"
        empty = SqliteStore(str(tmp_path / "empty.db"))
        empty.init_schema()
        try:
            with pytest.raises(ValidationError, match=r"projects\[0\].*aware ISO-8601"):
                import_memory.execute(empty, empty, envelope, mode="replace")
            assert empty.list_projects() == []
        finally:
            empty.close()
    finally:
        store.close()


def test_pre_005_export_import_preserves_offset_instant(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = _pre_005_store(tmp_path, monkeypatch)
    try:
        old._conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES ('p', 'P', '{}', '2026-09-23T04:00:00-05:00')"
        )
        old._conn.execute(
            "INSERT INTO memory_items (id, content, tags, created_at, pinned, project_id, source)"
            " VALUES ('m', 'note', '[]', '2026-09-23T04:41:37.123456-05:00', 0, 'p', 'git')"
        )
        envelope = export_memory.execute(old, old)
    finally:
        old.close()

    restored = SqliteStore(str(tmp_path / "from-envelope.db"))
    restored.init_schema()
    try:
        import_memory.execute(restored, restored, envelope, mode="replace")
        assert restored.get_project("p").created_at.isoformat() == "2026-09-23T09:00:00+00:00"  # type: ignore[union-attr]
        assert restored.get_memory("m").created_at.isoformat() == "2026-09-23T09:41:37.123456+00:00"  # type: ignore[union-attr]
    finally:
        restored.close()


def test_005_preserves_instants_embeddings_and_fts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _pre_005_store(tmp_path, monkeypatch)
    try:
        store._conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            ("p", "P", "{}", "2026-09-23T04:00:00-05:00"),
        )
        store._conn.execute(
            "INSERT INTO memory_items (id, content, tags, created_at, pinned, project_id, source, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "older-text",
                "needle",
                '["tag"]',
                "2026-09-23T04:41:37.123456-05:00",
                0,
                "p",
                "git",
                "2026-09-23T04:42:00.654321-05:00",
            ),
        )
        store._conn.execute(
            "INSERT INTO memory_items (id, content, tags, created_at, pinned, project_id, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("newer-text", "needle", '["tag"]', "2026-09-23T07:04:17+00:00", 0, "p", "git"),
        )
        assert store.save_embedding("older-text", [1.0], "model", "stub", hash_content("needle"), "rev", "fp")
        identity = store.get_embedding_identity("older-text")
        assert [m.id for m in store.list_memory(order_by="created_at")] == ["newer-text", "older-text"]

        store.init_schema()
        assert migrator.current_version(store._conn) == 5
        assert store._conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert store.get_embedding_identity("older-text") == identity
        assert store.get_embedding("older-text") == [1.0]
        assert store.get_project("p").created_at.isoformat() == "2026-09-23T09:00:00+00:00"  # type: ignore[union-attr]
        migrated = store.get_memory("older-text")
        assert migrated is not None
        assert migrated.created_at.isoformat() == "2026-09-23T09:41:37.123456+00:00"
        assert migrated.updated_at is not None
        assert migrated.updated_at.isoformat() == "2026-09-23T09:42:00.654321+00:00"
        assert migrated.content == "needle" and migrated.tags == ["tag"] and migrated.project_id == "p"
        assert [m.id for m in store.list_memory(order_by="created_at")] == ["older-text", "newer-text"]
        assert [m.id for m in store.search_memory("needle")] == ["older-text", "newer-text"]
        assert migrator.apply_pending(store._conn) == []
    finally:
        store.close()


@pytest.mark.parametrize("bad", ["2026-09-23T04:41:37", "not-a-date"])
def test_005_refuses_uninterpretable_legacy_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad: str) -> None:
    store = _pre_005_store(tmp_path, monkeypatch)
    try:
        store._conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES ('p', 'P', '{}', '2026-09-23T04:00:00-05:00')"
        )
        store._conn.execute(
            "INSERT INTO memory_items (id, content, tags, created_at, pinned, project_id, source)"
            " VALUES (?, 'needle', '[]', ?, 0, 'p', 'git')",
            ("bad-row", bad),
        )
        with pytest.raises(ConfigError, match=r"005_normalize_timestamps.sql failed: 1 .*id='bad-row'"):
            store.init_schema()
        assert migrator.current_version(store._conn) == 4
        assert store._conn.execute("SELECT created_at FROM projects WHERE id='p'").fetchone()[0].endswith("-05:00")
        assert store._conn.execute("SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'needle'").fetchone()[0] == 1
    finally:
        store.close()


def test_005_rolls_back_after_partial_sql_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = _pre_005_store(tmp_path, monkeypatch)
    try:
        store._conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES ('p', 'P', '{}', '2026-09-23T04:00:00-05:00')"
        )
        store._conn.execute(
            "INSERT INTO memory_items (id, content, tags, created_at, pinned, project_id, source)"
            " VALUES ('m', 'needle', '[]', '2026-09-23T04:41:37-05:00', 0, 'p', 'git')"
        )
        store._conn.execute(
            "CREATE TRIGGER abort_timestamp_update BEFORE UPDATE ON memory_items"
            " BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
        with pytest.raises(ConfigError, match="forced failure"):
            store.init_schema()
        assert migrator.current_version(store._conn) == 4
        assert store._conn.execute("SELECT created_at FROM projects WHERE id='p'").fetchone()[0].endswith("-05:00")
        assert store.search_memory("needle")[0].id == "m"
    finally:
        store.close()


def test_pre_migration_online_backup_restores_legacy_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Disposable restore rehearsal; the live named volume still needs its own."""
    store = _pre_005_store(tmp_path, monkeypatch)
    try:
        store._conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES ('p', 'P', '{}', '2026-09-23T04:00:00-05:00')"
        )
        store._conn.execute(
            "INSERT INTO memory_items (id, content, tags, created_at, pinned, project_id, source)"
            " VALUES ('m', 'needle', '[]', '2026-09-23T04:41:37-05:00', 0, 'p', 'git')"
        )
        backup = backup_from_connection(store._conn, tmp_path / "pre-upgrade.db")
        store.init_schema()
        assert migrator.current_version(store._conn) == 5
    finally:
        store.close()

    restore_path = tmp_path / "restored-legacy.db"
    shutil.copy2(backup, restore_path)
    restored = SqliteStore(str(restore_path))
    try:
        assert migrator.current_version(restored._conn) == 4
        assert restored._conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert restored.get_memory("m").created_at.isoformat() == "2026-09-23T04:41:37-05:00"  # type: ignore[union-attr]
        assert (
            restored._conn.execute("SELECT count(*) FROM memory_fts WHERE memory_fts MATCH 'needle'").fetchone()[0] == 1
        )
    finally:
        restored.close()
