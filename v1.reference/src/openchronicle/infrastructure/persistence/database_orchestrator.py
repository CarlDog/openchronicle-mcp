"""
DatabaseOrchestrator - Main coordination for all database operations.

Provides a unified interface without importing plugin implementations. Where
domain-specific behavior is needed (e.g., table schemas), plugins should
register operations in the registry and the orchestrator will use them if present.
"""

import sqlite3
from typing import Any

from .connection import ConnectionManager
from .fts import FTSManager
from .health_checker import DatabaseHealthChecker
from .operations import get_operations_registry
from .shared import DatabaseConfig
from .shared import DatabaseStats


class DatabaseOrchestrator:
    """
    Main orchestrator for all database operations in OpenChronicle.

    Provides unified access to:
    - Connection management
    - Query operations (SELECT, INSERT, UPDATE)
    - Full-text search (FTS5) operations
    - Data migration utilities
    - Database statistics and optimization

    This replaces the monolithic database.py with organized components.
    """

    def __init__(self) -> None:
        self._connection_manager: ConnectionManager | None = None
        self._operations = None  # Lazy plugin-provided operations
        self._fts_manager: FTSManager | None = None
        self._health_checker: DatabaseHealthChecker | None = None
        self._config = DatabaseConfig()

    @property
    def connection_manager(self) -> ConnectionManager:
        """Lazy-loaded connection manager."""
        if self._connection_manager is None:
            self._connection_manager = ConnectionManager(self._config)
        return self._connection_manager

    def _get_operations(self):
        """Get plugin-registered operations if available."""
        if self._operations is not None:
            return self._operations
        registry = get_operations_registry()
        # Default domain key; plugins should register under their domain
        self._operations = registry.get_operations("storytelling")
        return self._operations

    @property
    def fts_manager(self) -> FTSManager:
        """Lazy-loaded FTS manager."""
        if self._fts_manager is None:
            self._fts_manager = FTSManager(self.connection_manager)
        return self._fts_manager

    def migrate_from_json(self, story_id: str) -> bool:  # noqa: ARG002
        """DEPRECATED: Migrate data using backward compatibility function."""
        raise ImportError("migrate_from_json is no longer available in core. Use plugin-provided migration managers.")

    @property
    def health_checker(self) -> DatabaseHealthChecker:
        """Lazy-loaded health checker."""
        if self._health_checker is None:
            self._health_checker = DatabaseHealthChecker(self.connection_manager)
        return self._health_checker

    # Main Database Operations API
    def init_database(self, story_id: str, is_test: bool | None = None) -> bool:
        """Initialize database with required tables."""
        ops = self._get_operations()
        if ops is not None:
            return ops.init_database(story_id, is_test)
        # Fallback: ensure DB exists without domain tables
        self.connection_manager.ensure_db_dir(story_id, is_test)
        with self.connection_manager.get_connection(story_id, is_test) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
        return True

    async def initialize_story_database(self, story_id: str, is_test: bool | None = None) -> bool:
        """Async wrapper for init_database - used by workflow tests."""
        return self.init_database(story_id, is_test)

    def get_connection(self, story_id: str, is_test: bool | None = None) -> sqlite3.Connection:
        """Get database connection for a unit."""
        return self.connection_manager.get_connection(story_id, is_test)

    def execute_query(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> list[sqlite3.Row]:
        """Execute SELECT query and return results."""
        with self.connection_manager.get_connection(story_id, is_test) as conn:
            cur = conn.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            return cur.fetchall()

    def execute_update(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> int:
        """Execute UPDATE/DELETE query and return affected rows."""
        with self.connection_manager.get_connection(story_id, is_test) as conn:
            cur = conn.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            conn.commit()
            return cur.rowcount

    def execute_insert(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> int:
        """Execute INSERT query and return last row ID."""
        with self.connection_manager.get_connection(story_id, is_test) as conn:
            cur = conn.cursor()
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            conn.commit()
            try:
                return cur.lastrowid  # type: ignore[attr-defined]
            except Exception:
                return 0

    # FTS Operations API
    def has_fts5_support(self) -> bool:
        """Check if SQLite supports FTS5."""
        return self.fts_manager.has_fts5_support()

    def optimize_fts_index(self, story_id: str, is_test: bool | None = None) -> bool:
        """Optimize FTS indexes for better performance."""
        return self.fts_manager.optimize_fts_index(story_id, is_test)

    def rebuild_fts_index(self, story_id: str, is_test: bool | None = None) -> bool:
        """Rebuild FTS indexes from scratch."""
        return self.fts_manager.rebuild_fts_index(story_id, is_test)

    def get_fts_stats(self, story_id: str, is_test: bool | None = None) -> dict[str, Any]:
        """Get FTS index statistics."""
        return self.fts_manager.get_fts_stats(story_id, is_test)

    # Migration Operations API - DEPRECATED
    # Migration functionality moved to domain-specific plugins

    def cleanup_json_files(self, story_id: str) -> bool:  # noqa: ARG002
        """Deprecated: JSON cleanup handled by plugins now."""
        import warnings

        warnings.warn(
            "cleanup_json_files is deprecated. JSON cleanup handled by domain-specific plugins.",
            DeprecationWarning,
            stacklevel=2,
        )
        return True

    # Statistics and Utilities API
    def get_database_stats(self, story_id: str, is_test: bool | None = None) -> DatabaseStats:
        """Get comprehensive database statistics."""
        # Basic stats without domain knowledge; plugins can override via ops
        ops = self._get_operations()
        if ops and hasattr(ops, "get_database_stats"):
            return ops.get_database_stats(story_id, is_test)  # type: ignore[no-any-return]

        with self.connection_manager.get_connection(story_id, is_test) as conn:
            cur = conn.cursor()
            tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()
            stats = DatabaseStats()
            stats.total_tables = len(tables)
            stats.database_path = self.connection_manager.get_db_path(story_id, is_test)
            return stats

    def get_db_path(self, story_id: str, is_test: bool | None = None) -> str:
        """Get database file path for a unit."""
        return self.connection_manager.get_db_path(story_id, is_test)

    def ensure_db_dir(self, story_id: str, is_test: bool | None = None) -> None:
        """Ensure database directory exists."""
        self.connection_manager.ensure_db_dir(story_id, is_test)

    # Health Check Operations API
    async def startup_health_check(self) -> dict[str, Any]:
        """Run comprehensive startup health check on all databases."""
        return await self.health_checker.startup_health_check()

    def get_all_databases(self) -> list[str]:
        """Get paths to all databases for health checks."""
        return self.health_checker.get_all_databases()


# Convenience instance for global use
database_orchestrator = DatabaseOrchestrator()


# Module-level health check retained as public API convenience
async def startup_health_check() -> dict[str, Any]:
    return await database_orchestrator.startup_health_check()
