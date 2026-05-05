"""SQLite schema migrator.

Versioned forward-compatible migration runner. Migrations are plain `.sql`
files in `migrations/` named ``NNN_<slug>.sql`` where ``NNN`` is a
monotonic three-digit integer (``001``, ``002``, …). Each file is a
self-contained transactional unit — wrap multi-statement migrations in
``BEGIN/COMMIT`` only if you want to override the runner's outer
transaction. Most migrations should rely on the runner's own transaction.

The runner:
  1. Reads the current ``schema_version.version`` (0 if the table is
     absent — first-run case).
  2. Discovers migrations under ``migrations/`` and orders by file number.
  3. Skips any with ``number <= current``.
  4. Applies remaining migrations in order, each in its own transaction;
     on success, inserts a ``schema_version`` row.
  5. Re-running the migrator on an up-to-date DB is a no-op.

Migration semantics:
  - SQL is executed via ``executescript`` so multi-statement files work.
  - Idempotency: prefer ``CREATE TABLE IF NOT EXISTS`` etc. so re-applying
    against an already-migrated DB during recovery does not break.
  - Failures abort startup with a clear error pointing at the offending
    migration file.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from openchronicle.core.domain.errors.error_codes import CONFIG_ERROR
from openchronicle.core.domain.exceptions import ConfigError

_logger = logging.getLogger(__name__)

_MIGRATION_FILENAME_RE = re.compile(r"^(\d{3,})_[A-Za-z0-9_]+\.sql$")
_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _split_sql(script: str) -> list[str]:
    """Split a multi-statement SQL script on top-level semicolons.

    Strips line comments (``--``) and blank statements. Does not handle
    nested literals containing semicolons — migrations are simple DDL
    so this is fine in practice.
    """
    cleaned: list[str] = []
    for raw_line in script.splitlines():
        comment_idx = raw_line.find("--")
        if comment_idx >= 0:
            raw_line = raw_line[:comment_idx]
        cleaned.append(raw_line)
    body = "\n".join(cleaned)
    statements = [s.strip() for s in body.split(";")]
    return [s for s in statements if s]


def _read_current_version(conn: sqlite3.Connection) -> int:
    """Return the highest applied schema version, or 0 if untracked."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    cur = conn.execute("SELECT MAX(version) FROM schema_version")
    val = cur.fetchone()[0]
    return int(val) if val is not None else 0


def _discover_migrations(directory: Path) -> list[tuple[int, Path]]:
    """List `(version, path)` for every migration file in `directory`."""
    if not directory.is_dir():
        return []
    migrations: list[tuple[int, Path]] = []
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            continue
        match = _MIGRATION_FILENAME_RE.match(entry.name)
        if match is None:
            continue
        migrations.append((int(match.group(1)), entry))
    migrations.sort(key=lambda x: x[0])
    return migrations


def apply_pending(
    conn: sqlite3.Connection,
    *,
    migrations_dir: Path | None = None,
) -> list[int]:
    """Apply any unapplied migrations to ``conn`` in order.

    Returns the versions that were applied during this call (empty list
    if the DB was already up to date). Raises ``ConfigError`` on failure.
    """
    directory = migrations_dir or _MIGRATIONS_DIR
    current = _read_current_version(conn)
    pending = [(v, p) for v, p in _discover_migrations(directory) if v > current]

    applied: list[int] = []
    for version, path in pending:
        sql = path.read_text(encoding="utf-8")
        statements = _split_sql(sql)
        _logger.info("Applying migration %03d (%s)", version, path.name)
        savepoint = f"mig_{version}"
        conn.execute(f"SAVEPOINT {savepoint}")
        try:
            for stmt in statements:
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception as exc:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise ConfigError(
                f"Migration {path.name} failed: {exc}",
                code=CONFIG_ERROR,
            ) from exc
        applied.append(version)

    if applied:
        _logger.info(
            "Migrations applied: %s (now at version %d)",
            applied,
            applied[-1],
        )
    return applied


def current_version(conn: sqlite3.Connection) -> int:
    """Public read-only helper for inspecting the current schema version."""
    return _read_current_version(conn)
