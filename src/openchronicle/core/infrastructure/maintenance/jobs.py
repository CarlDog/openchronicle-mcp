"""Built-in maintenance job handlers for the maintenance loop.

Each handler is a coroutine ``async def(container) -> None``. Failures
must raise; the loop catches and counts.

Job inventory:
- ``db_backup`` — atomic online backup to ``${data_dir}/backups/auto/``,
  retains the last 7.
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
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from openchronicle.core.infrastructure.persistence.backup import backup_from_connection

if TYPE_CHECKING:
    from openchronicle.core.infrastructure.wiring.container import CoreContainer

_logger = logging.getLogger(__name__)

_BACKUP_RETENTION = 7


def _auto_backup_dir(container: CoreContainer) -> Path:
    base = container.paths.db_path.parent
    return base / "backups" / "auto"


def _retention_prune(directory: Path, keep: int) -> None:
    """Keep the `keep` newest *.db files; delete older ones."""
    candidates = sorted(directory.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates[keep:]:
        try:
            path.unlink()
        except OSError as exc:
            _logger.warning("backup retention: failed to prune %s: %s", path, exc)


async def db_backup(container: CoreContainer) -> None:
    """Take an online backup; prune to the last `_BACKUP_RETENTION`."""
    directory = _auto_backup_dir(container)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = directory / f"openchronicle-{timestamp}.db"

    # The stdlib backup API blocks; run on a worker thread so the
    # asyncio loop stays responsive.
    await asyncio.to_thread(backup_from_connection, container.storage._conn, dest)
    await asyncio.to_thread(_retention_prune, directory, _BACKUP_RETENTION)
    _logger.info("db_backup: wrote %s; retention pruned to last %d", dest, _BACKUP_RETENTION)


async def db_vacuum(container: CoreContainer) -> None:
    """Backup-before-destructive policy: backup, checkpoint, vacuum."""
    await db_backup(container)
    conn = container.storage._conn  # noqa: SLF001

    def _do_vacuum() -> None:
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        conn.execute("VACUUM")

    await asyncio.to_thread(_do_vacuum)
    _logger.info("db_vacuum: WAL checkpointed + VACUUM complete")


async def db_integrity_check(container: CoreContainer) -> None:
    """Run integrity_check; on failure, backup + flag degraded."""
    conn = container.storage._conn  # noqa: SLF001

    def _check() -> str:
        return str(conn.execute("PRAGMA integrity_check").fetchone()[0])

    result = await asyncio.to_thread(_check)
    if result != "ok":
        # Snapshot before doing anything else, then flag degraded so
        # callers (health endpoint, MCP health tool) surface it.
        _logger.error("db_integrity_check FAILED: %s — taking emergency backup", result)
        try:
            await db_backup(container)
        except Exception:
            _logger.exception("emergency backup also failed")
        # Flag is opaque on the container; consumers read via getattr
        # to avoid hard-coupling every call site.
        setattr(container, "maintenance_degraded", True)  # noqa: B010
        raise RuntimeError(f"integrity_check failed: {result}")

    # On success, clear any previously-set degraded flag.
    if getattr(container, "maintenance_degraded", False):
        setattr(container, "maintenance_degraded", False)  # noqa: B010
        _logger.info("db_integrity_check: previously-degraded flag cleared")


async def embedding_backfill(container: CoreContainer) -> None:
    """Generate embeddings for memories that lack them. No-op when none."""
    service = container.embedding_service
    if service is None:
        _logger.debug("embedding_backfill: no embedding service configured; skipping")
        return

    def _run() -> dict[str, int]:
        result = service.generate_missing(force=False)
        return {"generated": result.generated, "failed": result.failed}

    summary = await asyncio.to_thread(_run)
    if summary["generated"] or summary["failed"]:
        _logger.info(
            "embedding_backfill: generated=%d failed=%d",
            summary["generated"],
            summary["failed"],
        )


async def git_onboard_resync(container: CoreContainer) -> None:
    """Placeholder — full implementation lands when a tracked-repo list exists.

    Off by default in the config; this handler exists so the registry
    name resolves and the loop can dispatch to it without crashing.
    """
    _logger.debug("git_onboard_resync: not implemented yet (off by default)")


HANDLERS = {
    "db_backup": db_backup,
    "db_vacuum": db_vacuum,
    "db_integrity_check": db_integrity_check,
    "embedding_backfill": embedding_backfill,
    "git_onboard_resync": git_onboard_resync,
}
