"""Tests for the in-process maintenance loop + job handlers."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
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


def test_load_jobs_drops_unknown_names() -> None:
    """An unknown name is skipped; the known ones still merge onto the defaults."""
    config = {
        "maintenance": {
            "jobs": [
                {"name": "db_vacuum", "interval_seconds": 60, "enabled": True},
                {"name": "totally_made_up", "interval_seconds": 60, "enabled": True},
            ]
        }
    }
    jobs = maintenance_loop.load_jobs(file_config=config)
    names = [j.name for j in jobs]
    assert "totally_made_up" not in names
    assert names == [d["name"] for d in maintenance_loop._DEFAULT_JOBS]
    assert {j.name: j.interval_seconds for j in jobs}["db_vacuum"] == 60


def test_load_jobs_merges_onto_defaults_instead_of_replacing() -> None:
    """The whole point: tuning one job must not silently delete the others.

    Before this merged, a config naming only db_backup left the store with
    no vacuum, no integrity check and no embedding backfill — no warning,
    because the loop only ever warned about *unknown* names.
    """
    config = {"maintenance": {"jobs": [{"name": "db_backup", "interval_seconds": 43200}]}}
    jobs = {j.name: j for j in maintenance_loop.load_jobs(file_config=config)}

    assert jobs["db_backup"].interval_seconds == 43200, "the override must apply"
    # Every unmentioned job survives, at its default interval.
    for default in maintenance_loop._DEFAULT_JOBS:
        name = default["name"]
        assert name in jobs, f"{name} was dropped by a config that never mentioned it"
        if name != "db_backup":
            assert jobs[name].interval_seconds == default["interval_seconds"]
            assert jobs[name].enabled == default["enabled"]


def test_load_jobs_omission_does_not_disable() -> None:
    """Omitting a job inherits its default; only `enabled: false` turns one off."""
    config = {"maintenance": {"jobs": [{"name": "db_vacuum", "enabled": False}]}}
    jobs = {j.name: j for j in maintenance_loop.load_jobs(file_config=config)}

    assert jobs["db_vacuum"].enabled is False, "explicit false must disable"
    assert jobs["db_backup"].enabled is True, "omission must NOT disable"
    # An omitted job with a non-default `enabled` keeps its own default,
    # not a blanket True — git_onboard_resync ships off.
    assert jobs["git_onboard_resync"].enabled is False


def test_load_jobs_partial_entry_inherits_unspecified_fields() -> None:
    """A config entry may override one field without restating the rest."""
    config = {"maintenance": {"jobs": [{"name": "git_onboard_resync", "enabled": True}]}}
    jobs = {j.name: j for j in maintenance_loop.load_jobs(file_config=config)}

    default = next(d for d in maintenance_loop._DEFAULT_JOBS if d["name"] == "git_onboard_resync")
    assert jobs["git_onboard_resync"].enabled is True
    assert jobs["git_onboard_resync"].interval_seconds == default["interval_seconds"]


@pytest.mark.parametrize(
    "named",
    [
        pytest.param("all-reversed", id="all-reversed"),
        pytest.param("one-late-job", id="partial-override"),
    ],
)
def test_load_jobs_ordering_follows_defaults_not_the_file(named: str) -> None:
    """Status output must be stable however the operator arranged their JSON.

    The partial case is the one that matters: overriding a single job that
    sits late in the defaults must not float it to the front. An
    all-overridden config cannot catch that — every entry is present, so a
    reordering bug is invisible under a stable sort.
    """
    defaults = maintenance_loop._DEFAULT_JOBS
    if named == "all-reversed":
        entries = [{"name": d["name"]} for d in reversed(defaults)]
    else:
        # db_backup is 4th of 5 — a mutation that groups configured jobs
        # first would move it, and nothing else would.
        entries = [{"name": "db_backup", "interval_seconds": 43200}]

    jobs = maintenance_loop.load_jobs(file_config={"maintenance": {"jobs": entries}})
    assert [j.name for j in jobs] == [d["name"] for d in defaults]


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


# ─── last_success_at (V3_PLAN Q16; prerequisite for cloud backup §6.1) ───


def test_last_success_at_advances_only_on_success() -> None:
    """`last_run_at` answers "did the loop tick", which a permanently
    broken job keeps answering forever. `last_success_at` answers "did it
    last WORK" — the question a silent failure cannot fake.
    """
    outcome: list[bool] = [True]

    async def _flaky(c: object) -> None:  # noqa: ARG001
        if not outcome[0]:
            raise RuntimeError("boom")

    job = maintenance_loop.JobState(name="probe", interval_seconds=1, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(container=MagicMock(), jobs=[job], handlers={"probe": _flaky})

    asyncio.run(loop.run_once("probe"))
    first_success = job.last_success_at
    assert first_success is not None
    assert job.last_run_at == first_success, "a successful run stamps both from one clock read"

    outcome[0] = False
    asyncio.run(loop.run_once("probe"))

    assert job.last_outcome == "failed"
    assert job.last_success_at == first_success, "a failure must not advance it"
    assert job.last_run_at is not None and job.last_run_at > first_success, "but the run did happen"


def test_last_success_at_is_not_cleared_by_a_later_failure() -> None:
    """The whole point is surviving a failing streak: if a failure reset
    it to None, "how long since this last worked" would be unanswerable
    exactly when it is being asked.
    """

    async def _bad(c: object) -> None:  # noqa: ARG001
        raise RuntimeError("boom")

    job = maintenance_loop.JobState(name="bad", interval_seconds=1, enabled=True)
    job.last_success_at = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    loop = maintenance_loop.MaintenanceLoop(container=MagicMock(), jobs=[job], handlers={"bad": _bad})

    asyncio.run(loop.run_once("bad"))

    assert job.last_success_at == datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


def test_last_success_at_survives_a_restart(tmp_path: Path) -> None:
    """Persisted, not per-process. Every push to main bounces this
    container, so an in-memory-only marker would let a job that has been
    failing for weeks present a clean surface after each redeploy.
    """
    state_path = tmp_path / "maintenance_state.json"

    async def _noop(c: object) -> None:  # noqa: ARG001
        return None

    job1 = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop1 = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job1], handlers={"probe": _noop}, state_path=state_path
    )
    asyncio.run(loop1.run_once("probe"))
    assert job1.last_success_at is not None

    job2 = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop2 = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job2], handlers={"probe": _noop}, state_path=state_path
    )
    loop2._load_state()  # start() does this; called directly per the sibling test

    assert job2.last_success_at == job1.last_success_at


def test_state_file_written_before_last_success_at_loads_without_raising(tmp_path: Path) -> None:
    """Verify, don't assume: this parses a REAL pre-change state file.

    A state-file exception happens at boot under `restart:
    unless-stopped` — the exact crash-loop this file exists to prevent.
    The old shape simply has no `last_success_at` block.
    """
    state_path = tmp_path / "maintenance_state.json"
    state_path.write_text(
        json.dumps({"last_run_at": {"probe": "2026-08-01T12:00:00+00:00"}}),
        encoding="utf-8",
    )

    job = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(container=MagicMock(), jobs=[job], handlers={}, state_path=state_path)
    loop._load_state()

    assert job.last_run_at == datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC), "the old block still loads"
    assert job.last_success_at is None, "and the absent one is simply unknown, not an error"


def test_malformed_last_success_at_block_degrades_per_entry(tmp_path: Path) -> None:
    """Each tolerance rule is per-entry: a bad value loses that job's
    timestamp, never the whole file and never the other block.
    """
    state_path = tmp_path / "maintenance_state.json"
    state_path.write_text(
        json.dumps(
            {
                "last_run_at": {"a": "2026-08-01T12:00:00+00:00", "b": "2026-08-01T12:00:00+00:00"},
                "last_success_at": {"a": "not-a-timestamp", "b": "2026-08-02T12:00:00+00:00"},
            }
        ),
        encoding="utf-8",
    )
    job_a = maintenance_loop.JobState(name="a", interval_seconds=3600, enabled=True)
    job_b = maintenance_loop.JobState(name="b", interval_seconds=3600, enabled=True)

    loop = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job_a, job_b], handlers={}, state_path=state_path
    )
    loop._load_state()

    assert job_a.last_success_at is None, "the unparseable entry is dropped"
    assert job_a.last_run_at is not None, "without taking its own last_run_at with it"
    assert job_b.last_success_at == datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC), "or its neighbour"


def test_status_payload_exposes_last_success_at() -> None:
    job = maintenance_loop.JobState(name="probe", interval_seconds=60, enabled=True)
    job.last_success_at = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)
    loop = maintenance_loop.MaintenanceLoop(container=MagicMock(), jobs=[job], handlers={})

    entry = loop.status()[0]

    assert entry["last_success_at"] == "2026-08-01T12:00:00+00:00"
    assert entry["last_run_at"] is None, "never run, but a prior success is still reported"


def test_a_failing_streak_keeps_the_older_success_across_a_restart(tmp_path: Path) -> None:
    """The round-trip that actually distinguishes the two fields.

    Every other persistence test drives a handler that only succeeds, so
    last_run_at == last_success_at by construction and the file cannot
    show which value landed under which key. Persisting last_run_at
    under "last_success_at" survives those tests — and silently inverts
    the feature, since a job failing for weeks would reload a
    fresh-looking success after every redeploy.
    """
    state_path = tmp_path / "maintenance_state.json"
    ok = [True]

    async def _flaky(c: object) -> None:  # noqa: ARG001
        if not ok[0]:
            raise RuntimeError("boom")

    job1 = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop1 = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job1], handlers={"probe": _flaky}, state_path=state_path
    )
    asyncio.run(loop1.run_once("probe"))
    success = job1.last_success_at
    assert success is not None

    ok[0] = False
    asyncio.run(loop1.run_once("probe"))
    assert job1.last_run_at is not None and job1.last_run_at > success

    job2 = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop2 = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job2], handlers={"probe": _flaky}, state_path=state_path
    )
    loop2._load_state()

    assert job2.last_success_at == success, "the reloaded success is the success, not the failed run"
    assert job2.last_run_at == job1.last_run_at


def test_is_due_reads_last_run_at_not_last_success_at() -> None:
    """Pins the scheduler to the right field.

    This change put a lookalike attribute next to the one _is_due reads.
    Were _is_due to read last_success_at, a job that has never succeeded
    would be due on every tick and re-fire continuously — the exact
    runaway-backup regression the state file was added to fix, except
    permanent.
    """
    now = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)

    just_ran_never_succeeded = maintenance_loop.JobState(name="a", interval_seconds=3600, enabled=True)
    just_ran_never_succeeded.last_run_at = now
    just_ran_never_succeeded.last_success_at = None
    assert maintenance_loop._is_due(just_ran_never_succeeded, now) is False, "a failing job still waits its interval"

    stale_run_recent_success = maintenance_loop.JobState(name="b", interval_seconds=3600, enabled=True)
    stale_run_recent_success.last_run_at = now - timedelta(hours=2)
    stale_run_recent_success.last_success_at = now
    assert maintenance_loop._is_due(stale_run_recent_success, now) is True, (
        "and the schedule follows runs, not successes"
    )


def test_persist_survives_a_job_that_has_never_succeeded(tmp_path: Path) -> None:
    """The deployed shape on day one: a job that ran and failed.

    _persist_state is called from _invoke's `finally`, so a raise while
    assembling the payload — e.g. the success block filtering on the
    neighbouring attribute — escapes the job task rather than being
    logged. Nothing else in the suite persists state for a job whose
    last_success_at is still None.
    """
    state_path = tmp_path / "maintenance_state.json"

    async def _bad(c: object) -> None:  # noqa: ARG001
        raise RuntimeError("boom")

    job = maintenance_loop.JobState(name="probe", interval_seconds=3600, enabled=True)
    loop = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job], handlers={"probe": _bad}, state_path=state_path
    )

    asyncio.run(loop.run_once("probe"))  # must not raise

    assert job.last_outcome == "failed"
    assert job.last_success_at is None
    written = json.loads(state_path.read_text(encoding="utf-8"))
    assert written["last_run_at"]["probe"], "the run was recorded"
    assert written["last_success_at"] == {}, "and the success block is simply empty, not absent or wrong"


def test_non_string_timestamp_degrades_that_entry_only(tmp_path: Path) -> None:
    """The asymmetric tolerance rule.

    A non-string value raises TypeError, not ValueError, so it slips
    past the inner `except ValueError` and would be caught only by
    _load_state's whole-file handler — turning per-entry tolerance into
    lose-the-entire-file. The isinstance guard is what keeps a single
    bad value from costing every other job its schedule.
    """
    state_path = tmp_path / "maintenance_state.json"
    state_path.write_text(
        json.dumps({"last_run_at": {"a": 1754049600, "b": "2026-08-01T12:00:00+00:00"}}),
        encoding="utf-8",
    )
    job_a = maintenance_loop.JobState(name="a", interval_seconds=3600, enabled=True)
    job_b = maintenance_loop.JobState(name="b", interval_seconds=3600, enabled=True)

    loop = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job_a, job_b], handlers={}, state_path=state_path
    )
    loop._load_state()

    assert job_a.last_run_at is None, "the non-string entry is dropped"
    assert job_b.last_run_at == datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC), "without costing its neighbour"


# ── truthful backfill outcome + durable degraded (0003 F4 / 0004 F9) ──


def test_embedding_backfill_all_failed_raises(tmp_path: Path) -> None:
    """A totally failed backfill must FAIL the job. Returning normally
    let the loop record last_outcome="ok" and advance last_success_at
    while zero vectors were generated — a dead provider read as a
    healthy nightly success."""
    from openchronicle.core.application.services.embedding_service import BackfillResult

    container = MagicMock()
    container.embedding_service.generate_missing.return_value = BackfillResult(generated=0, failed=7, elapsed_ms=1)
    with pytest.raises(RuntimeError, match="all 7 candidate"):
        asyncio.run(maintenance_jobs.embedding_backfill(container))


def test_embedding_backfill_partial_failure_completes(tmp_path: Path) -> None:
    """Partial success stays a completed run — per-item resilience is the
    point of the backfill loop; only TOTAL failure raises."""
    from openchronicle.core.application.services.embedding_service import BackfillResult

    container = MagicMock()
    container.embedding_service.generate_missing.return_value = BackfillResult(generated=3, failed=2, elapsed_ms=1)
    asyncio.run(maintenance_jobs.embedding_backfill(container))  # must not raise


def test_degraded_survives_restart_via_persisted_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """maintenance_degraded is process-local and every push bounces the
    container — so a failed integrity check used to present a clean
    health surface after restart. The persisted run/success timestamps
    are the durable evidence, and health now consults them."""
    import json as _json

    from openchronicle.core.application.use_cases.diagnose_runtime import _integrity_failure_persisted

    db_path = tmp_path / "data" / "oc.db"
    db_path.parent.mkdir(parents=True)
    monkeypatch.setenv("OC_DB_PATH", str(db_path))
    state = db_path.parent / "maintenance_state.json"

    # Last run failed: run stamped, success older (or absent).
    state.write_text(
        _json.dumps(
            {
                "last_run_at": {"db_integrity_check": "2026-08-28T10:00:00+00:00"},
                "last_success_at": {"db_integrity_check": "2026-08-27T10:00:00+00:00"},
            }
        ),
        encoding="utf-8",
    )
    assert _integrity_failure_persisted() is True

    # Success stamps both from one clock read — equal means healthy.
    state.write_text(
        _json.dumps(
            {
                "last_run_at": {"db_integrity_check": "2026-08-28T10:00:00+00:00"},
                "last_success_at": {"db_integrity_check": "2026-08-28T10:00:00+00:00"},
            }
        ),
        encoding="utf-8",
    )
    assert _integrity_failure_persisted() is False

    # Ran once, never succeeded.
    state.write_text(
        _json.dumps({"last_run_at": {"db_integrity_check": "2026-08-28T10:00:00+00:00"}}), encoding="utf-8"
    )
    assert _integrity_failure_persisted() is True

    # Never ran / no state file: fail-soft to False.
    state.unlink()
    assert _integrity_failure_persisted() is False
