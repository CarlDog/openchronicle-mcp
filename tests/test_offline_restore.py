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
    with pytest.raises(offline_restore.RestoreError, match="Nothing to roll back in phase"):
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


# ── Review fixes (2026-09-24): damaged stores, retry deadlock, guard coverage ──


def _activate(db: Path, candidate: Path, op: str, expected: offline_restore.BackupInfo) -> dict[str, object]:
    return offline_restore.activate(
        db,
        candidate,
        op,
        expected["sha256"],
        expected["schema_version"],
        expected["project_identity_sha256"],
        apply=True,
    )


def _family_digests(db: Path) -> dict[str, str]:
    return {path.name: offline_restore._sha256(path) for path in offline_restore._family(db)}


def _ids(db: Path) -> list[str]:
    with closing(sqlite3.connect(db)) as conn:
        return [str(row[0]) for row in conn.execute("SELECT id FROM memory_items ORDER BY id")]


def test_identical_candidate_interrupted_rollback_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No post-snapshot write: old-consistent is byte-identical to the candidate.

    An interrupted rollback used to be refused forever ("Unexpected sidecars
    appeared after rollback installation") because digest equality alone was
    read as "already installed".
    """
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    with closing(sqlite3.connect(db)) as conn:  # drop the fixture's post-snapshot row
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("DELETE FROM memory_items WHERE id = 'after-snapshot'")
        conn.commit()
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    stage_fresh = candidate.parent / f"candidate-{'b' * 24}.db"
    with closing(sqlite3.connect(db)) as source, closing(sqlite3.connect(stage_fresh)) as target:
        source.backup(target)
    candidate.unlink()
    expected = offline_restore._inspect(stage_fresh)
    result = _activate(db, stage_fresh, "same-digest", expected)
    state = result["state"]
    assert isinstance(state, dict)
    assert state["old_state"]["sha256"] == expected["sha256"]
    _abrupt_wal_insert(db, "candidate-write")
    real_copy = offline_restore._copy_durable

    def crash_on_rollback_copy(source: Path, target: Path) -> None:
        if target.name.startswith(".rollback-"):
            raise OSError("power loss while copying the rollback file")
        real_copy(source, target)

    monkeypatch.setattr(offline_restore, "_copy_durable", crash_on_rollback_copy)
    with pytest.raises(OSError, match="power loss"):
        offline_restore.rollback(db, "same-digest", apply=True)
    monkeypatch.setattr(offline_restore, "_copy_durable", real_copy)
    assert offline_restore.rollback(db, "same-digest", apply=True)["state"]["phase"] == "rolled_back"
    assert _ids(db) == ["before-snapshot"]
    forward = tmp_path / ".recovery" / "same-digest" / "forward-state"
    assert (forward / "displaced-openchronicle.db-wal").stat().st_size > 0


def test_retry_refuses_a_writing_restart_after_rollback_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    _activate(db, candidate, "wrong-restart", expected)
    real_save = offline_restore._save_state

    def crash_before_rolled_back(recovery: Path, state: dict[str, object]) -> None:
        if state.get("phase") == "rolled_back":
            raise OSError("power loss after installation")
        real_save(recovery, state)

    monkeypatch.setattr(offline_restore, "_save_state", crash_before_rolled_back)
    with pytest.raises(OSError, match="power loss after installation"):
        offline_restore.rollback(db, "wrong-restart", apply=True)
    monkeypatch.setattr(offline_restore, "_save_state", real_save)
    # Someone starts the service on the installed old state and it writes.
    _abrupt_wal_insert(db, "written-after-install")
    with pytest.raises(offline_restore.RestoreError, match="sidecar"):
        offline_restore.rollback(db, "wrong-restart", apply=True)


def test_retry_refuses_when_current_database_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    _activate(db, candidate, "db-changed", expected)
    real_replace = offline_restore.os.replace

    def fail_at_rollback_swap(source: str | Path, target: str | Path) -> None:
        if Path(source).name.startswith(".rollback-") and Path(target) == db:
            raise OSError("simulated interruption during rollback")
        real_replace(source, target)

    monkeypatch.setattr(offline_restore.os, "replace", fail_at_rollback_swap)
    with pytest.raises(OSError, match="simulated interruption"):
        offline_restore.rollback(db, "db-changed", apply=True)
    monkeypatch.setattr(offline_restore.os, "replace", real_replace)
    db.write_bytes(db.read_bytes() + b"\0" * 4096)
    with pytest.raises(offline_restore.RestoreError, match="Current database changed"):
        offline_restore.rollback(db, "db-changed", apply=True)


def test_fk_orphan_in_live_store_does_not_block_activation_or_rollback(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("INSERT INTO memory_items VALUES ('orphan', 'missing-project')")
        conn.commit()
    before = _family_digests(db)
    result = _activate(db, candidate, "fk-orphan", expected)
    state = result["state"]
    assert isinstance(state, dict)
    assert state["phase"] == "activated"
    old_state = state["old_state"]
    assert old_state["checks"]["foreign_keys"] == "violations"
    assert old_state["verified"] is False and old_state["rollback_available"] is True
    recovery = tmp_path / ".recovery" / "fk-orphan"
    assert {name: offline_restore._sha256(recovery / "raw-old" / name) for name in before} == before
    assert _ids(db) == ["before-snapshot"]
    offline_restore.rollback(db, "fk-orphan", apply=True)
    # The faithful damaged state returns, including WAL-committed rows.
    assert _ids(db) == ["after-snapshot", "before-snapshot", "orphan"]


def _corrupt_page(db: Path, table: str) -> None:
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
        root = int(conn.execute("SELECT rootpage FROM sqlite_master WHERE name = ?", (table,)).fetchone()[0])
    with db.open("r+b") as handle:
        handle.seek((root - 1) * page_size)
        handle.write(b"\xa5" * page_size)


def test_page_corruption_in_live_store_does_not_block_activation(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    _corrupt_page(db, "memory_items")
    result = _activate(db, candidate, "page-corrupt", expected)
    state = result["state"]
    assert isinstance(state, dict)
    assert state["phase"] == "activated"
    old_state = state["old_state"]
    assert old_state["verified"] is False
    assert (
        old_state.get("readable") is False or old_state["checks"]["integrity"] != "ok" or "identity_error" in old_state
    )
    assert _ids(db) == ["before-snapshot"]


@pytest.mark.parametrize("damage", ["garbage-header", "truncated-main"])
def test_unreadable_live_store_activates_and_refuses_rollback(tmp_path: Path, damage: str) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    for sidecar in (Path(f"{db}-wal"), Path(f"{db}-shm")):
        sidecar.unlink(missing_ok=True)
    if damage == "garbage-header":
        db.write_bytes(b"not a database, just damage " * 400)
    else:
        with db.open("r+b") as handle:
            handle.truncate(db.stat().st_size // 2 + 100)
    before = _family_digests(db)
    result = _activate(db, candidate, f"unreadable-{damage}", expected)
    state = result["state"]
    assert isinstance(state, dict)
    assert state["phase"] == "activated"
    assert state["old_state"]["readable"] is False
    recovery = tmp_path / ".recovery" / f"unreadable-{damage}"
    assert sorted(path.name for path in recovery.iterdir()) == ["raw-old", "state.json"]
    assert {name: offline_restore._sha256(recovery / "raw-old" / name) for name in before} == before
    with pytest.raises(offline_restore.RestoreError, match="no automated rollback target"):
        offline_restore.rollback(db, f"unreadable-{damage}")
    assert _ids(db) == ["before-snapshot"]
    # The documented way out: another activation under a new operation ID.
    expected_again = offline_restore._inspect(candidate)
    assert _activate(db, candidate, f"again-{damage}", expected_again)["applied"] is True


def test_environmental_consolidation_failure_stops_in_archiving_with_live_family_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    before = _family_digests(db)

    def locked(_source: Path, _target: Path) -> None:
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(offline_restore, "_consolidate", locked)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        _activate(db, candidate, "env-failure", expected)
    assert _family_digests(db) == before
    assert offline_restore._load_state(tmp_path / ".recovery" / "env-failure")["phase"] == "archiving"
    assert offline_restore.rollback(db, "env-failure")["note"].startswith("Activation stopped before")


def test_activation_never_opens_the_live_family_with_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean live DB gains no sidecars and loses no WAL before the swap."""
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    before = _family_digests(db)
    real_replace = offline_restore.os.replace
    seen: dict[str, str] = {}

    def observe_at_swap(source: str | Path, target: str | Path) -> None:
        if Path(source).name.startswith(".incoming-") and Path(target) == db:
            seen.update({"main": offline_restore._sha256(db)})
        real_replace(source, target)

    monkeypatch.setattr(offline_restore.os, "replace", observe_at_swap)
    _activate(db, candidate, "no-live-open", expected)
    displaced = tmp_path / ".recovery" / "no-live-open"
    assert seen["main"] == before["openchronicle.db"]
    for name, digest in before.items():
        if name != "openchronicle.db":
            assert offline_restore._sha256(displaced / f"displaced-{name}") == digest


def test_leftover_incoming_copy_is_removed_when_abandoning_archiving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    real_copy = offline_restore._copy_durable

    def fail_after_incoming(source: Path, target: Path) -> None:
        real_copy(source, target)
        if target.name.startswith(".incoming-"):
            raise OSError("simulated failure after the incoming copy")

    monkeypatch.setattr(offline_restore, "_copy_durable", fail_after_incoming)
    with pytest.raises(OSError, match="after the incoming copy"):
        _activate(db, candidate, "abandon", expected)
    monkeypatch.setattr(offline_restore, "_copy_durable", real_copy)
    incoming = tmp_path / ".incoming-abandon.db"
    assert incoming.exists()
    assert offline_restore.rollback(db, "abandon")["applied"] is False
    assert incoming.exists()
    result = offline_restore.rollback(db, "abandon", apply=True)
    assert result["phase"] == "abandoned"
    assert not incoming.exists()
    assert offline_restore.retire_stage(db, "abandon", apply=True)["stage_retired"] is True


def test_leftover_incoming_copy_is_removed_after_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    real_replace = offline_restore.os.replace

    def fail_at_swap(source: str | Path, target: str | Path) -> None:
        if Path(source).name.startswith(".incoming-") and Path(target) == db:
            raise OSError("simulated interruption before candidate installation")
        real_replace(source, target)

    monkeypatch.setattr(offline_restore.os, "replace", fail_at_swap)
    with pytest.raises(OSError, match="simulated interruption"):
        _activate(db, candidate, "incoming-left", expected)
    monkeypatch.setattr(offline_restore.os, "replace", real_replace)
    assert (tmp_path / ".incoming-incoming-left.db").exists()
    result = offline_restore.rollback(db, "incoming-left", apply=True)
    assert result["cleanup"] == "removed .incoming-incoming-left.db"
    assert not (tmp_path / ".incoming-incoming-left.db").exists()


def test_activation_refuses_reused_operation_id(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    _activate(db, candidate, "reused", expected)
    with pytest.raises(offline_restore.RestoreError, match="already has recovery state"):
        _activate(db, candidate, "reused", offline_restore._inspect(candidate))


def test_activation_refuses_wrong_project_identity(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    with pytest.raises(offline_restore.RestoreError, match="project identity"):
        offline_restore.activate(
            db, candidate, "foreign", expected["sha256"], expected["schema_version"], "f" * 64, apply=True
        )
    assert not (tmp_path / ".recovery").exists()


def test_activation_refuses_insufficient_space(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    usage = offline_restore.shutil.disk_usage(tmp_path)
    monkeypatch.setattr(
        offline_restore.shutil, "disk_usage", lambda _path: usage._replace(free=offline_restore._MARGIN)
    )
    with pytest.raises(offline_restore.RestoreError, match="Insufficient space"):
        _activate(db, candidate, "no-space", expected)
    assert not (tmp_path / ".recovery").exists()


def test_activation_stops_if_live_family_changes_while_archiving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    real_copy = offline_restore._copy_durable

    def writer_during_archive(source: Path, target: Path) -> None:
        real_copy(source, target)
        if target.parent.name == "raw-old" and source == db:
            with db.open("ab") as live:
                live.write(b"\0" * 16)

    monkeypatch.setattr(offline_restore, "_copy_durable", writer_during_archive)
    with pytest.raises(offline_restore.RestoreError, match="changed while archiving"):
        _activate(db, candidate, "moving", expected)


def test_rollback_refuses_modified_old_state_copy(tmp_path: Path) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    _activate(db, candidate, "old-modified", expected)
    old = tmp_path / ".recovery" / "old-modified" / "old-consistent.db"
    old.write_bytes(old.read_bytes() + b"\0")
    with pytest.raises(offline_restore.RestoreError, match="differs from its recorded identity"):
        offline_restore.rollback(db, "old-modified")


def test_retire_refuses_before_completion_and_on_changed_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    real_replace = offline_restore.os.replace

    def fail_at_swap(source: str | Path, target: str | Path) -> None:
        if Path(source).name.startswith(".incoming-") and Path(target) == db:
            raise OSError("simulated interruption before candidate installation")
        real_replace(source, target)

    monkeypatch.setattr(offline_restore.os, "replace", fail_at_swap)
    with pytest.raises(OSError):
        _activate(db, candidate, "retire-early", expected)
    monkeypatch.setattr(offline_restore.os, "replace", real_replace)
    with pytest.raises(offline_restore.RestoreError, match="before activation or rollback completes"):
        offline_restore.retire_stage(db, "retire-early", apply=True)
    offline_restore.rollback(db, "retire-early", apply=True)
    with closing(sqlite3.connect(candidate)) as conn:
        conn.execute("INSERT INTO memory_items VALUES ('tampered', 'project-1')")
        conn.commit()
    with pytest.raises(offline_restore.RestoreError, match="changed before retirement"):
        offline_restore.retire_stage(db, "retire-early", apply=True)
    assert candidate.exists()


def test_helper_guard_requires_marker_and_pid_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OC_OFFLINE_RESTORE", raising=False)
    with pytest.raises(offline_restore.RestoreError, match="OC_OFFLINE_RESTORE=1"):
        offline_restore._require_helper()
    monkeypatch.setenv("OC_OFFLINE_RESTORE", "1")
    if sys.platform == "linux":  # pytest is never PID 1 of a helper container
        with pytest.raises(offline_restore.RestoreError, match="PID 1"):
            offline_restore._require_helper()
    else:
        offline_restore._require_helper()


def test_main_refuses_without_helper_marker(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("OC_OFFLINE_RESTORE", raising=False)
    assert offline_restore.main(["status", "--db", "/data/openchronicle.db", "--operation-id", "abcd"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert '"service_must_remain_stopped": true' in captured.err
    assert "OC_OFFLINE_RESTORE" in captured.err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["status", "--db", "/tmp/openchronicle.db", "--operation-id", "abcd"], "require --db /data/openchronicle.db"),
        (["activate", "--db", "/data/openchronicle.db", "--operation-id", "abcd"], "Activation requires candidate"),
        (["status", "--db", "/data/openchronicle.db", "--operation-id", "abcd", "--apply"], "Status is read-only"),
    ],
)
def test_main_argument_guards(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], argv: list[str], message: str
) -> None:
    monkeypatch.setattr(offline_restore, "_require_helper", lambda: None)
    assert offline_restore.main(argv) == 1
    assert message in capsys.readouterr().err


def test_zero_length_main_with_wal_is_not_a_rollback_target(tmp_path: Path) -> None:
    """Consolidating a zero-length main yields an empty DB that passes both checks.

    Rollback must not install it: restarting the old image would migrate it
    into a fresh, empty store while the real rows sit only in raw-old's WAL.
    """
    db, candidate, expected = _stopped_wal_fixture(tmp_path)
    with db.open("r+b") as handle:
        handle.truncate(0)
    assert Path(f"{db}-wal").stat().st_size > 0
    before = _family_digests(db)
    state = _activate(db, candidate, "zero-main", expected)["state"]
    assert isinstance(state, dict)
    assert state["phase"] == "activated"
    assert state["old_state"]["rollback_available"] is False
    raw = tmp_path / ".recovery" / "zero-main" / "raw-old"
    assert {name: offline_restore._sha256(raw / name) for name in before} == before
    with pytest.raises(offline_restore.RestoreError, match="no automated rollback target"):
        offline_restore.rollback(db, "zero-main", apply=True)


# ── Helper staging: the production path while the MCP tools are parked ──


def _snapshot(tmp_path: Path, name: str = "snapshot.db") -> tuple[Path, Path, offline_restore.BackupInfo]:
    db, candidate, _ = _stopped_wal_fixture(tmp_path)
    exported = tmp_path / "exports" / name
    exported.parent.mkdir()
    exported.write_bytes(candidate.read_bytes())
    candidate.unlink()
    return db, exported, offline_restore._inspect(exported)


def test_stage_then_activate_from_an_exported_snapshot(tmp_path: Path) -> None:
    db, exported, info = _snapshot(tmp_path)
    dry = offline_restore.stage(db, exported, info["sha256"])
    assert dry["applied"] is False
    assert list((tmp_path / ".restore-stage").glob("*")) == []
    staged = offline_restore.stage(db, exported, info["sha256"], apply=True)
    stage_path = Path(str(staged["stage_path"]))
    assert staged["candidate"] == info
    assert [path.name for path in stage_path.parent.iterdir()] == [stage_path.name]
    # The printed values are exactly what activation checks.
    result = _activate(db, stage_path, "staged-by-helper", info)
    assert result["applied"] is True
    assert _ids(db) == ["before-snapshot"]
    with pytest.raises(offline_restore.RestoreError, match="already staged"):
        offline_restore.stage(db, exported, info["sha256"])


def test_stage_requires_the_independently_recorded_digest(tmp_path: Path) -> None:
    db, exported, info = _snapshot(tmp_path)
    with pytest.raises(offline_restore.RestoreError, match="differs from the independently recorded"):
        offline_restore.stage(db, exported, "0" * 64, apply=True)
    for malformed in (info["sha256"].upper(), "", "abc"):
        with pytest.raises(offline_restore.RestoreError, match="64 lowercase hex"):
            offline_restore.stage(db, exported, malformed, apply=True)
    assert list((tmp_path / ".restore-stage").glob("*")) == []


def test_stage_refuses_the_live_family_and_recovery_files(tmp_path: Path) -> None:
    db, exported, info = _snapshot(tmp_path)
    live_digest = offline_restore._sha256(db)
    for source in (db, Path(f"{db}-wal")):
        with pytest.raises(offline_restore.RestoreError, match="live database family"):
            offline_restore.stage(db, source, live_digest, apply=True)
    recovery_copy = tmp_path / ".recovery" / "op" / "old-consistent.db"
    recovery_copy.parent.mkdir(parents=True)
    recovery_copy.write_bytes(exported.read_bytes())
    with pytest.raises(offline_restore.RestoreError, match=r"\.recovery"):
        offline_restore.stage(db, recovery_copy, info["sha256"], apply=True)


def test_stage_refuses_unverifiable_snapshots(tmp_path: Path) -> None:
    db, exported, info = _snapshot(tmp_path)
    Path(f"{exported}-wal").write_bytes(b"sidecar")
    with pytest.raises(offline_restore.RestoreError, match="without sidecars"):
        offline_restore.stage(db, exported, info["sha256"], apply=True)
    Path(f"{exported}-wal").unlink()
    with closing(sqlite3.connect(exported)) as conn:
        conn.execute("INSERT INTO memory_items VALUES ('orphan', 'missing-project')")
        conn.commit()
    broken = offline_restore._sha256(exported)
    with pytest.raises(offline_restore.RestoreError, match="foreign_key_check"):
        offline_restore.stage(db, exported, broken, apply=True)
    assert list((tmp_path / ".restore-stage").glob("*")) == []


def test_main_stage_wiring(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    monkeypatch.setattr(offline_restore, "_require_helper", lambda: None)
    assert offline_restore.main(["stage", "--db", "/data/openchronicle.db"]) == 1
    stage_error = capsys.readouterr().err
    assert "requires --source and --expected-sha256" in stage_error
    assert "service_must_remain_stopped" not in stage_error
    assert offline_restore.main(["rollback", "--db", "/data/openchronicle.db"]) == 1
    assert "requires --operation-id" in capsys.readouterr().err
    calls: list[tuple[Path, Path, str, bool]] = []

    def fake_stage(db: Path, source: Path, digest: str, *, apply: bool = False) -> dict[str, object]:
        calls.append((db, source, digest, apply))
        return {"action": "stage", "applied": apply}

    monkeypatch.setattr(offline_restore, "stage", fake_stage)
    source = tmp_path / "snap.db"
    argv = ["stage", "--db", "/data/openchronicle.db", "--source", str(source), "--expected-sha256", "a" * 64]
    assert offline_restore.main([*argv, "--apply"]) == 0
    assert calls == [(Path("/data/openchronicle.db"), source, "a" * 64, True)]
    assert '"applied": true' in capsys.readouterr().out
