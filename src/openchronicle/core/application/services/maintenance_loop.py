"""In-process maintenance loop for v3.

The v2 scheduler is gone (orchestrator-coupled, multi-worker, DB-backed
queue — overkill for a single-user memory store). This is the slim
replacement: an asyncio task that wakes every tick, walks a list of
configured jobs, and runs the ones whose interval has elapsed.

Design constraints (locked in V3_PLAN.md):
- Pure asyncio. No DB-backed queue, no manager/worker, no atomic claim.
- One process. One loop. Jobs run sequentially within a tick.
- Overlap protection: each job has its own asyncio.Lock; if a job is
  still running when its next tick fires, the new tick skips (does NOT
  queue).
- Failure isolation: exceptions are logged + counted, never crash the
  loop. Bad jobs degrade the system; they don't stop it.
- Backup-before-destructive: jobs that touch the whole file
  (`db_vacuum`, future schema migrations) MUST run a backup first as
  part of the same job, in code (not just by config).
- Opt-out: `OC_MAINTENANCE_DISABLED=1` short-circuits the loop. Useful
  for tests, one-shot CLI invocations, and migration windows.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from openchronicle.core.domain.time_utils import utc_now

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

_logger = logging.getLogger(__name__)

# Handler signature: async function that takes the container and returns
# nothing. Failures must raise; the loop catches and counts.
JobHandler = Callable[["CoreContainer"], Awaitable[None]]


@dataclass
class JobState:
    """Per-job runtime state surfaced via /api/v1/maintenance/status."""

    name: str
    interval_seconds: int
    enabled: bool
    last_run_at: datetime | None = None
    last_outcome: str | None = None  # "ok" | "failed" | "skipped_overlap"
    last_error: str | None = None
    runs_total: int = 0
    runs_ok: int = 0
    runs_failed: int = 0
    runs_skipped_overlap: int = 0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class MaintenanceLoop:
    """Single-process asyncio loop that runs configured jobs on schedule."""

    def __init__(
        self,
        container: CoreContainer,
        jobs: list[JobState],
        handlers: dict[str, JobHandler],
        *,
        tick_seconds: float = 1.0,
    ) -> None:
        self._container = container
        self._jobs = {j.name: j for j in jobs}
        self._handlers = handlers
        self._tick_seconds = tick_seconds
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()
        # Global mutex so background-spawned jobs still execute one-at-
        # a-time (no two jobs ever run concurrently in this process; a
        # vacuum + backfill would otherwise race the same DB).
        self._global_lock: asyncio.Lock = asyncio.Lock()
        self._inflight: set[asyncio.Task[None]] = set()

    def status(self) -> list[dict[str, Any]]:
        """Snapshot of every job's runtime state, JSON-safe."""
        out: list[dict[str, Any]] = []
        for job in self._jobs.values():
            out.append(
                {
                    "name": job.name,
                    "interval_seconds": job.interval_seconds,
                    "enabled": job.enabled,
                    "last_run_at": job.last_run_at.isoformat() if job.last_run_at else None,
                    "last_outcome": job.last_outcome,
                    "last_error": job.last_error,
                    "runs_total": job.runs_total,
                    "runs_ok": job.runs_ok,
                    "runs_failed": job.runs_failed,
                    "runs_skipped_overlap": job.runs_skipped_overlap,
                }
            )
        return out

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="oc-maintenance")
        _logger.info(
            "Maintenance loop started (%d jobs, %d enabled)",
            len(self._jobs),
            sum(1 for j in self._jobs.values() if j.enabled),
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self._task.cancel()
        # Drain any in-flight job tasks (cancel rather than wait for
        # potentially long-running jobs).
        for task in list(self._inflight):
            task.cancel()
        if self._inflight:
            await asyncio.gather(*self._inflight, return_exceptions=True)
        self._inflight.clear()
        self._task = None
        _logger.info("Maintenance loop stopped")

    async def run_once(self, name: str) -> None:
        """Manually trigger a single job (used by `oc maintenance run-once`)."""
        job = self._jobs.get(name)
        if job is None:
            raise KeyError(f"unknown maintenance job: {name}")
        await self._invoke(job)

    async def _run(self) -> None:
        """Main loop. Wakes every tick; dispatches due jobs as tasks.

        Jobs run as background tasks (so the loop can keep ticking while
        a long-running job is in flight), but each job acquires the
        global lock before running its handler — so two jobs never run
        at the same time. The per-job lock is what the next tick checks
        to detect overlap.
        """
        while not self._stop_event.is_set():
            try:
                now = utc_now()
                for job in self._jobs.values():
                    if not job.enabled:
                        continue
                    if not _is_due(job, now):
                        continue
                    if job._lock.locked():
                        job.runs_skipped_overlap += 1
                        job.last_outcome = "skipped_overlap"
                        _logger.warning(
                            "maintenance job %s skipped: previous run still in progress",
                            job.name,
                        )
                        continue
                    self._spawn(job)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover — defensive
                _logger.exception("Maintenance loop iteration failed; continuing")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._tick_seconds
                )
            except asyncio.TimeoutError:
                continue

    def _spawn(self, job: JobState) -> None:
        task = asyncio.create_task(self._invoke(job), name=f"oc-maint-{job.name}")
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)

    async def _invoke(self, job: JobState) -> None:
        async with job._lock:
            # Global mutex serializes all jobs across the process —
            # never two at once. Per-job lock (above) is for next-tick
            # overlap detection.
            async with self._global_lock:
                handler = self._handlers.get(job.name)
                if handler is None:
                    _logger.error("maintenance job %s has no handler registered", job.name)
                    job.last_outcome = "failed"
                    job.last_error = "no handler registered"
                    job.runs_failed += 1
                    job.runs_total += 1
                    job.last_run_at = utc_now()
                    return

                _logger.info("maintenance job %s: running", job.name)
                try:
                    await handler(self._container)
                    job.last_outcome = "ok"
                    job.last_error = None
                    job.runs_ok += 1
                except Exception as exc:
                    _logger.exception("maintenance job %s failed", job.name)
                    job.last_outcome = "failed"
                    job.last_error = str(exc)
                    job.runs_failed += 1
                finally:
                    job.runs_total += 1
                    job.last_run_at = utc_now()


def _is_due(job: JobState, now: datetime) -> bool:
    if job.last_run_at is None:
        return True
    return now - job.last_run_at >= timedelta(seconds=job.interval_seconds)


# ─────────────────────────────────────────────────────────────────────
# Default jobs + config loading
# ─────────────────────────────────────────────────────────────────────


_DEFAULT_JOBS: list[dict[str, Any]] = [
    {"name": "db_vacuum", "interval_seconds": 7 * 24 * 3600, "enabled": True},
    {"name": "db_integrity_check", "interval_seconds": 7 * 24 * 3600, "enabled": True},
    {"name": "embedding_backfill", "interval_seconds": 6 * 3600, "enabled": True},
    {"name": "db_backup", "interval_seconds": 24 * 3600, "enabled": True},
    {"name": "git_onboard_resync", "interval_seconds": 3600, "enabled": False},
]


def is_disabled() -> bool:
    """Honor `OC_MAINTENANCE_DISABLED=1` (or `true`/`yes`/`on`)."""
    raw = os.getenv("OC_MAINTENANCE_DISABLED", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def load_jobs(file_config: dict[str, Any] | None = None) -> list[JobState]:
    """Build JobState list from core.json's `maintenance.jobs` entry.

    Falls back to ``_DEFAULT_JOBS`` when no config is supplied. Unknown
    job names in config are silently dropped (safer than crashing on
    typos in a hand-edited file).
    """
    fc = (file_config or {}).get("maintenance", {}) if file_config else {}
    jobs_config = fc.get("jobs") if isinstance(fc, dict) else None
    if not isinstance(jobs_config, list) or not jobs_config:
        jobs_config = _DEFAULT_JOBS

    known_names = {entry["name"] for entry in _DEFAULT_JOBS}
    states: list[JobState] = []
    for entry in jobs_config:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        if name not in known_names:
            _logger.warning("unknown maintenance job %r in config; skipping", name)
            continue
        states.append(
            JobState(
                name=name,
                interval_seconds=int(entry.get("interval_seconds", 3600)),
                enabled=bool(entry.get("enabled", True)),
            )
        )
    return states
