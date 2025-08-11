"""
In-memory SQLite persistence adapter for tests and simple runs.

Implements IPersistencePort without importing infrastructure, keeping
hexagonal boundaries intact. Uses one SQLite :memory: database per story_id.
"""

from __future__ import annotations

import sqlite3
from threading import RLock
from typing import Any, Optional

from .persistence_port import IPersistencePort


class InMemorySqlitePersistence(IPersistencePort):
    """Simple in-memory SQLite implementation of IPersistencePort."""

    def __init__(self) -> None:
        # Use class-level registries so multiple instances within the same
        # process share the same per-story in-memory databases. This ensures
        # CLI subcommands and tests that create new instances still see the
        # same data for a given story_id.
        if not hasattr(self.__class__, "_connections_global"):
            self.__class__._connections_global = {}
        if not hasattr(self.__class__, "_lock_global"):
            self.__class__._lock_global = RLock()

        self._connections: dict[str, sqlite3.Connection] = self.__class__._connections_global  # type: ignore[attr-defined]
        self._lock = self.__class__._lock_global  # type: ignore[attr-defined]

    def _get_conn(self, story_id: str) -> sqlite3.Connection:
        with self._lock:
            conn = self._connections.get(story_id)
            if conn is None:
                conn = sqlite3.connect(":memory:")
                conn.row_factory = sqlite3.Row
                self._connections[story_id] = conn
            return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scenes (
                scene_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                input TEXT NOT NULL,
                output TEXT NOT NULL,
                memory_snapshot TEXT,
                flags TEXT,
                canon_refs TEXT,
                analysis TEXT,
                scene_label TEXT,
                structured_tags TEXT,
                story_id TEXT NOT NULL
            )
            """
        )
        # Simple navigation history for stats/tracking (denormalized for tests)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS navigation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_scene TEXT NOT NULL,
                to_scene TEXT NOT NULL,
                navigation_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                story_id TEXT NOT NULL
            )
            """
        )
        # Rollback points storage for timeline state management
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rollback_points (
                rollback_id TEXT PRIMARY KEY,
                scene_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                description TEXT,
                scene_data TEXT,
                state_snapshot TEXT,
                last_used TEXT,
                usage_count INTEGER,
                story_id TEXT NOT NULL
            )
            """
        )
        # Optional bookmarks table for timeline bookmarks
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                story_id TEXT NOT NULL,
                bookmark_id TEXT,
                scene_id TEXT,
                timestamp TEXT,
                description TEXT,
                bookmark_data TEXT
            )
            """
        )
        conn.commit()

    # IPersistencePort implementation
    def execute_query(
        self, story_id: str, query: str, params: Optional[list[Any] | tuple[Any, ...]] = None
    ) -> list[dict[str, Any]]:
        conn = self._get_conn(story_id)
        self._ensure_schema(conn)
        cur = conn.execute(query, params or [])
        rows = cur.fetchall()
        # Convert sqlite3.Row to dict
        return [dict(r) for r in rows]

    def execute_update(
        self, story_id: str, query: str, params: Optional[list[Any] | tuple[Any, ...]] = None
    ) -> bool:
        conn = self._get_conn(story_id)
        self._ensure_schema(conn)
        cur = conn.execute(query, params or [])
        conn.commit()
        # SQLite returns -1 for rowcount when not applicable; treat as success
        return cur.rowcount is None or cur.rowcount >= -1

    def init_database(self, story_id: str) -> bool:
        conn = self._get_conn(story_id)
        self._ensure_schema(conn)
        return True

    def backup_database(self, story_id: str, backup_name: str) -> bool:
        # No-op for in-memory DB
        return True

    def restore_database(self, story_id: str, backup_name: str) -> bool:
        # No-op for in-memory DB
        return True
