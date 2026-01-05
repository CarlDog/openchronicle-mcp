"""
AsyncDatabaseOrchestrator - Async coordination for all database operations.

This orchestrator provides a unified async interface for all database operations,
improving performance through non-blocking database access.
"""

from typing import Any

from .async_connection import AsyncConnectionManager
from .async_operations import AsyncDatabaseOperations
from .fts import FTSManager  # Keep sync FTS for now, migrate later
from .migration import MigrationManager  # Keep sync migrations for now
from .shared import DatabaseConfig


class AsyncDatabaseOrchestrator:
    """
    Async orchestrator for all database operations in OpenChronicle.

    Provides unified async access to:
    - Connection management (async)
    - Query operations (async SELECT, INSERT, UPDATE)
    - Full-text search (FTS5) operations
    - Data migration utilities
    - Database statistics and optimization

    This provides async version of DatabaseOrchestrator for performance.
    """

    def __init__(self):
        self._connection_manager = None
        self._operations = None
        self._fts_manager = None
        self._migration_manager = None
        self._config = DatabaseConfig()

    @property
    def connection_manager(self) -> AsyncConnectionManager:
        """Lazy-loaded async connection manager."""
        if self._connection_manager is None:
            self._connection_manager = AsyncConnectionManager(self._config)
        return self._connection_manager

    @property
    def operations(self) -> AsyncDatabaseOperations:
        """Lazy-loaded async database operations."""
        if self._operations is None:
            self._operations = AsyncDatabaseOperations(self.connection_manager)
        return self._operations

    @property
    def fts_manager(self) -> FTSManager:
        """Lazy-loaded FTS manager (sync for now)."""
        if self._fts_manager is None:
            # TODO: Create async FTS manager in future iteration
            from .connection import ConnectionManager

            sync_conn_manager = ConnectionManager(self._config)
            self._fts_manager = FTSManager(sync_conn_manager)
        return self._fts_manager

    @property
    def migration_manager(self) -> MigrationManager:
        """Lazy-loaded migration manager (sync for now)."""
        if self._migration_manager is None:
            # TODO: Create async migration manager in future iteration
            from .connection import ConnectionManager

            sync_conn_manager = ConnectionManager(self._config)
            self._migration_manager = MigrationManager(sync_conn_manager)
        return self._migration_manager

    # Async database operations
    async def init_database(self, story_id: str, is_test: bool | None = None) -> bool:
        """Initialize database with all required tables."""
        return await self.operations.init_database(story_id, is_test)

    async def execute_query(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Execute SELECT query and return results."""
        return await self.operations.execute_query(story_id, query, params, is_test)

    async def execute_update(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> bool:
        """Execute UPDATE/DELETE query."""
        return await self.operations.execute_update(story_id, query, params, is_test)

    async def execute_insert(
        self,
        story_id: str,
        query: str,
        params: tuple | None = None,
        is_test: bool | None = None,
    ) -> int | None:
        """Execute INSERT query and return row ID."""
        return await self.operations.execute_insert(story_id, query, params, is_test)

    async def execute_many(
        self,
        story_id: str,
        query: str,
        params_list: list[tuple],
        is_test: bool | None = None,
    ) -> bool:
        """Execute multiple queries in a transaction."""
        return await self.operations.execute_many(story_id, query, params_list, is_test)

    # Database management
    async def get_database_info(self, story_id: str, is_test: bool | None = None) -> dict[str, Any]:
        """Get database information and statistics."""
        return await self.operations.get_database_info(story_id, is_test)

    async def check_integrity(self, story_id: str, is_test: bool | None = None) -> bool:
        """Run integrity check on database."""
        return await self.operations.check_integrity(story_id, is_test)

    async def optimize_database(self, story_id: str, is_test: bool | None = None) -> bool:
        """Optimize database performance."""
        return await self.operations.optimize_database(story_id, is_test)

    async def check_connection(self, story_id: str, is_test: bool | None = None) -> bool:
        """Test database connection."""
        return await self.connection_manager.check_connection(story_id, is_test)

    # Startup health checks
    async def startup_health_check(self, story_ids: list[str]) -> dict[str, bool]:
        """Run health checks on multiple databases."""
        results = {}
        for story_id in story_ids:
            try:
                connection_ok = await self.check_connection(story_id)
                integrity_ok = await self.check_integrity(story_id) if connection_ok else False
                results[story_id] = connection_ok and integrity_ok
            except Exception as e:
                print(f"Health check failed for {story_id}: {e}")
                results[story_id] = False
        return results

    # No compatibility or global helpers are exposed. Use the async orchestrator directly.
