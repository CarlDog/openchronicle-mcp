"""
DatabaseOrchestrator - Main coordination for all database operations.

This orchestrator provides a unified interface for all database operations,
replacing the monolithic database.py module with organized components.
"""

import sqlite3
from typing import Any

from .connection import ConnectionManager
from .fts import FTSManager
from .health_checker import DatabaseHealthChecker
from .migration import MigrationManager
from .operations import DatabaseOperations
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

    def __init__(self):
        self._connection_manager = None
        self._operations = None
        self._fts_manager = None
        self._migration_manager = None
        self._health_checker = None
        self._config = DatabaseConfig()

    @property
    def connection_manager(self) -> ConnectionManager:
        """Lazy-loaded connection manager."""
        if self._connection_manager is None:
            self._connection_manager = ConnectionManager(self._config)
        return self._connection_manager

    @property
    def operations(self) -> DatabaseOperations:
        """Lazy-loaded database operations."""
        if self._operations is None:
            self._operations = DatabaseOperations(self.connection_manager)
        return self._operations

    @property
    def fts_manager(self) -> FTSManager:
        """Lazy-loaded FTS manager."""
        if self._fts_manager is None:
            self._fts_manager = FTSManager(self.connection_manager)
        return self._fts_manager

    @property
    def migration_manager(self) -> MigrationManager:
        """Lazy-loaded migration manager."""
        if self._migration_manager is None:
            self._migration_manager = MigrationManager(
                self.connection_manager, self.operations
            )
        return self._migration_manager

    @property
    def health_checker(self) -> DatabaseHealthChecker:
        """Lazy-loaded health checker."""
        if self._health_checker is None:
            self._health_checker = DatabaseHealthChecker(self.connection_manager)
        return self._health_checker

    # Main Database Operations API
    def init_database(self, story_id: str, is_test: bool | None = None) -> bool:
        """Initialize database with required tables."""
        return self.operations.init_database(story_id, is_test)

    def get_connection(
        self, story_id: str, is_test: bool | None = None
    ) -> sqlite3.Connection:
        """Get database connection for story."""
        return self.connection_manager.get_connection(story_id, is_test)

    def execute_query(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> list[sqlite3.Row]:
        """Execute SELECT query and return results."""
        return self.operations.execute_query(story_id, query, params, is_test)

    def execute_update(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> int:
        """Execute UPDATE/DELETE query and return affected rows."""
        return self.operations.execute_update(story_id, query, params, is_test)

    def execute_insert(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> int:
        """Execute INSERT query and return last row ID."""
        return self.operations.execute_insert(story_id, query, params, is_test)

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

    def get_fts_stats(
        self, story_id: str, is_test: bool | None = None
    ) -> dict[str, Any]:
        """Get FTS index statistics."""
        return self.fts_manager.get_fts_stats(story_id, is_test)

    # Migration Operations API
    def migrate_from_json(self, story_id: str) -> bool:
        """Migrate data from JSON files to database."""
        return self.migration_manager.migrate_from_json(story_id)

    def cleanup_json_files(self, story_id: str) -> bool:
        """Clean up JSON files after successful migration."""
        return self.migration_manager.cleanup_json_files(story_id)

    # Statistics and Utilities API
    def get_database_stats(
        self, story_id: str, is_test: bool | None = None
    ) -> DatabaseStats:
        """Get comprehensive database statistics."""
        return self.operations.get_database_stats(story_id, is_test)

    def get_db_path(self, story_id: str, is_test: bool | None = None) -> str:
        """Get database file path for story."""
        return self.connection_manager.get_db_path(story_id, is_test)

    def ensure_db_dir(self, story_id: str, is_test: bool | None = None) -> None:
        """Ensure database directory exists."""
        self.connection_manager.ensure_db_dir(story_id, is_test)

    # Health Check Operations API
    async def startup_health_check(self) -> dict[str, Any]:
        """
        Run comprehensive startup health check on all databases.

        Implements Week 4 startup health check requirements:
        - Run PRAGMA integrity_check on all databases
        - Early detection of database corruption
        - Connection validation and schema checks

        Returns:
            Dict containing comprehensive health report
        """
        return await self.health_checker.startup_health_check()

    def get_all_databases(self) -> list[str]:
        """
        Get paths to all databases for health checks.

        Returns:
            List of database file paths
        """
        return self.health_checker.get_all_databases()

    # Legacy compatibility methods (maintaining function signatures for seamless transition)
    def check_fts_support(self) -> bool:
        """Legacy alias for has_fts5_support."""
        return self.has_fts5_support()


# Convenience instance for global use
database_orchestrator = DatabaseOrchestrator()


# Convenience function for module-level health check access
async def startup_health_check() -> dict[str, Any]:
    """
    Run the startup health check using the global orchestrator instance.

    Provided for compatibility with call sites that import a module-level
    function rather than accessing the method on DatabaseOrchestrator.
    """
    return await database_orchestrator.startup_health_check()
