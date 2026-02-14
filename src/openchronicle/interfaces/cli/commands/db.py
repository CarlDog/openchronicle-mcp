"""Database maintenance CLI commands: db info/vacuum/backup/stats."""

from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Callable
from pathlib import Path

from openchronicle.core.application.runtime.container import CoreContainer

from ._helpers import json_envelope, print_json

# Table names matching schema.py creation order.
_TABLE_NAMES = [
    "projects",
    "agents",
    "tasks",
    "events",
    "resources",
    "spans",
    "llm_usage",
    "conversations",
    "turns",
    "memory_items",
]


def cmd_db(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch to db subcommands."""
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
    """Show database information: file sizes, row counts, pragma values, integrity."""
    # Private access to connection and path is appropriate here — this is an
    # infrastructure CLI command inspecting the store's internal state.
    conn = container.storage._conn  # noqa: SLF001
    db_path = container.storage.db_path

    # File sizes
    db_size = db_path.stat().st_size if db_path.exists() else 0
    wal_path = Path(f"{db_path}-wal")
    wal_size = wal_path.stat().st_size if wal_path.exists() else 0

    # Row counts
    row_counts: dict[str, int] = {}
    for table in _TABLE_NAMES:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        row_counts[table] = cur.fetchone()[0]

    # Pragmas
    pragmas: dict[str, str] = {}
    for pragma in ("journal_mode", "foreign_keys", "busy_timeout", "synchronous"):
        cur = conn.execute(f"PRAGMA {pragma}")
        pragmas[pragma] = str(cur.fetchone()[0])

    # Integrity check
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
    """Hot-backup the database to a file using sqlite3.Connection.backup()."""
    dest = Path(args.path)
    if dest.exists() and not args.force:
        print(f"Error: destination already exists: {dest}")
        print("Use --force to overwrite.")
        return 1

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and args.force:
        dest.unlink()

    src_conn = container.storage._conn  # noqa: SLF001
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()

    backup_size = dest.stat().st_size
    print(f"Backup written: {dest} ({backup_size:,} bytes)")
    return 0


def cmd_db_stats(args: argparse.Namespace, container: CoreContainer) -> int:
    """Show global token usage statistics from llm_usage table."""
    conn = container.storage._conn  # noqa: SLF001

    # Global totals
    cur = conn.execute(
        "SELECT COUNT(*) as total_calls, "
        "COALESCE(SUM(input_tokens), 0) as input_tokens, "
        "COALESCE(SUM(output_tokens), 0) as output_tokens, "
        "COALESCE(SUM(total_tokens), 0) as total_tokens "
        "FROM llm_usage"
    )
    row = cur.fetchone()
    total_calls = row[0]
    input_tokens = row[1]
    output_tokens = row[2]
    total_tokens = row[3]

    # Breakdown by provider/model
    cur = conn.execute(
        "SELECT provider, model, COUNT(*) as calls, "
        "COALESCE(SUM(total_tokens), 0) as tokens "
        "FROM llm_usage GROUP BY provider, model ORDER BY tokens DESC"
    )
    breakdown = [{"provider": r[0], "model": r[1], "calls": r[2], "tokens": r[3]} for r in cur.fetchall()]

    if args.json:
        payload = json_envelope(
            command="db.stats",
            ok=True,
            result={
                "total_calls": total_calls,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "breakdown": breakdown,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print("Global LLM Usage:")
    print(f"  Total calls:    {total_calls:>10,}")
    print(f"  Input tokens:   {input_tokens:>10,}")
    print(f"  Output tokens:  {output_tokens:>10,}")
    print(f"  Total tokens:   {total_tokens:>10,}")

    if breakdown:
        print()
        print("By provider/model:")
        for entry in breakdown:
            print(
                f"  {entry['provider']}/{entry['model']:<30} {entry['calls']:>6} calls  {entry['tokens']:>10,} tokens"
            )

    return 0
