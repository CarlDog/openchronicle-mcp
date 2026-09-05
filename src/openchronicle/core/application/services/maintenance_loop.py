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
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openchronicle.core.domain.time_utils import utc_now

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

_logger = logging.getLogger(__name__)

# Handler signature: async function that takes the container and returns
# nothing. Failures must raise; the loop catches and counts.
JobHandler = Callable[["CoreContainer"], Awaitable[object]]


@dataclass
class JobState:
    """Per-job runtime state surfaced via /api/v1/maintenance/status."""

    name: str
    interval_seconds: int
    enabled: bool
    last_run_at: datetime | None = None
    # Advanced ONLY by a run that completed without raising, and never
    # cleared by a later failure. `last_run_at` answers "did the loop
    # tick", which a permanently broken job keeps answering forever;
    # this answers "did it last WORK", which is the only question a
    # silent failure cannot fake. Persisted, because a per-process
    # counter resets on every redeploy — and this repo redeploys on
    # every push to main.
    last_success_at: datetime | None = None
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
        handlers: Mapping[str, JobHandler],
        *,
        tick_seconds: float = 1.0,
        state_path: Path | None = None,
    ) -> None:
        self._container = container
        self._jobs = {j.name: j for j in jobs}
        self._handlers = handlers
        self._tick_seconds = tick_seconds
        self._state_path = state_path
        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event = asyncio.Event()
        # Global mutex so background-spawned jobs still execute one-at-
        # a-time (no two jobs ever run concurrently in this process; a
        # vacuum + backfill would otherwise race the same DB).
        self._global_lock: asyncio.Lock = asyncio.Lock()
        self._inflight: set[asyncio.Task[None]] = set()

    def _safe_observe_job(self, *, name: str, outcome: str, duration_seconds: float | None = None) -> None:
        try:
            self._container.metrics.observe_job(
                name=name,
                outcome=outcome,
                duration_seconds=duration_seconds,
            )
        except Exception:  # metrics must never stop maintenance
            _logger.warning("metrics recorder failed while observing maintenance job", exc_info=False)

    def _safe_set_last_success(self, *, name: str, timestamp: datetime) -> None:
        try:
            self._container.metrics.set_job_last_success(name=name, timestamp_seconds=timestamp.timestamp())
        except Exception:  # metrics must never stop maintenance
            _logger.warning("metrics recorder failed while seeding maintenance success", exc_info=False)

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
                    "last_success_at": job.last_success_at.isoformat() if job.last_success_at else None,
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
        self._load_state()
        for job in self._jobs.values():
            if job.last_success_at is not None:
                self._safe_set_last_success(name=job.name, timestamp=job.last_success_at)
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
        except TimeoutError, asyncio.CancelledError:
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
        """Run one job through the full loop machinery: locks, counters,
        both timestamps, and state persistence.

        NOT the path `oc maintenance run-once` takes, despite the name —
        that CLI calls the handler directly (`cli/commands/maintenance.py`)
        and so bypasses the global lock, the counters, and
        ``last_success_at``. Corrected 2026-08-23; the docstring had
        claimed the CLI used this. Production callers: none today.
        """
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
                        self._safe_observe_job(name=job.name, outcome="overlap")
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
                await asyncio.wait_for(self._stop_event.wait(), timeout=self._tick_seconds)
            except TimeoutError:
                continue

    def _spawn(self, job: JobState) -> None:
        task = asyncio.create_task(self._invoke(job), name=f"oc-maint-{job.name}")
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)

    async def _invoke(self, job: JobState) -> None:
        # job._lock = next-tick overlap detection. self._global_lock =
        # process-wide mutex so two jobs never run simultaneously.
        started = time.monotonic()
        metric_outcome = "failure"
        async with job._lock, self._global_lock:
            handler = self._handlers.get(job.name)
            if handler is None:
                _logger.error("maintenance job %s has no handler registered", job.name)
                job.last_outcome = "failed"
                job.last_error = "no handler registered"
                job.runs_failed += 1
                job.runs_total += 1
                job.last_run_at = utc_now()
                self._safe_observe_job(
                    name=job.name,
                    outcome="failure",
                    duration_seconds=time.monotonic() - started,
                )
                return

            _logger.info("maintenance job %s: running", job.name)
            succeeded = False
            try:
                result = await handler(self._container)
                job.last_outcome = "ok"
                job.last_error = None
                job.runs_ok += 1
                succeeded = True
                metric_outcome = "partial" if _job_result_is_partial(result) else "success"
            except Exception as exc:
                _logger.exception("maintenance job %s failed", job.name)
                job.last_outcome = "failed"
                job.last_error = str(exc)
                job.runs_failed += 1
                metric_outcome = "failure"
            except asyncio.CancelledError:
                metric_outcome = "cancel"
                raise
            finally:
                job.runs_total += 1
                # One timestamp for both, so a successful run reads
                # last_run_at == last_success_at exactly rather than
                # differing by the microseconds between two utc_now()
                # calls — a difference that looks like a signal.
                now = utc_now()
                job.last_run_at = now
                if succeeded:
                    job.last_success_at = now
                    self._safe_set_last_success(name=job.name, timestamp=now)
                self._safe_observe_job(
                    name=job.name,
                    outcome=metric_outcome,
                    duration_seconds=time.monotonic() - started,
                )
                await asyncio.to_thread(self._persist_state)

    @staticmethod
    def _parse_timestamp_map(raw: dict[str, Any], key: str) -> dict[str, datetime]:
        """Parse one ``{job_name: iso8601}`` block, skipping anything odd.

        Shared by the two blocks in the state file so their tolerance
        rules cannot drift: a missing block, a non-dict block, a
        non-string value, or an unparseable timestamp each degrade to
        "that job has no value", never to an exception.
        """
        parsed: dict[str, datetime] = {}
        entries = raw.get(key)
        if not isinstance(entries, dict):
            return parsed
        for name, iso in entries.items():
            if not isinstance(iso, str):
                continue
            try:
                parsed[name] = datetime.fromisoformat(iso)
            except ValueError:
                continue
        return parsed

    def _load_state(self) -> None:
        """Restore persisted ``last_run_at`` / ``last_success_at``.

        ``last_run_at`` exists so a container restart doesn't make every
        job due at once: without it every JobState starts fresh and
        ``_is_due`` fires every enabled job on boot — two backups per
        restart (db_backup + db_vacuum's backup-first), which under the
        redeploy-on-push deployment model eroded the backup retention
        window to same-day snapshots.

        ``last_success_at`` exists for the opposite reason: it must
        survive a restart so a job that has been failing for weeks
        cannot present a clean surface after each redeploy. Counters
        stay per-process; the two timestamps survive.

        A state file written before ``last_success_at`` existed simply
        has no such block, which parses to empty — old files load, they
        do not raise. That matters more than it sounds: an exception
        here happens at boot, under ``restart: unless-stopped``, which
        is the crash-loop this file exists to prevent.
        """
        if self._state_path is None:
            return
        # Fully defensive: a corrupt or weird state file must never block
        # boot (crash-loop rule) — worst case is pre-persistence behavior.
        try:
            if not self._state_path.exists():
                return
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return
            run_at = self._parse_timestamp_map(raw, "last_run_at")
            success_at = self._parse_timestamp_map(raw, "last_success_at")
            for name, job in self._jobs.items():
                if name in run_at:
                    job.last_run_at = run_at[name]
                if name in success_at:
                    job.last_success_at = success_at[name]
        except Exception as exc:
            _logger.warning("maintenance state file unreadable (%s); starting fresh", exc)

    def _persist_state(self) -> None:
        """Write per-job ``last_run_at`` / ``last_success_at`` atomically.

        Called after every job run, serialized by the global lock. A
        write failure degrades to pre-persistence behavior (all jobs due
        on next boot) — logged, never fatal.
        """
        if self._state_path is None:
            return
        try:
            # Built INSIDE the try on purpose. This runs from _invoke's
            # `finally`, where a raise would escape the job task — and
            # the docstring's "never fatal" has to cover assembling the
            # payload, not just writing it. Two near-identical
            # comprehensions is exactly the shape where a copy-paste
            # slip (wrong attribute in the None-filter) turns into an
            # AttributeError on the first job that has run but never
            # succeeded.
            payload = {
                "last_run_at": {
                    j.name: j.last_run_at.isoformat() for j in self._jobs.values() if j.last_run_at is not None
                },
                "last_success_at": {
                    j.name: j.last_success_at.isoformat() for j in self._jobs.values() if j.last_success_at is not None
                },
            }
            tmp = self._state_path.with_suffix(".tmp")
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, self._state_path)
        except Exception as exc:
            _logger.warning("failed to persist maintenance state to %s: %s", self._state_path, exc)


def _is_due(job: JobState, now: datetime) -> bool:
    if job.last_run_at is None:
        return True
    return now - job.last_run_at >= timedelta(seconds=job.interval_seconds)


def _job_result_is_partial(result: object) -> bool:
    """Recognize the one built-in handler result that carries partial counts."""
    return isinstance(result, Mapping) and bool(result.get("failed"))


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
    """Build JobState list by MERGING core.json's `maintenance.jobs` onto the defaults.

    A config entry overrides the matching default **by name**; every job
    it does not mention keeps its default. Omitting a job therefore does
    NOT disable it — set ``"enabled": false`` explicitly, which is how the
    shipped example already expresses "off" for ``git_onboard_resync``.

    This used to be a total replacement, and that silently cost the
    operator jobs twice over. Tuning one interval meant hand-copying every
    other job or losing it — including ``db_backup``. Worse, the entrypoint
    seeds ``/config`` from ``core.json.example`` with ``cp -rn``, so a
    stale seeded file would have dropped every job added in any future
    release, with no warning: the loop only ever warned about *unknown*
    names, never missing ones. Merging makes both harmless.

    Unknown job names are warned about and skipped rather than raising —
    a typo in a hand-edited file must not crash the config path, which
    under ``restart: unless-stopped`` is an indefinite crash-loop.

    Ordering follows ``_DEFAULT_JOBS``, not the config file, so the status
    surface is stable regardless of how an operator arranged their JSON.
    """
    fc = (file_config or {}).get("maintenance", {}) if file_config else {}
    jobs_config = fc.get("jobs") if isinstance(fc, dict) else None

    overrides: dict[str, dict[str, Any]] = {}
    known_names = {entry["name"] for entry in _DEFAULT_JOBS}
    if isinstance(jobs_config, list):
        for entry in jobs_config:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str) or name not in known_names:
                _logger.warning("unknown maintenance job %r in config; skipping", name)
                continue
            overrides[name] = entry

    states: list[JobState] = []
    for default in _DEFAULT_JOBS:
        name = default["name"]
        entry = {**default, **overrides.get(name, {})}
        # Fail soft on a bad interval (hand-edited core.json) — one typo
        # must not crash create_app into a restart loop, and a
        # zero/negative interval would fire the job every tick.
        interval_raw = entry.get("interval_seconds", 3600)
        try:
            interval = int(interval_raw)
        except TypeError, ValueError:
            _logger.warning("invalid interval_seconds %r for job %s; using 3600", interval_raw, name)
            interval = 3600
        if interval <= 0:
            _logger.warning("non-positive interval_seconds %r for job %s; using 3600", interval_raw, name)
            interval = 3600
        states.append(
            JobState(
                name=name,
                interval_seconds=interval,
                enabled=bool(entry.get("enabled", True)),
            )
        )
    return states
