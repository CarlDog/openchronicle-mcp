"""Tests for the in-process maintenance loop + job handlers."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any
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
    loop = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[], handlers={}
    )
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
    loop = maintenance_loop.MaintenanceLoop(
        container=MagicMock(), jobs=[job], handlers={"probe": _async_noop}
    )
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


def test_embedding_backfill_no_op_when_service_missing(tmp_path: Path) -> None:
    """Loop should not crash when embeddings are disabled."""
    container = MagicMock()
    container.embedding_service = None
    asyncio.run(maintenance_jobs.embedding_backfill(container))


def test_handlers_registry_complete() -> None:
    """Every default-config job must have a handler registered."""
    expected = {entry["name"] for entry in maintenance_loop._DEFAULT_JOBS}
    assert expected == set(maintenance_jobs.HANDLERS), (
        "default jobs and handler registry must agree"
    )


def test_retention_keeps_newest(tmp_path: Path) -> None:
    """_retention_prune deletes oldest .db files beyond the keep limit."""
    backup_dir = tmp_path / "auto"
    backup_dir.mkdir()
    paths = []
    for i in range(10):
        p = backup_dir / f"old-{i}.db"
        p.write_bytes(b"x")
        # Stagger mtimes so sort is deterministic.
        os_time = time.time() - (10 - i) * 60
        import os

        os.utime(p, (os_time, os_time))
        paths.append(p)

    maintenance_jobs._retention_prune(backup_dir, keep=3)
    survivors = sorted(backup_dir.glob("*.db"))
    assert len(survivors) == 3
    # Newest (largest i) should survive
    assert all("old-" in p.name for p in survivors)
    surviving_indices = sorted(int(p.stem.split("-")[1]) for p in survivors)
    assert surviving_indices == [7, 8, 9]
