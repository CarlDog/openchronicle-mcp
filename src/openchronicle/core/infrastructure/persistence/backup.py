"""Online SQLite backup using sqlite3.Connection.backup().

The stdlib backup API safely snapshots a live database while writes are
in flight — far more reliable than ``shutil.copy()`` against a WAL-mode
DB. v2 used file-copy in some paths and lost a backup to a torn-write
on 2026-04-29; v3 routes every backup through this module.

Publication guarantees (verify, then rename):
  - The destination is written to a sibling ``<dest>.tmp`` first.
  - The staged file is re-opened read-only and must pass
    ``PRAGMA quick_check`` before it may replace anything — an artifact
    that cannot be proven openable is not a backup (the 2026-05-06
    cutover shipped a corrupt DB that nothing had validated).
  - ``os.replace`` is atomic on POSIX and Windows (assuming same
    filesystem), so callers either see the previous file or the new one,
    never a half-written backup.
  - A staged file that FAILS validation is preserved as
    ``<dest>.failed-quick-check`` (forensic evidence that the LIVE db
    may be corrupt — deleting it would discard the proof), the previous
    destination is left intact, and the error raises. Other errors
    remove the ``.tmp``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sqlite3
from pathlib import Path

_logger = logging.getLogger(__name__)


class BackupValidationError(RuntimeError):
    """The staged backup failed integrity validation before publication."""


def _validate_staged(tmp: Path) -> None:
    """``PRAGMA quick_check`` on the staged artifact; anything but ``ok`` raises.

    Opened read-only via URI so validation cannot mutate the artifact it
    is judging. ``quick_check`` (not ``integrity_check``) is deliberate:
    it proves the file opens and its structure is sound at this
    database's size in milliseconds, while the deeper scan already runs
    as the scheduled ``db_integrity_check`` maintenance job against the
    live DB.
    """
    check_conn = sqlite3.connect(f"file:{tmp.as_posix()}?mode=ro", uri=True)
    try:
        row = check_conn.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupValidationError(f"staged backup is not a readable SQLite database: {exc}") from exc
    finally:
        check_conn.close()
    result = row[0] if row else "(no result)"
    if result != "ok":
        raise BackupValidationError(f"staged backup failed quick_check: {result!r}")


def backup_from_connection(conn: sqlite3.Connection, dest_db_path: Path | str) -> Path:
    """Snapshot from an open connection (e.g. SqliteStore._conn).

    Use when the caller already holds an open connection and wants to
    avoid re-opening the file. Publication guarantees per the module
    docstring: staged, validated, then atomically renamed.
    """
    dest = Path(dest_db_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()

    try:
        # Explicit close required so Windows can rename the file via
        # os.replace.
        dst_conn = sqlite3.connect(str(tmp))
        try:
            conn.backup(dst_conn)
        finally:
            dst_conn.close()
        try:
            _validate_staged(tmp)
        except BackupValidationError:
            # Quarantine, don't delete: this artifact is the evidence
            # that the live DB may be corrupt. The name is outside the
            # retention glob (backups/auto/*.db), so it is never pruned
            # or mistaken for a restorable backup.
            quarantine = dest.with_name(dest.name + ".failed-quick-check")
            with contextlib.suppress(OSError):
                os.replace(tmp, quarantine)
                _logger.error("Invalid staged backup preserved for forensics: %s", quarantine)
            raise
        os.replace(tmp, dest)
    except Exception:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()
        raise

    _logger.info("Online backup written: %s (%d bytes)", dest, dest.stat().st_size)
    return dest
