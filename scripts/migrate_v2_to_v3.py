#!/usr/bin/env python3
"""One-shot migration from v2 schema to v3 schema.

Reads a v2 SQLite DB read-only, writes a fresh v3-shaped DB next to it
with only the surviving tables (projects, memory_items, memory_embeddings),
runs the v3 migration framework to register schema_version=1, runs
``PRAGMA integrity_check``, and ``VACUUM``s the result.

Usage:
    python scripts/migrate_v2_to_v3.py SRC_V2.db DEST_V3.db [--force]

The destination must not exist unless ``--force`` is passed. The source is
opened read-only and never modified.

What's preserved:
- ``projects`` rows (id, name, metadata, created_at)
- ``memory_items`` rows minus the ``conversation_id`` column (Q1 locked)
- ``memory_embeddings`` rows (FK target ``memory_id`` continues to resolve)

What's dropped:
- agents, tasks, events, spans, llm_usage, conversations, turns,
  scheduled_jobs, mcp_tool_usage, moe_usage, assets, asset_links,
  webhooks, webhook_deliveries, resources, turn_search FTS5 — all of
  the v2 subsystems archived on ``archive/openchronicle.v2``.

Companion: ``scripts/verify_v3_db.py`` runs invariant checks on the
output.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _read_v2_projects(src: sqlite3.Connection) -> list[tuple]:
    return src.execute(
        "SELECT id, name, metadata, created_at FROM projects"
    ).fetchall()


def _read_v2_memory_items(src: sqlite3.Connection) -> list[tuple]:
    columns = [r[1] for r in src.execute("PRAGMA table_info(memory_items)").fetchall()]
    has_updated_at = "updated_at" in columns
    select_cols = "id, content, tags, created_at, pinned, project_id, source"
    if has_updated_at:
        select_cols += ", updated_at"
    rows = src.execute(f"SELECT {select_cols} FROM memory_items").fetchall()
    if has_updated_at:
        return rows
    # Pad with None for updated_at so downstream insert is uniform.
    return [(*r, None) for r in rows]


def _read_v2_embeddings(src: sqlite3.Connection) -> list[tuple]:
    return src.execute(
        "SELECT memory_id, embedding, model, dimensions, generated_at FROM memory_embeddings"
    ).fetchall()


def _build_v3_schema(dst: sqlite3.Connection) -> None:
    """Apply the v3 migration framework to the empty destination."""
    # The migrator lives in the package; import it here so the script
    # is self-contained when invoked from a checkout.
    from openchronicle.core.infrastructure.persistence import migrator

    migrator.apply_pending(dst)


def migrate(src_path: Path, dest_path: Path, *, force: bool = False) -> dict[str, int]:
    if not src_path.is_file():
        raise FileNotFoundError(f"Source DB not found: {src_path}")
    if dest_path.exists():
        if not force:
            raise FileExistsError(
                f"Destination exists: {dest_path}. Use --force to overwrite."
            )
        dest_path.unlink()

    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(str(dest_path), isolation_level=None)

    try:
        _build_v3_schema(dst)

        projects = _read_v2_projects(src)
        memory_items = _read_v2_memory_items(src)
        embeddings = _read_v2_embeddings(src)

        dst.execute("BEGIN")
        try:
            dst.executemany(
                "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
                projects,
            )
            dst.executemany(
                "INSERT INTO memory_items "
                "(id, content, tags, created_at, pinned, project_id, source, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                memory_items,
            )
            dst.executemany(
                "INSERT INTO memory_embeddings "
                "(memory_id, embedding, model, dimensions, generated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                embeddings,
            )
            dst.execute("COMMIT")
        except Exception:
            dst.execute("ROLLBACK")
            raise

        # Integrity check
        result = dst.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"integrity_check failed: {result}")

        dst.execute("VACUUM")
    finally:
        src.close()
        dst.close()

    return {
        "projects": len(projects),
        "memory_items": len(memory_items),
        "embeddings": len(embeddings),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Migrate v2 SQLite DB to v3 shape.")
    parser.add_argument("src", help="Source v2 DB path")
    parser.add_argument("dest", help="Destination v3 DB path")
    parser.add_argument("--force", action="store_true", help="Overwrite dest if exists")
    parser.add_argument("--json", action="store_true", help="Emit summary as JSON")
    args = parser.parse_args(argv)

    try:
        summary = migrate(Path(args.src), Path(args.dest), force=args.force)
    except (FileNotFoundError, FileExistsError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"ok": True, **summary}))
    else:
        print(f"Migrated {Path(args.src).name} -> {Path(args.dest).name}")
        for key, value in summary.items():
            print(f"  {key:<20} {value:>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
