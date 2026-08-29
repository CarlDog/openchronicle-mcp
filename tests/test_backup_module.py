"""Tests for the online backup module."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from openchronicle.core.infrastructure.persistence import backup
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _seeded_store(tmp_path: Path) -> SqliteStore:
    store = SqliteStore(str(tmp_path / "src.db"))
    store.init_schema()
    from openchronicle.core.domain.models.memory_item import MemoryItem
    from openchronicle.core.domain.models.project import Project

    project = Project(name="test")
    store.add_project(project)
    for i in range(5):
        store.add_memory(MemoryItem(content=f"row {i}", project_id=project.id, source="test"))
    return store


def test_backup_from_connection_preserves_rows(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    dest = tmp_path / "out.db"
    backup.backup_from_connection(store._conn, dest)
    store.close()

    # Read the backup with a fresh store; ensure rows survive.
    restored = SqliteStore(str(dest))
    items = restored.list_memory()
    assert len(items) == 5
    restored.close()


def test_backup_atomic_rename_no_tmp_left(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    dest = tmp_path / "out.db"
    backup.backup_from_connection(store._conn, dest)
    store.close()

    leftover_tmp = dest.with_name(dest.name + ".tmp")
    assert not leftover_tmp.exists(), "atomic rename should remove the .tmp"


def test_backup_overwrites_existing_destination(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    dest = tmp_path / "out.db"
    dest.write_bytes(b"stale content")
    backup.backup_from_connection(store._conn, dest)
    store.close()

    # Overwrite means the file is now a real DB
    conn = sqlite3.connect(str(dest))
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "memory_items" in names
    finally:
        conn.close()


def test_backup_during_concurrent_writes(tmp_path: Path) -> None:
    """Online backup snapshots safely while writes are in flight."""
    store = _seeded_store(tmp_path)
    dest = tmp_path / "out.db"
    stop_event = threading.Event()

    def _writer() -> None:
        from openchronicle.core.domain.models.memory_item import MemoryItem

        i = 0
        while not stop_event.is_set():
            try:
                store.add_memory(MemoryItem(content=f"concurrent {i}", source="bg"))
            except sqlite3.OperationalError:
                pass
            i += 1
            time.sleep(0.005)

    writer = threading.Thread(target=_writer, daemon=True)
    writer.start()
    try:
        # While writer thrashes the source, take the backup.
        backup.backup_from_connection(store._conn, dest)
    finally:
        stop_event.set()
        writer.join(timeout=2)

    # Backup must be readable and pass integrity check.
    conn = sqlite3.connect(str(dest))
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        assert result == "ok"
    finally:
        conn.close()
    store.close()


def test_backup_failure_cleans_up_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the rename step fails, the .tmp file should be removed.

    sqlite3.Connection is a C type and its `backup` method can't be
    monkeypatched, so we induce failure at the os.replace step instead —
    the contract we care about is "no half-written backup left behind."
    """
    store = _seeded_store(tmp_path)
    dest = tmp_path / "out.db"

    real_replace = backup.os.replace

    def _explode(*args: object, **kwargs: object) -> None:  # noqa: ARG001
        raise OSError("simulated rename failure")

    monkeypatch.setattr(backup.os, "replace", _explode)
    with pytest.raises(OSError, match="simulated rename failure"):
        backup.backup_from_connection(store._conn, dest)

    leftover_tmp = dest.with_name(dest.name + ".tmp")
    assert not leftover_tmp.exists()
    assert not dest.exists()

    # Restore for cleanup safety (autouse on session scope can leak otherwise)
    monkeypatch.setattr(backup.os, "replace", real_replace)
    store.close()


# ── validate-before-publish (0003 F5 / 0004 F8) ────────────────────────


def test_valid_backup_publishes_and_leaves_no_quarantine(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    dest = tmp_path / "out.db"
    backup.backup_from_connection(store._conn, dest)
    store.close()
    assert dest.exists()
    assert not (tmp_path / "out.db.failed-quick-check").exists()
    assert not (tmp_path / "out.db.tmp").exists()


def test_validate_staged_rejects_garbage(tmp_path: Path) -> None:
    garbage = tmp_path / "garbage.db"
    garbage.write_bytes(b"this is not a sqlite database, not even close" * 100)
    with pytest.raises(backup.BackupValidationError):
        backup._validate_staged(garbage)


def test_failed_validation_preserves_previous_backup_and_quarantines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The previous good artifact must survive, and the invalid staged
    file must be kept as forensic evidence — not deleted, not published."""
    store = _seeded_store(tmp_path)
    dest = tmp_path / "out.db"
    previous = b"previous good backup bytes"
    dest.write_bytes(previous)

    def _always_fail(tmp: Path) -> None:
        raise backup.BackupValidationError("staged backup failed quick_check: 'boom'")

    monkeypatch.setattr(backup, "_validate_staged", _always_fail)
    with pytest.raises(backup.BackupValidationError):
        backup.backup_from_connection(store._conn, dest)
    store.close()

    assert dest.read_bytes() == previous, "an unvalidated artifact must never replace the previous backup"
    quarantine = tmp_path / "out.db.failed-quick-check"
    assert quarantine.exists(), "the invalid artifact is evidence, not trash"
    assert not (tmp_path / "out.db.tmp").exists()


def test_quarantine_name_is_outside_the_retention_glob(tmp_path: Path) -> None:
    """_retention_prune globs *.db non-recursively; the quarantine file
    must never be pruned as if it were a restorable backup."""
    from openchronicle.core.infrastructure.maintenance.jobs import _retention_prune

    (tmp_path / "openchronicle-1.db").write_bytes(b"a")
    quarantine = tmp_path / "openchronicle-1.db.failed-quick-check"
    quarantine.write_bytes(b"evidence")
    _retention_prune(tmp_path, keep=1)
    assert quarantine.exists()
