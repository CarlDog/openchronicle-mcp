"""
Async database operations for OpenChronicle core modules.
Provides async/await pattern for all database operations to improve performance.
"""

import asyncio
import os
from pathlib import Path
from typing import Any

import aiosqlite


class AsyncDatabaseOperations:
    """Base class for all async database operations."""

    def __init__(self, story_id: str, is_test: bool | None = None):
        self.story_id = story_id
        self.is_test = is_test if is_test is not None else self._is_test_context()
        self.db_path = self._get_db_path()

    def _is_test_context(self) -> bool:
        """Detect if running in test context."""
        import sys

        return "pytest" in sys.modules or os.getenv("TESTING") == "1"

    def _get_db_path(self) -> str:
        """Get database path based on story_id and test context."""
        if self.is_test:
            base_dir = Path("storage/temp/test_data") / self.story_id
        else:
            base_dir = Path("storage/data") / self.story_id

        base_dir.mkdir(parents=True, exist_ok=True)
        return str(base_dir / "openchronicle.db")

    async def get_connection(self) -> aiosqlite.Connection:
        """Get async database connection."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        return conn

    async def execute_query(self, query: str, params: tuple = None) -> list[dict[str, Any]]:
        """Execute SELECT query and return results."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params or ())
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def execute_update(self, query: str, params: tuple = None) -> bool:
        """Execute UPDATE/DELETE query."""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(query, params or ())
                await conn.commit()
                return True
        except aiosqlite.Error:
            return False

    async def execute_insert(self, query: str, params: tuple = None) -> int | None:
        """Execute INSERT query and return row ID."""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute(query, params or ())
                await conn.commit()
                return cursor.lastrowid
        except aiosqlite.Error:
            return None

    async def execute_many(self, query: str, params_list: list[tuple]) -> bool:
        """Execute multiple queries in a transaction."""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.executemany(query, params_list)
                await conn.commit()
                return True
        except aiosqlite.Error:
            return False

    async def safe_database_operation(self, operation_func, *args, **kwargs):
        """Execute database operation with error handling and retries."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiosqlite.connect(self.db_path) as conn:
                    conn.row_factory = aiosqlite.Row
                    async with conn:  # Transaction context
                        return await operation_func(conn, *args, **kwargs)
            except aiosqlite.Error:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff

    async def check_database_integrity(self) -> bool:
        """Check database integrity using PRAGMA integrity_check."""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute("PRAGMA integrity_check")
                result = await cursor.fetchone()
                return result[0] == "ok" if result else False
        except aiosqlite.Error:
            return False


class AsyncQueryBuilder:
    """Dynamic SQL query construction for async operations."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset builder state."""
        self._select_fields = []
        self._from_table = ""
        self._where_conditions = []
        self._order_by = []
        self._limit_value = None
        self._params = []

    def select(self, *fields):
        """Add SELECT fields."""
        self._select_fields.extend(fields)
        return self

    def from_table(self, table):
        """Set FROM table."""
        self._from_table = table
        return self

    def where(self, condition, *params):
        """Add WHERE condition."""
        self._where_conditions.append(condition)
        self._params.extend(params)
        return self

    def order_by(self, field, direction="ASC"):
        """Add ORDER BY clause."""
        self._order_by.append(f"{field} {direction}")
        return self

    def limit(self, count):
        """Add LIMIT clause."""
        self._limit_value = count
        return self

    def build(self) -> tuple:
        """Build the query and return (query, params)."""
        query_parts = []

        # SELECT
        if self._select_fields:
            query_parts.append(f"SELECT {', '.join(self._select_fields)}")
        else:
            query_parts.append("SELECT *")

        # FROM
        if self._from_table:
            query_parts.append(f"FROM {self._from_table}")

        # WHERE
        if self._where_conditions:
            query_parts.append(f"WHERE {' AND '.join(self._where_conditions)}")

        # ORDER BY
        if self._order_by:
            query_parts.append(f"ORDER BY {', '.join(self._order_by)}")

        # LIMIT
        if self._limit_value:
            query_parts.append(f"LIMIT {self._limit_value}")

        query = " ".join(query_parts)
        return query, tuple(self._params)


# No backwards-compatibility utility functions are provided.
# Use AsyncDatabaseOperations directly.
