"""
Async database connection manager for OpenChronicle.
Handles async SQLite connections with proper resource management.
"""

import aiosqlite
import os
from typing import Optional
from pathlib import Path
from contextlib import asynccontextmanager

from .shared import DatabaseConfig


class AsyncConnectionManager:
    """Manages async database connections."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
    
    def _get_db_path(self, story_id: str, is_test: Optional[bool] = None) -> str:
        """Get database path for story."""
        if is_test is None:
            is_test = self._is_test_context()
        
        if is_test:
            base_dir = Path("storage/temp/test_data") / story_id
        else:
            base_dir = Path("storage/data") / story_id
        
        base_dir.mkdir(parents=True, exist_ok=True)
        return str(base_dir / "openchronicle.db")
    
    def _is_test_context(self) -> bool:
        """Detect if running in test context."""
        import sys
        return 'pytest' in sys.modules or os.getenv('TESTING') == '1'
    
    @asynccontextmanager
    async def get_connection(self, story_id: str, is_test: Optional[bool] = None):
        """Get async database connection with automatic cleanup."""
        db_path = self._get_db_path(story_id, is_test)
        
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        
        try:
            yield conn
        finally:
            await conn.close()
    
    async def check_connection(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Test database connection."""
        try:
            async with self.get_connection(story_id, is_test) as conn:
                await conn.execute("SELECT 1")
                return True
        except Exception:
            return False
