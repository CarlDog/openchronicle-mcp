"""Disposable offline activation and rollback, including committed WAL data."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from scripts import offline_restore


def _abrupt_wal_insert(db: Path, memory_id: str) -> None:
    code = (
        "import os,sqlite3,sys; "
        "c=sqlite3.connect(sys.argv[1]); "
        "c.execute('PRAGMA wal_autocheckpoint=0'); "
        "c.execute('INSERT INTO memory_items VALUES (?, ?)', (sys.argv[2], 'project-1')); "
        "c.commit(); os._exit(0)"
    )
    subprocess.run([sys.executable, "-c", code, str(db), memory_id], check=True, timeout=10)
    wal = Path(f"{db}-wal")
    assert wal.is_file() and wal.stat().st_size > 0


def _stopped_wal_fixture(tmp_path: Path) -> tuple[Path, Path, offline_restore.BackupInfo]:
    db = tmp_path / "openchronicle.db"
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO schema_version VALUES (4)")
        conn.execute("CREATE TABLE projects(id TEXT PRIMARY KEY)")
        conn.execute("INSERT INTO projects VALUES ('project-1')")
        conn.execute("CREATE TABLE memory_items(id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id))")
        conn.execute("INSERT INTO memory_items VALUES ('before-snapshot', 'project-1')")
        conn.execute("CREATE TABLE memory_embeddings(memory_id TEXT PRIMARY KEY)")
        conn.commit()

    stage = tmp_path / ".restore-stage"
    stage.mkdir()
    candidate = stage / f"candidate-{'a' * 24}.db"
    with closing(sqlite3.connect(db)) as source, closing(sqlite3.connect(candidate)) as target:
        source.backup(target)
    expected = offline_restore._inspect(candidate)

    # Abrupt exit leaves a committed marker in a nonempty WAL. Normal close
    # would checkpoint/delete the sidecar and make this test vacuous.
    _abrupt_wal_insert(db, "after-snapshot")
    return db, candidate, expected


def _count(db: Path) -> int:
    with closing(sqlite3.connect(db)) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()[0])


def test_offline_activation_and_rollback_preserve_post_snapshot_wal_write(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    dry_run = offline_restore.activate(
        db, candidate, "drill-001", expected["sha256"], expected["schema_version"], expected["project_identity_sha256"]
    )
    assert dry_run["applied"] is False
    assert not (tmp_path / ".recovery").exists()

    result = offline_restore.activate(
        db,
        candidate,
        "drill-001",
        expected["sha256"],
        expected["schema_version"],
        expected["project_identity_sha256"],
        apply=True,
    )
    recovery = Path(result["recovery_dir"])
    assert candidate.exists(), "the staged source must remain available"
    assert (recovery / "raw-old" / "openchronicle.db-wal").stat().st_size > 0
    assert _count(recovery / "old-consistent.db") == 2
    assert _count(db) == 1

    assert offline_restore.rollback(db, "drill-001")["applied"] is False
    rolled_back = offline_restore.rollback(db, "drill-001", apply=True)
    assert rolled_back["state"]["phase"] == "rolled_back"
    assert _count(db) == 2
    assert (recovery / "forward-state" / "openchronicle.db").exists()
    with pytest.raises(offline_restore.RestoreError, match="No verified old-state"):
        offline_restore.rollback(db, "drill-001", apply=True)


def test_bad_candidate_identity_never_creates_recovery_state(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    with pytest.raises(offline_restore.RestoreError, match="differs from expected"):
        offline_restore.activate(
            db,
            candidate,
            "drill-002",
            "0" * 64,
            expected["schema_version"],
            expected["project_identity_sha256"],
            apply=True,
        )
    assert _count(db) == 2
    assert not (tmp_path / ".recovery").exists()


def test_abort_after_sidecar_move_can_roll_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    real_replace = offline_restore.os.replace

    def fail_at_swap(source: str | Path, target: str | Path) -> None:
        if Path(source).name.startswith(".incoming-") and Path(target) == db:
            raise OSError("simulated interruption before candidate installation")
        real_replace(source, target)

    monkeypatch.setattr(offline_restore.os, "replace", fail_at_swap)
    with pytest.raises(OSError, match="simulated interruption"):
        offline_restore.activate(
            db,
            candidate,
            "drill-003",
            expected["sha256"],
            expected["schema_version"],
            expected["project_identity_sha256"],
            apply=True,
        )
    monkeypatch.setattr(offline_restore.os, "replace", real_replace)
    assert offline_restore._load_state(tmp_path / ".recovery" / "drill-003")["phase"] == "prepared"
    offline_restore.rollback(db, "drill-003", apply=True)
    assert _count(db) == 2


def test_interrupted_rollback_retries_from_verified_forward_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    offline_restore.activate(
        db,
        candidate,
        "drill-004",
        expected["sha256"],
        expected["schema_version"],
        expected["project_identity_sha256"],
        apply=True,
    )
    _abrupt_wal_insert(db, "candidate-write")
    real_replace = offline_restore.os.replace

    def fail_at_rollback_swap(source: str | Path, target: str | Path) -> None:
        if Path(source).name.startswith(".rollback-") and Path(target) == db:
            raise OSError("simulated interruption during rollback")
        real_replace(source, target)

    monkeypatch.setattr(offline_restore.os, "replace", fail_at_rollback_swap)
    with pytest.raises(OSError, match="simulated interruption"):
        offline_restore.rollback(db, "drill-004", apply=True)
    monkeypatch.setattr(offline_restore.os, "replace", real_replace)
    recovery = tmp_path / ".recovery" / "drill-004"
    assert offline_restore._load_state(recovery)["phase"] == "rolling_back"
    assert (recovery / "forward-state" / "openchronicle.db").exists()
    displaced_wal = recovery / "forward-state" / "displaced-openchronicle.db-wal"
    original_wal = displaced_wal.read_bytes()
    assert original_wal
    displaced_wal.write_bytes(b"tampered")
    with pytest.raises(offline_restore.RestoreError, match="Displaced sidecar"):
        offline_restore.rollback(db, "drill-004", apply=True)
    displaced_wal.write_bytes(original_wal)
    offline_restore.rollback(db, "drill-004", apply=True)
    assert _count(db) == 2


def test_partial_forward_archive_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    offline_restore.activate(
        db,
        candidate,
        "drill-005",
        expected["sha256"],
        expected["schema_version"],
        expected["project_identity_sha256"],
        apply=True,
    )
    real_copy = offline_restore._copy_durable

    def fail_archiving_forward(source: Path, target: Path) -> None:
        if target.parent.name == "forward-state":
            raise OSError("simulated interrupted forward archive")
        real_copy(source, target)

    monkeypatch.setattr(offline_restore, "_copy_durable", fail_archiving_forward)
    with pytest.raises(OSError, match="simulated interrupted"):
        offline_restore.rollback(db, "drill-005", apply=True)
    monkeypatch.setattr(offline_restore, "_copy_durable", real_copy)
    with pytest.raises(offline_restore.RestoreError, match="Incomplete forward archive"):
        offline_restore.rollback(db, "drill-005", apply=True)


def test_retire_stage_after_completed_rollback_releases_stage_slot(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    offline_restore.activate(
        db,
        candidate,
        "drill-006",
        expected["sha256"],
        expected["schema_version"],
        expected["project_identity_sha256"],
        apply=True,
    )
    offline_restore.rollback(db, "drill-006", apply=True)
    assert offline_restore.retire_stage(db, "drill-006")["applied"] is False
    assert candidate.exists()
    assert offline_restore.retire_stage(db, "drill-006", apply=True)["stage_retired"] is True
    assert not candidate.exists()
    assert list(candidate.parent.glob("*.db")) == []
    assert offline_restore.retire_stage(db, "drill-006", apply=True)["applied"] is False
