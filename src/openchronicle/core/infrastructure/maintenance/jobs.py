"""Built-in maintenance job handlers for the maintenance loop.

Each handler is a coroutine ``async def(container) -> None``. Failures
must raise; the loop catches and counts.

Job inventory:
- ``db_backup`` — atomic online backup to ``auto/`` under
  ``OC_BACKUP_DIR`` (default ``${data_dir}/backups``), published with a
  verified manifest; retention keeps the 7 newest plus the newest per
  day for 7 days. A snapshot that fails verification is kept as
  ``*.failed-verify`` and the job fails.
- ``db_vacuum`` — runs ``db_backup`` first (backup-before-destructive
  policy), then ``PRAGMA wal_checkpoint(FULL)`` and ``VACUUM``.
- ``db_integrity_check`` — ``PRAGMA integrity_check``; on failure,
  triggers an immediate ``db_backup`` and sets the container's
  ``maintenance_degraded`` flag so ``/health`` and ``/api/v1/health``
  surface the condition.
- ``embedding_backfill`` — equivalent to
  ``oc memory embed --backfill`` (no-op when nothing is missing).
- ``git_onboard_resync`` — placeholder; off by default. Will scan the
  ``OC_GIT_ONBOARD_REPOS`` env var when implemented.
- ``cloud_backup`` — encrypts the newest published snapshots to the age
  recipients in ``OC_CLOUD_AGE_RECIPIENTS`` and ``rclone copy``s them to
  ``OC_CLOUD_REMOTE`` (design 0001). Append-only: never ``sync``, never
  deletes, never overwrites. Skipped (not a success) while the remote is unset.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openchronicle.core.application.config.offsite import read_cloud_backup_config
from openchronicle.core.domain.time_utils import utc_now

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

_logger = logging.getLogger(__name__)

_BACKUP_RETENTION = 7

# Cloud backup (design 0001 §3, plan review amendments A1-A9).
# The whole handler runs inside this bound. It is also the only release
# guarantee for the loop's global lock and the worst-case container-stop delay.
_CLOUD_TIMEOUT_SECONDS = 900.0
# db_backup runs every 24 h; a newest published snapshot older than this means
# snapshots have stopped, and pushing the same old ones again must not count
# as success (A1).
_CLOUD_SOURCE_MAX_AGE = timedelta(hours=26)
_CLOUD_CLOCK_SKEW = timedelta(minutes=5)
_CLOUD_WINDOW = 3  # the 3 newest, plus the newest from each of 3 recent UTC days (A2)
_CLOUD_TMP_PREFIX = "cloud-push-"
_STAMP_FORMAT = "%Y%m%dT%H%M%S%fZ"
_recipients_logged: tuple[str, ...] | None = None


def _auto_backup_dir(container: CoreContainer) -> Path:
    return container.backup_dir / "auto"


def _is_published(path: Path) -> bool:
    """A snapshot is published once its manifest exists (design 0017).

    The catalog writes the manifest last, after the database is flushed and
    inspected, so a `.db` without one was never a usable artifact. Retention
    and the cloud push share this rule; two copies of it would drift.
    """
    return path.suffix == ".db" and path.with_suffix(".json").is_file()


def _snapshot_stamp(path: Path) -> datetime | None:
    """The UTC creation stamp in `openchronicle-<stamp>-<hex>.db`, or None."""
    name = path.stem.removeprefix("openchronicle-")
    try:
        return datetime.strptime(name.split("-", 1)[0], _STAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def _published_snapshots(directory: Path) -> list[tuple[datetime, Path]]:
    """Published snapshots with a parseable stamp, oldest first."""
    found = []
    for path in directory.glob("*.db"):
        stamp = _snapshot_stamp(path)
        if stamp is not None and _is_published(path):
            found.append((stamp, path))
    return sorted(found)


def _retention_prune(directory: Path, keep: int) -> None:
    """Prune old backups, keeping the union of two sets:

    - the ``keep`` newest files overall (protects same-day bursts —
      manual run-once backups, vacuum's backup-first), and
    - the newest file from each of the ``keep`` most recent UTC days
      that have backups.

    The per-day set is what a pure newest-N rule lacked: a burst of
    restarts or manual runs filled all N slots with same-day snapshots
    and evicted the week-old backup that matters after discovering
    corruption. Worst-case published snapshots retained: 2 × ``keep``.
    Files outside that set are never pruned: pre-catalog snapshots
    without a manifest, and ``*.failed-*`` quarantines.
    """
    # A database file without its manifest was never published as a usable
    # artifact. Do not let an interrupted publication evict a valid recovery
    # point from either retention set. Preserve old manifestless files for
    # explicit operator review rather than deleting them implicitly.
    candidates = sorted(
        (path for path in directory.glob("*.db") if _is_published(path)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    keep_set: set[Path] = set(candidates[:keep])
    newest_per_day: dict[str, Path] = {}
    for path in candidates:  # newest-first, so the first hit per day wins
        day = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).strftime("%Y-%m-%d")
        if day not in newest_per_day:
            newest_per_day[day] = path
    for day in sorted(newest_per_day, reverse=True)[:keep]:
        keep_set.add(newest_per_day[day])
    for path in candidates:
        if path in keep_set:
            continue
        try:
            path.unlink()
            path.with_suffix(".json").unlink(missing_ok=True)
        except OSError as exc:
            _logger.warning("backup retention: failed to prune %s: %s", path, exc)


async def db_backup(container: CoreContainer) -> None:
    """Take an online backup; prune to the last `_BACKUP_RETENTION`.

    Filename uses microsecond-precision UTC timestamp so two backups in
    the same second (e.g. db_vacuum's pre-backup followed immediately by
    a standalone db_backup tick) don't overwrite each other. Triage
    finding from the 2026-05-06 cutover.
    """
    directory = _auto_backup_dir(container)
    # The stdlib backup API blocks; run on a worker thread so the
    # asyncio loop stays responsive. The store method holds the store lock.
    artifact = await asyncio.to_thread(container.backups.create, "auto")
    await asyncio.to_thread(_retention_prune, directory, _BACKUP_RETENTION)
    _logger.info("db_backup: wrote %s; retention pruned to last %d", artifact["artifact_id"], _BACKUP_RETENTION)


async def db_vacuum(container: CoreContainer) -> None:
    """Backup-before-destructive policy: backup, checkpoint, vacuum."""
    await db_backup(container)
    # Store method holds the store lock — VACUUM can never run inside
    # another thread's open transaction on the shared connection.
    await asyncio.to_thread(container.storage.vacuum)
    _logger.info("db_vacuum: WAL checkpointed + VACUUM complete")


async def db_integrity_check(container: CoreContainer) -> None:
    """Run integrity_check; on failure, backup + flag degraded."""
    result = await asyncio.to_thread(container.storage.integrity_check)
    if result != "ok":
        # Snapshot before doing anything else, then flag degraded so
        # callers (health endpoint, MCP health tool) surface it.
        _logger.error("db_integrity_check FAILED: %s — taking emergency backup", result)
        try:
            await db_backup(container)
        except Exception:
            _logger.exception("emergency backup also failed")
        container.maintenance_degraded = True
        raise RuntimeError(f"integrity_check failed: {result}")

    # On success, clear any previously-set degraded flag.
    if container.maintenance_degraded:
        container.maintenance_degraded = False
        _logger.info("db_integrity_check: previously-degraded flag cleared")


async def embedding_backfill(container: CoreContainer) -> dict[str, int] | None:
    """Generate embeddings for memories that lack them. No-op when none."""
    service = container.embedding_service
    if service is None:
        _logger.debug("embedding_backfill: no embedding service configured; skipping")
        return None

    def _run() -> dict[str, int]:
        result = service.generate_missing(force=False)
        summary = {"generated": result.generated, "failed": result.failed, "tombstoned": result.tombstoned}
        if result.skipped:
            # Another backfill (operator or revision reconciliation) is doing
            # this work right now; a second one would only double the embeds.
            # The loop records "skipped", never a success (pre-deploy review).
            _logger.info("embedding_backfill: another backfill is running; skipped")
            summary["skipped"] = 1
        return summary

    summary = await asyncio.to_thread(_run)
    # A total failure must FAIL the job: returning normally here let the
    # loop record last_outcome="ok" and advance last_success_at while
    # zero vectors were generated — a dead provider produced "backfill
    # succeeded" every night (the Ollama review's success-shaped health
    # defect). Partial success stays a completed-but-degraded run with
    # exact counts; zero candidates stays a clean no-op. Tombstoned rows
    # (ADR 0009) are classified permanent outcomes, not failures — a
    # tombstoned-only run is a SUCCESS, and this guard expression
    # deliberately doesn't see them.
    if summary["failed"] and not summary["generated"]:
        raise RuntimeError(
            f"embedding_backfill: 0 generated, {summary['failed']} failed, "
            f"{summary['tombstoned']} tombstoned — provider down?"
        )
    if summary["failed"]:
        _logger.warning(
            "embedding_backfill: partial failure — generated=%d failed=%d tombstoned=%d",
            summary["generated"],
            summary["failed"],
            summary["tombstoned"],
        )
    elif summary["generated"] or summary["tombstoned"]:
        _logger.info(
            "embedding_backfill: generated=%d tombstoned=%d",
            summary["generated"],
            summary["tombstoned"],
        )
    return summary


async def git_onboard_resync(container: CoreContainer) -> None:
    """Placeholder — full implementation lands when a tracked-repo list exists.

    Off by default in the config; this handler exists so the registry
    name resolves and the loop can dispatch to it without crashing.
    """
    _logger.debug("git_onboard_resync: not implemented yet (off by default)")


def _select_for_push(published: list[tuple[datetime, Path]]) -> list[Path]:
    """The 3 newest, plus the newest from each of the 3 most recent UTC days.

    A count-only window can skip a whole day: db_vacuum's backup-first and
    manual runs add same-day snapshots (plan review A2, the defect retention
    already fixed). Returned oldest first.
    """
    chosen = {path for _, path in published[-_CLOUD_WINDOW:]}
    per_day: dict[str, Path] = {}
    for stamp, path in reversed(published):  # newest first: the first hit per day wins
        per_day.setdefault(stamp.strftime("%Y-%m-%d"), path)
    for day in sorted(per_day, reverse=True)[:_CLOUD_WINDOW]:
        chosen.add(per_day[day])
    return [path for _, path in published if path in chosen]


def _sweep_stale_push_dirs(root: Path) -> None:
    """Remove push temp dirs a killed run left behind; never raises.

    A SIGKILL skips the TemporaryDirectory cleanup. Only a directory older than
    the handler's own timeout can belong to no live run.
    """
    try:
        for entry in root.glob(f"{_CLOUD_TMP_PREFIX}*"):
            if entry.is_dir() and time.time() - entry.stat().st_mtime > _CLOUD_TIMEOUT_SECONDS:
                shutil.rmtree(entry, ignore_errors=True)
                _logger.info("cloud_backup: removed stale temp dir %s", entry.name)
    except OSError as exc:
        _logger.warning("cloud_backup: could not sweep stale temp dirs: %s", exc)


async def _run_captured(argv: list[str], env: dict[str, str]) -> tuple[int, bytes]:
    """Run a child with captured pipes; kill it if the caller is cancelled.

    A native subprocess rather than to_thread(subprocess.run): cancelling a
    thread does not stop it, and a hung upload would outlive the timeout.
    """
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    try:
        _, stderr = await proc.communicate()
        return (proc.returncode if proc.returncode is not None else -1), stderr
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()


def _stderr_tail(stderr: bytes) -> str:
    return stderr.decode("utf-8", "replace")[-2048:].strip()


def _rclone_argv(source: Path, remote: str) -> list[str]:
    """`copy`, never `sync`: the remote is append-only (design 0001 §3.3)."""
    return [
        "rclone",
        "copy",
        "--ignore-existing",
        "--transfers",
        "1",
        "--contimeout",
        "30s",
        "--stats",
        "0",
        "--ask-password=false",
        "--log-level",
        "INFO",
        "--",
        str(source),
        f"{remote.rstrip('/')}/",
    ]


async def cloud_backup(container: CoreContainer) -> dict[str, Any] | None:
    """Encrypt the newest published snapshots and copy them offsite.

    Raises on anything that would otherwise report success without a fresh
    snapshot landing offsite (plan review A1): an invalid configuration, a
    root run, a missing rclone.conf, no published snapshot, or a newest
    snapshot that is stale or stamped in the future.
    """
    config = read_cloud_backup_config()
    if not config.enabled:
        _logger.debug("cloud_backup: OC_CLOUD_REMOTE is unset; skipped")
        # Skipped, never a success: a success stamp now would make health read
        # "ok" on the day the feature is first enabled, before anything pushed.
        return {"skipped": 1, "reason": "OC_CLOUD_REMOTE is unset"}
    if config.problem:
        raise ValueError(f"cloud_backup: {config.problem}")
    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        # As root, rclone's token refresh rewrites rclone.conf root-owned 0600,
        # locking the nightly run (uid 1000) out until the next restart (A4).
        raise PermissionError(
            "cloud_backup: refusing to run as root; use `docker exec --user 1000:1000` "
            "or the Portainer console as user oc"
        )

    global _recipients_logged
    if _recipients_logged != config.recipients:
        # Public keys, safe in logs; compare them with escrow (design 0001 §6.4).
        _logger.info("cloud_backup: age recipients %s", ", ".join(config.recipients))
        _recipients_logged = config.recipients

    rclone_config = os.environ.get("RCLONE_CONFIG", "").strip() or str(container.paths.config_dir / "rclone.conf")
    if not Path(rclone_config).is_file():
        raise FileNotFoundError(
            f"cloud_backup: rclone config not found at {rclone_config}; install it as uid 1000 (see the runbook)"
        )

    async with asyncio.timeout(_CLOUD_TIMEOUT_SECONDS):
        root = container.backup_dir
        await asyncio.to_thread(_sweep_stale_push_dirs, root)
        published = await asyncio.to_thread(_published_snapshots, _auto_backup_dir(container))
        if not published:
            raise RuntimeError(f"cloud_backup: no published snapshot in {_auto_backup_dir(container)}")
        newest = published[-1][0]
        now = utc_now()
        if newest > now + _CLOUD_CLOCK_SKEW:
            raise RuntimeError(f"cloud_backup: newest snapshot is stamped in the future ({newest.isoformat()})")
        if now - newest > _CLOUD_SOURCE_MAX_AGE:
            raise RuntimeError(
                f"cloud_backup: newest published snapshot is from {newest.isoformat()}; "
                "db_backup has stopped producing, so nothing fresh would go offsite"
            )
        selected = _select_for_push(published)

        # Never ship a snapshot that no longer matches its manifest (A3).
        for path in selected:
            artifact_id = "auto:" + path.stem.removeprefix("openchronicle-")
            await asyncio.to_thread(container.backups.verify, artifact_id)

        with tempfile.TemporaryDirectory(prefix=_CLOUD_TMP_PREFIX, dir=root) as tmp:
            out = Path(tmp) / "out"
            cache = Path(tmp) / "cache"  # outside `out`, or rclone would upload it
            out.mkdir()
            cache.mkdir()
            recipient_args = [arg for key in config.recipients for arg in ("-r", key)]
            for path in selected:
                for source in (path, path.with_suffix(".json")):
                    rc, stderr = await _run_captured(
                        ["age", *recipient_args, "-o", str(out / f"{source.name}.age"), str(source)],
                        dict(os.environ),
                    )
                    if rc != 0:
                        raise RuntimeError(f"cloud_backup: age exited {rc} for {source.name}: {_stderr_tail(stderr)}")
            env = {
                **os.environ,
                "RCLONE_CONFIG": rclone_config,
                "RCLONE_CACHE_DIR": str(cache),
                "XDG_CACHE_HOME": str(cache),
            }
            rc, stderr = await _run_captured(_rclone_argv(out, config.remote), env)
            if rc != 0:
                raise RuntimeError(f"cloud_backup: rclone exited {rc}: {_stderr_tail(stderr)}")
            if b"ERROR" in stderr:
                # rclone exits 0 when it cannot save a refreshed token; the
                # upload landed, but the next refresh may not.
                _logger.warning("cloud_backup: rclone reported errors: %s", _stderr_tail(stderr))

    for path in selected:
        manifest = path.with_suffix(".json").read_text(encoding="utf-8")
        _logger.info("cloud_backup: offsite %s sha256=%s", path.name, _manifest_sha256(manifest))
    return {"selected": len(selected)}


def _manifest_sha256(manifest_text: str) -> str:
    try:
        return str(json.loads(manifest_text).get("sha256", "?"))
    except ValueError:
        return "?"


HANDLERS = {
    "db_backup": db_backup,
    "db_vacuum": db_vacuum,
    "db_integrity_check": db_integrity_check,
    "embedding_backfill": embedding_backfill,
    "git_onboard_resync": git_onboard_resync,
    "cloud_backup": cloud_backup,
}
