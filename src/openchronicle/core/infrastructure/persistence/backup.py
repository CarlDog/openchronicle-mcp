"""Online SQLite backup using sqlite3.Connection.backup().

The stdlib backup API safely snapshots a live database while writes are
in flight — far more reliable than ``shutil.copy()`` against a WAL-mode
DB. v2 used file-copy in some paths and lost a backup to a torn-write
on 2026-04-29; v3 routes every backup through this module.

Atomicity guarantees:
  - The destination is written to a sibling ``<dest>.tmp`` first, then
    ``os.replace`` renames it on success.
  - ``os.replace`` is atomic on POSIX and Windows (assuming same
    filesystem), so callers either see the previous file or the new one,
    never a half-written backup.
  - On error, the ``.tmp`` is removed and the previous file is left intact.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

_logger = logging.getLogger(__name__)


def backup_to(src_db_path: Path | str, dest_db_path: Path | str) -> Path:
    """Snapshot ``src_db_path`` to ``dest_db_path`` atomically.

    The source connection can have writers in flight; SQLite's online
    backup API copies pages safely. Returns the destination ``Path``
    on success. Raises whatever sqlite3 raises on failure (the caller
    handles logging/retry).
    """
    src = Path(src_db_path)
    dest = Path(dest_db_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()

    src_conn = sqlite3.connect(str(src))
    try:
        with sqlite3.connect(str(tmp)) as dst_conn:
            src_conn.backup(dst_conn)
        os.replace(tmp, dest)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    finally:
        src_conn.close()

    _logger.info("Online backup written: %s (%d bytes)", dest, dest.stat().st_size)
    return dest


def backup_from_connection(conn: sqlite3.Connection, dest_db_path: Path | str) -> Path:
    """Snapshot from an open connection (e.g. SqliteStore._conn).

    Use when the caller already holds an open connection and wants to
    avoid re-opening the file. Same atomicity guarantees as
    ``backup_to``.
    """
    dest = Path(dest_db_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()

    try:
        with sqlite3.connect(str(tmp)) as dst_conn:
            conn.backup(dst_conn)
        os.replace(tmp, dest)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise

    _logger.info("Online backup written: %s (%d bytes)", dest, dest.stat().st_size)
    return dest
