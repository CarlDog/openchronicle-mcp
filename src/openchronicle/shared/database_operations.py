"""
Shared database operations for OpenChronicle core modules.
Consolidates database patterns from 10+ modules to eliminate duplication.
"""

import sqlite3
import json
import os
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from contextlib import contextmanager


class DatabaseOperations:
    """Base class for all database operations."""

    def __init__(self, story_id: str, is_test: bool = None):
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
        return str(base_dir / "story.db")

    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def execute_update(self, query: str, params: tuple = None) -> bool:
        """Execute UPDATE/DELETE query."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                conn.commit()
                return True
        except sqlite3.Error:
            return False

    def execute_insert(self, query: str, params: tuple = None) -> Optional[int]:
        """Execute INSERT query and return row ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error:
            return None


class QueryBuilder:
    """Dynamic SQL query construction."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset builder state."""
        self._select = []
        self._from = ""
        self._where = []
        self._order_by = []
        self._limit = None
        self._params = []
        return self

    def select(self, columns: Union[str, List[str]]):
        """Add SELECT columns."""
        if isinstance(columns, str):
            self._select.append(columns)
        else:
            self._select.extend(columns)
        return self

    def from_table(self, table: str):
        """Set FROM table."""
        self._from = table
        return self

    def where(self, condition: str, *params):
        """Add WHERE condition."""
        self._where.append(condition)
        self._params.extend(params)
        return self

    def order_by(self, column: str, direction: str = "ASC"):
        """Add ORDER BY clause."""
        self._order_by.append(f"{column} {direction}")
        return self

    def limit(self, count: int):
        """Add LIMIT clause."""
        self._limit = count
        return self

    def build(self) -> tuple[str, tuple]:
        """Build the final query and parameters."""
        query_parts = []

        # SELECT
        if self._select:
            query_parts.append(f"SELECT {', '.join(self._select)}")

        # FROM
        if self._from:
            query_parts.append(f"FROM {self._from}")

        # WHERE
        if self._where:
            query_parts.append(f"WHERE {' AND '.join(self._where)}")

        # ORDER BY
        if self._order_by:
            query_parts.append(f"ORDER BY {', '.join(self._order_by)}")

        # LIMIT
        if self._limit:
            query_parts.append(f"LIMIT {self._limit}")

        return " ".join(query_parts), tuple(self._params)
