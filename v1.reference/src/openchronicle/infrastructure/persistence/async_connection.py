"""
Async database connection manager for OpenChronicle.
Handles async SQLite connections with proper resource management.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from ...shared.logging_system import log_error
from .shared import DatabaseConfig


class AsyncConnectionManager:
    """Manages async database connections."""

    def __init__(self, config: DatabaseConfig):
        self.config = config

    def _get_db_path(self, story_id: str, is_test: bool | None = None) -> str:
        """Get database path for unit."""
        # Use shared DatabaseConfig to avoid hard-coded paths drifting from sync code
        base_path = self.config.get_base_path(is_test)
        base_dir = Path(base_path) / story_id
        base_dir.mkdir(parents=True, exist_ok=True)
        return str(base_dir / self.config.db_filename)

    def _is_test_context(self) -> bool:
        """Detect if running in test context."""
        import sys

        return "pytest" in sys.modules or os.getenv("TESTING") == "1"

    @asynccontextmanager
    async def get_connection(self, story_id: str, is_test: bool | None = None):
        """Get async database connection with automatic cleanup."""
        db_path = self._get_db_path(story_id, is_test)

        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row

        try:
            yield conn
        finally:
            await conn.close()

    async def check_connection(self, story_id: str, is_test: bool | None = None) -> bool:
        """Test database connection."""
        try:
            async with self.get_connection(story_id, is_test) as conn:
                await conn.execute("SELECT 1")
                return True
        except OSError as e:
            # Database file system error
            log_error(
                f"File system error in async connection check: {e}",
                context_tags=["db", "async", "check_connection"],
                story_id=story_id,
            )
            return False
        except Exception as e:
            # Log the exception for diagnostics but keep the boolean contract
            log_error(
                f"Async DB connection check failed: {e}",
                context_tags=["db", "async", "check_connection"],
                story_id=story_id,
            )
            return False
