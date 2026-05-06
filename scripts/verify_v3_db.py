#!/usr/bin/env python3
"""Invariant checks for a v3-shaped SQLite DB.

Run after ``migrate_v2_to_v3.py`` (or anytime) to confirm the file is a
valid v3 store. Exits non-zero on any failure.

Checks:
  - ``schema_version`` exists and reports >= 1.
  - The expected tables exist and no v2-only tables remain.
  - ``PRAGMA integrity_check = ok``.
  - All ``memory_embeddings.memory_id`` values resolve in
    ``memory_items`` (FK invariant).
  - All ``memory_items.project_id`` values either are NULL or resolve in
    ``projects`` (FK invariant).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

_EXPECTED_TABLES = {
    "schema_version",
    "projects",
    "memory_items",
    "memory_embeddings",
}


def _orphan_sidecars(db_path: Path) -> list[Path]:
    """Return any pre-existing SQLite sidecar files (-wal, -shm) at the
    DB's path stem. Their presence on a freshly-placed DB indicates a
    process is currently holding it open OR (more dangerously) that
    leftover sidecars from a prior DB are about to corrupt the next
    open. The 2026-05-06 v3 cutover hit exactly this trap.
    """
    candidates = [
        db_path.with_name(db_path.name + "-wal"),
        db_path.with_name(db_path.name + "-shm"),
    ]
    return [p for p in candidates if p.exists()]


_FORBIDDEN_TABLES = {
    "agents",
    "tasks",
    "events",
    "spans",
    "resources",
    "llm_usage",
    "conversations",
    "turns",
    "scheduled_jobs",
    "mcp_tool_usage",
    "moe_usage",
    "assets",
    "asset_links",
    "webhooks",
    "webhook_deliveries",
}


def verify(db_path: Path) -> dict[str, object]:
    if not db_path.is_file():
        raise FileNotFoundError(f"DB not found: {db_path}")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    failures: list[str] = []
    warnings: list[str] = []

    # Orphan -wal/-shm sidecars at the path stem are not corruption per
    # se, but they're a strong signal of trouble: either a process holds
    # the DB open right now, or leftover sidecars from a prior DB are
    # about to corrupt the next open. Surface as a warning, not a
    # failure (the DB itself may still be valid).
    sidecars = _orphan_sidecars(db_path)
    if sidecars:
        warnings.append(
            f"orphan SQLite sidecars present at {db_path}: "
            f"{[str(p) for p in sidecars]} — these may corrupt the next "
            f"open if they belong to a different DB"
        )

    try:
        # Tables present
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        present = {r["name"] for r in rows}

        missing = _EXPECTED_TABLES - present
        if missing:
            failures.append(f"missing expected tables: {sorted(missing)}")

        leftover = _FORBIDDEN_TABLES & present
        if leftover:
            failures.append(f"v2 tables still present: {sorted(leftover)}")

        # Schema version
        if "schema_version" in present:
            version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            if version is None or version < 1:
                failures.append(f"schema_version is {version!r}; expected >= 1")
        else:
            version = None

        # Integrity
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            failures.append(f"integrity_check returned {integrity!r}")

        # FK invariants
        if "memory_embeddings" in present and "memory_items" in present:
            orphans = conn.execute(
                """SELECT COUNT(*) FROM memory_embeddings e
                   LEFT JOIN memory_items m ON m.id = e.memory_id
                   WHERE m.id IS NULL"""
            ).fetchone()[0]
            if orphans:
                failures.append(f"{orphans} memory_embeddings rows reference missing memory_items")

        if "memory_items" in present and "projects" in present:
            bad_proj = conn.execute(
                """SELECT COUNT(*) FROM memory_items m
                   LEFT JOIN projects p ON p.id = m.project_id
                   WHERE m.project_id IS NOT NULL AND p.id IS NULL"""
            ).fetchone()[0]
            if bad_proj:
                failures.append(f"{bad_proj} memory_items rows reference missing projects")

        counts = {}
        for tbl in ("projects", "memory_items", "memory_embeddings"):
            if tbl in present:
                counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    finally:
        conn.close()

    return {
        "ok": not failures,
        "schema_version": version if "schema_version" in present else None,
        "counts": counts,
        "failures": failures,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a v3-shaped SQLite DB.")
    parser.add_argument("db", help="Path to DB file")
    parser.add_argument("--json", action="store_true", help="Emit results as JSON")
    args = parser.parse_args(argv)

    try:
        report = verify(Path(args.db))
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        status = "OK" if report["ok"] else "FAIL"
        print(f"v3 verify: {status}")
        print(f"  schema_version: {report['schema_version']}")
        for table, count in report["counts"].items():
            print(f"  {table:<22} {count:>8}")
        for w in report.get("warnings", []):
            print(f"  ⚠ {w}")
        for f in report["failures"]:
            print(f"  ! {f}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
