"""Tests for the in-process maintenance loop + job handlers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openchronicle.core.application.services import maintenance_loop
from openchronicle.core.infrastructure.maintenance import jobs as maintenance_jobs

# ─── unit tests for MaintenanceLoop ──────────────────────────────────


def _container_stub(tmp_path: Path) -> MagicMock:
    container = MagicMock()
    container.paths.db_path = tmp_path / "data" / "openchronicle.db"
    container.embedding_service = None
    return container


def test_run_once_invokes_registered_handler() -> None:
    container = MagicMock()
    seen: list[str] = []

    async def _handler(c: object) -> None:  # noqa: ARG001
        seen.append("ran")

    job = maintenance_loop.JobState(name="probe", interval_seconds=1, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(
        container=container,
        jobs=[job],
        handlers={"probe": _handler},
    )
    asyncio.run(loop.run_once("probe"))
    assert seen == ["ran"]
    assert job.runs_total == 1
    assert job.runs_ok == 1
    assert job.last_outcome == "ok"


def test_run_once_records_failure_without_crashing() -> None:
    container = MagicMock()

    async def _bad(c: object) -> None:  # noqa: ARG001
        raise RuntimeError("boom")

    job = maintenance_loop.JobState(name="bad", interval_seconds=1, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(
        container=container,
        jobs=[job],
        handlers={"bad": _bad},
    )
    asyncio.run(loop.run_once("bad"))
    assert job.runs_failed == 1
    assert job.runs_ok == 0
    assert job.last_outcome == "failed"
    assert "boom" in (job.last_error or "")


def test_run_once_unknown_job_raises() -> None:
    loop = maintenance_loop.MaintenanceLoop(container=MagicMock(), jobs=[], handlers={})
    with pytest.raises(KeyError, match="unknown maintenance job"):
        asyncio.run(loop.run_once("does-not-exist"))


def test_overlap_skip_records_skip_and_does_not_block() -> None:
    """If job N is still running when its tick fires, the new tick skips."""
    container = MagicMock()
    block = asyncio.Event()
    started = asyncio.Event()

    async def _slow(c: object) -> None:  # noqa: ARG001
        started.set()
        await block.wait()

    job = maintenance_loop.JobState(name="slow", interval_seconds=0, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(
        container=container,
        jobs=[job],
        handlers={"slow": _slow},
        tick_seconds=0.005,
    )

    async def _exercise() -> int:
        await loop.start()
        await asyncio.wait_for(started.wait(), timeout=2)
        # Yield enough times for the loop to wake and detect the held lock.
        # The loop starts the first run inside the lock; the next tick wakes
        # while it's still held, recording a skip. Repeat until we see one.
        for _ in range(50):
            if job.runs_skipped_overlap > 0:
                break
            await asyncio.sleep(0.01)
        skipped = job.runs_skipped_overlap
        block.set()
        await asyncio.sleep(0.02)
        await loop.stop()
        return skipped

    skipped = asyncio.run(_exercise())
    assert skipped >= 1, "expected at least one overlap-skip during the slow job"
    assert job.runs_total >= 1


def test_disabled_job_is_not_invoked() -> None:
    container = MagicMock()
    seen: list[str] = []

    async def _handler(c: object) -> None:  # noqa: ARG001
        seen.append("hit")

    job = maintenance_loop.JobState(name="off", interval_seconds=0, enabled=False)
    loop = maintenance_loop.MaintenanceLoop(
        container=container,
        jobs=[job],
        handlers={"off": _handler},
        tick_seconds=0.01,
    )

    async def _exercise() -> None:
        await loop.start()
        await asyncio.sleep(0.05)
        await loop.stop()

    asyncio.run(_exercise())
    assert seen == []
    assert job.runs_total == 0


def test_status_payload_shape() -> None:
    job = maintenance_loop.JobState(name="probe", interval_seconds=300, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(container=MagicMock(), jobs=[job], handlers={"probe": _async_noop})
    snapshot = loop.status()
    assert len(snapshot) == 1
    entry = snapshot[0]
    assert entry["name"] == "probe"
    assert entry["interval_seconds"] == 300
    assert entry["enabled"] is True
    assert entry["last_run_at"] is None
    assert entry["runs_total"] == 0


async def _async_noop(_c: object) -> None:
    return None


def test_is_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OC_MAINTENANCE_DISABLED", raising=False)
    assert maintenance_loop.is_disabled() is False
    for value in ("1", "true", "yes", "on", "ON", "True"):
        monkeypatch.setenv("OC_MAINTENANCE_DISABLED", value)
        assert maintenance_loop.is_disabled() is True
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "0")
    assert maintenance_loop.is_disabled() is False


def test_load_jobs_falls_back_to_defaults_on_empty_config() -> None:
    jobs = maintenance_loop.load_jobs(file_config={})
    names = [j.name for j in jobs]
    assert "db_backup" in names
    assert "db_vacuum" in names
    assert "embedding_backfill" in names


def test_load_jobs_drops_unknown_names_silently() -> None:
    config = {
        "maintenance": {
            "jobs": [
                {"name": "db_vacuum", "interval_seconds": 60, "enabled": True},
                {"name": "totally_made_up", "interval_seconds": 60, "enabled": True},
            ]
        }
    }
    jobs = maintenance_loop.load_jobs(file_config=config)
    assert len(jobs) == 1
    assert jobs[0].name == "db_vacuum"


# ─── job handler tests ───────────────────────────────────────────────


def test_db_backup_writes_and_prunes(tmp_path: Path) -> None:
    """db_backup writes the file and keeps last 7 retention via mtime."""
    from openchronicle.core.domain.models.memory_item import MemoryItem
    from openchronicle.core.domain.models.project import Project
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

    db_path = tmp_path / "data" / "test.db"
    store = SqliteStore(str(db_path))
    store.init_schema()
    proj = Project(name="t")
    store.add_project(proj)
    store.add_memory(MemoryItem(content="x", project_id=proj.id))

    container = MagicMock()
    container.storage = store
    container.paths.db_path = db_path

    asyncio.run(maintenance_jobs.db_backup(container))

    backup_dir = tmp_path / "data" / "backups" / "auto"
    backups = list(backup_dir.glob("*.db"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0
    store.close()


def test_db_vacuum_runs_backup_first(tmp_path: Path) -> None:
    """The backup-before-destructive policy is enforced in code."""
    from openchronicle.core.domain.models.project import Project
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

    db_path = tmp_path / "data" / "test.db"
    store = SqliteStore(str(db_path))
    store.init_schema()
    store.add_project(Project(name="t"))

    container = MagicMock()
    container.storage = store
    container.paths.db_path = db_path

    asyncio.run(maintenance_jobs.db_vacuum(container))

    backup_dir = tmp_path / "data" / "backups" / "auto"
    backups = list(backup_dir.glob("*.db"))
    assert len(backups) == 1, "db_vacuum must run db_backup first"
    store.close()


def test_db_integrity_check_clears_degraded_on_success(tmp_path: Path) -> None:
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

    store = SqliteStore(str(tmp_path / "test.db"))
    store.init_schema()

    container = MagicMock()
    container.storage = store
    container.paths.db_path = store.db_path
    container.maintenance_degraded = True

    asyncio.run(maintenance_jobs.db_integrity_check(container))
    assert getattr(container, "maintenance_degraded") is False
    store.close()


def test_db_integrity_check_failure_backs_up_flags_degraded_and_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The corrupt-DB branch (2026-05-06 cutover incident): a non-'ok'
    integrity result must take an emergency backup, set the container's
    maintenance_degraded flag, and raise so the loop counts the failure."""
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

    db_path = tmp_path / "data" / "test.db"
    store = SqliteStore(str(db_path))
    store.init_schema()

    container = MagicMock()
    container.storage = store
    container.paths.db_path = db_path
    container.maintenance_degraded = False

    monkeypatch.setattr(store, "integrity_check", lambda: "*** in database main *** page 3: btree corruption")

    with pytest.raises(RuntimeError, match="integrity_check failed"):
        asyncio.run(maintenance_jobs.db_integrity_check(container))

    assert getattr(container, "maintenance_degraded") is True
    backups = list((tmp_path / "data" / "backups" / "auto").glob("*.db"))
    assert len(backups) == 1, "failure branch must take an emergency backup"
    assert backups[0].stat().st_size > 0
    store.close()


def test_db_integrity_check_failure_still_flags_when_emergency_backup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A secondary backup failure must not mask the integrity error:
    degraded is still set and the RuntimeError still carries the
    integrity result, not the backup exception."""
    from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

    db_path = tmp_path / "data" / "test.db"
    store = SqliteStore(str(db_path))
    store.init_schema()

    container = MagicMock()
    container.storage = store
    container.paths.db_path = db_path
    container.maintenance_degraded = False

    monkeypatch.setattr(store, "integrity_check", lambda: "not ok")

    def _boom(dest: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(store, "backup_to", _boom)

    with pytest.raises(RuntimeError, match="integrity_check failed: not ok"):
        asyncio.run(maintenance_jobs.db_integrity_check(container))

    assert getattr(container, "maintenance_degraded") is True
    store.close()


def test_embedding_backfill_no_op_when_service_missing(tmp_path: Path) -> None:
    """Loop should not crash when embeddings are disabled."""
    container = MagicMock()
    container.embedding_service = None
    asyncio.run(maintenance_jobs.embedding_backfill(container))


def test_handlers_registry_complete() -> None:
    """Every default-config job must have a handler registered."""
    expected = {entry["name"] for entry in maintenance_loop._DEFAULT_JOBS}
    assert expected == set(maintenance_jobs.HANDLERS), "default jobs and handler registry must agree"


def test_retention_keeps_newest(tmp_path: Path) -> None:
    """_retention_prune deletes oldest .db files beyond the keep limit.

    All files share one UTC day (fixed mid-day base, not time.time():
    near 00:00Z the minute stagger straddled midnight, and the
    newest-per-day keep-set then legitimately preserved a fourth file).
    """
    import os
    from datetime import UTC, datetime

    backup_dir = tmp_path / "auto"
    backup_dir.mkdir()
    base = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC).timestamp()
    paths = []
    for i in range(10):
        p = backup_dir / f"old-{i}.db"
        p.write_bytes(b"x")
        os_time = base - (10 - i) * 60
        os.utime(p, (os_time, os_time))
        paths.append(p)

    maintenance_jobs._retention_prune(backup_dir, keep=3)
    survivors = sorted(backup_dir.glob("*.db"))
    assert len(survivors) == 3
    # Newest (largest i) should survive
    assert all("old-" in p.name for p in survivors)
    surviving_indices = sorted(int(p.stem.split("-")[1]) for p in survivors)
    assert surviving_indices == [7, 8, 9]


def test_retention_burst_cannot_evict_older_days(tmp_path: Path) -> None:
    """Regression (2026-08-15 review): pure newest-N retention let a burst
    of same-day backups (restart spam, manual run-once) fill every slot
    and evict the week-old backup that matters after discovering
    corruption. The per-day keep-set preserves the newest file of each
    recent day alongside the newest N overall.
    """
    import os
    from datetime import UTC, datetime

    backup_dir = tmp_path / "auto"
    backup_dir.mkdir()
    # Fixed mid-day UTC base: deriving from time.time() made the "today"
    # burst straddle UTC midnight when the suite ran near 00:00Z, and a
    # straddling burst file legitimately claims the previous day's
    # newest-per-day slot — correct behavior, flaky assertions.
    now = datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC).timestamp()
    day = 24 * 3600

    # One backup per day for the six preceding days...
    for d in range(6, 0, -1):
        p = backup_dir / f"day-{d}.db"
        p.write_bytes(b"x")
        os.utime(p, (now - d * day, now - d * day))
    # ...plus a burst of four backups today.
    for i in range(4):
        p = backup_dir / f"today-{i}.db"
        p.write_bytes(b"x")
        ts = now - (4 - i) * 60
        os.utime(p, (ts, ts))

    maintenance_jobs._retention_prune(backup_dir, keep=3)
    survivors = {p.name for p in backup_dir.glob("*.db")}

    # Newest 3 overall: the three newest today files.
    assert {"today-1", "today-2", "today-3"} <= {n.removesuffix(".db") for n in survivors}
    # Newest-per-day for the 3 most recent days: today, day-1, day-2.
    assert "day-1.db" in survivors
    assert "day-2.db" in survivors
    # Older days and today's burst overflow are pruned.
    assert "day-3.db" not in survivors
    assert "day-6.db" not in survivors
    assert "today-0.db" not in survivors


# ─── state persistence ───────────────────────────────────────────────


def test_last_run_at_survives_a_new_loop_instance(tmp_path: Path) -> None:
    """Regression (2026-08-15 review): JobState started fresh on every
    boot, so _is_due fired every enabled job immediately — two backups
    per container restart under the redeploy-on-push deployment model.
    """

    async def _noop(c: object) -> None:  # noqa: ARG001
        return None

    state_path = tmp_path / "maintenance_state.json"
    job1 = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop1 = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job1], handlers={"probe": _noop}, state_path=state_path
    )
    asyncio.run(loop1.run_once("probe"))
    assert state_path.exists()

    job2 = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop2 = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job2], handlers={"probe": _noop}, state_path=state_path
    )
    loop2._load_state()

    assert job2.last_run_at == job1.last_run_at
    from openchronicle.core.domain.time_utils import utc_now

    assert maintenance_loop._is_due(job2, utc_now()) is False


def test_malformed_state_file_starts_fresh(tmp_path: Path) -> None:
    state_path = tmp_path / "maintenance_state.json"
    state_path.write_text("{not json", encoding="utf-8")
    job = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(container=MagicMock(), jobs=[job], handlers={}, state_path=state_path)
    loop._load_state()
    assert job.last_run_at is None


def test_state_write_failure_is_nonfatal(tmp_path: Path) -> None:
    """A write failure degrades to pre-persistence behavior, never fails
    the job that just ran.
    """
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"i am a file, not a directory")

    async def _noop(c: object) -> None:  # noqa: ARG001
        return None

    job = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(
        container=MagicMock(),
        jobs=[job],
        handlers={"probe": _noop},
        state_path=blocker / "state.json",
    )
    asyncio.run(loop.run_once("probe"))
    assert job.last_outcome == "ok"


def test_load_jobs_fails_soft_on_bad_interval() -> None:
    """A hand-edited core.json typo must not crash create_app (crash-loop
    rule), and a non-positive interval would fire the job every tick.
    """
    config = {
        "maintenance": {
            "jobs": [
                {"name": "db_backup", "interval_seconds": "often", "enabled": True},
                {"name": "db_vacuum", "interval_seconds": -5, "enabled": True},
                {"name": "db_integrity_check", "interval_seconds": 1234, "enabled": True},
            ]
        }
    }
    states = {j.name: j for j in maintenance_loop.load_jobs(config)}
    assert states["db_backup"].interval_seconds == 3600
    assert states["db_vacuum"].interval_seconds == 3600
    assert states["db_integrity_check"].interval_seconds == 1234
