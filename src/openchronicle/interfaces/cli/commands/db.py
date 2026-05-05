"""Database maintenance CLI commands: db info/vacuum/backup/stats."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from openchronicle.core.infrastructure.persistence.backup import backup_from_connection
from openchronicle.core.infrastructure.wiring.container import CoreContainer

from ._helpers import json_envelope, print_json

_TABLE_NAMES = [
    "projects",
    "memory_items",
    "memory_embeddings",
]


def cmd_db(args: argparse.Namespace, container: CoreContainer) -> int:
    db_dispatch: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
        "info": cmd_db_info,
        "vacuum": cmd_db_vacuum,
        "backup": cmd_db_backup,
        "stats": cmd_db_stats,
    }
    handler = db_dispatch.get(args.db_command)
    if handler is None:
        print("Usage: oc db {info|vacuum|backup|stats}")
        return 1
    return handler(args, container)


def cmd_db_info(args: argparse.Namespace, container: CoreContainer) -> int:
    """Show database information: file sizes, row counts, pragmas, integrity."""
    conn = container.storage._conn  # noqa: SLF001
    db_path = container.storage.db_path

    db_size = db_path.stat().st_size if db_path.exists() else 0
    wal_path = Path(f"{db_path}-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0

    row_counts: dict[str, int] = {}
    for table in _TABLE_NAMES:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        row_counts[table] = cur.fetchone()[0]

    pragmas: dict[str, str] = {}
    for pragma in ("journal_mode", "foreign_keys", "busy_timeout", "synchronous"):
        cur = conn.execute(f"PRAGMA {pragma}")
        pragmas[pragma] = str(cur.fetchone()[0])

    cur = conn.execute("PRAGMA integrity_check")
    integrity = str(cur.fetchone()[0])

    if args.json:
        payload = json_envelope(
            command="db.info",
            ok=True,
            result={
                "db_path": str(db_path),
                "db_size_bytes": db_size,
                "wal_size_bytes": wal_size,
                "row_counts": row_counts,
                "pragmas": pragmas,
                "integrity": integrity,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Database: {db_path}")
    print(f"Size: {db_size:,} bytes")
    print(f"WAL: {wal_size:,} bytes")
    print()
    print("Row counts:")
    for table, count in row_counts.items():
        print(f"  {table:<20} {count:>8,}")
    print()
    print("Pragmas:")
    for pragma, value in pragmas.items():
        print(f"  {pragma:<20} {value}")
    print()
    print(f"Integrity: {integrity}")
    return 0


def cmd_db_vacuum(args: argparse.Namespace, container: CoreContainer) -> int:
    """Run VACUUM and WAL checkpoint to compact the database."""
    conn = container.storage._conn  # noqa: SLF001
    db_path = container.storage.db_path

    size_before = db_path.stat().st_size if db_path.exists() else 0
    conn.execute("VACUUM")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    size_after = db_path.stat().st_size if db_path.exists() else 0
    saved = size_before - size_after

    print(f"Before: {size_before:,} bytes")
    print(f"After:  {size_after:,} bytes")
    print(f"Saved:  {saved:,} bytes")
    return 0


def cmd_db_backup(args: argparse.Namespace, container: CoreContainer) -> int:
    """Hot-backup the database via the online sqlite3.backup() API.

    Safe to run while writes are in flight; the backup is atomic
    (written to ``<path>.tmp`` then renamed). See
    ``infrastructure.persistence.backup`` for the full guarantees.
    """
    dest = Path(args.path)
    if dest.exists() and not args.force:
        print(f"Error: destination already exists: {dest}")
        print("Use --force to overwrite.")
        return 1

    src_conn = container.storage._conn  # noqa: SLF001
    backup_from_connection(src_conn, dest)
    backup_size = dest.stat().st_size
    print(f"Backup written: {dest} ({backup_size:,} bytes)")
    return 0


def cmd_db_stats(args: argparse.Namespace, container: CoreContainer) -> int:
    """Show memory/project counts plus pinned breakdown."""
    conn = container.storage._conn  # noqa: SLF001

    cur = conn.execute("SELECT COUNT(*) FROM projects")
    project_count = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM memory_items")
    memory_count = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM memory_items WHERE pinned = 1")
    pinned_count = cur.fetchone()[0]
    cur = conn.execute("SELECT COUNT(*) FROM memory_embeddings")
    embedding_count = cur.fetchone()[0]

    if args.json:
        payload = json_envelope(
            command="db.stats",
            ok=True,
            result={
                "projects": project_count,
                "memory_items": memory_count,
                "pinned": pinned_count,
                "embeddings": embedding_count,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Projects:      {project_count:>8,}")
    print(f"Memory items:  {memory_count:>8,}")
    print(f"  pinned:      {pinned_count:>8,}")
    print(f"Embeddings:    {embedding_count:>8,}")
    return 0
