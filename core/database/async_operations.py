"""
Async core database operations.

Handles async CRUD operations, database initialization, and statistics.
"""

import aiosqlite
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC

from .async_connection import AsyncConnectionManager
from .shared import DatabaseStats


class AsyncDatabaseOperations:
    """Async core database operations and initialization."""
    
    def __init__(self, connection_manager: AsyncConnectionManager):
        self.connection_manager = connection_manager
    
    async def init_database(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Initialize the database with required tables."""
        try:
            async with self.connection_manager.get_connection(story_id, is_test) as conn:
                # Create scenes table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS scenes (
                        id TEXT PRIMARY KEY,
                        title TEXT,
                        content TEXT,
                        characters TEXT,
                        timestamp REAL,
                        token_usage INTEGER,
                        mood TEXT,
                        scene_data TEXT
                    )
                ''')
                
                # Create characters table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS characters (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        description TEXT,
                        personality TEXT,
                        relationships TEXT,
                        character_data TEXT,
                        created_at REAL,
                        updated_at REAL
                    )
                ''')
                
                # Create memory table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS memory (
                        story_id TEXT,
                        type TEXT,
                        key TEXT,
                        value TEXT,
                        updated_at TEXT,
                        PRIMARY KEY (story_id, type, key)
                    )
                ''')
                
                # Create memory snapshots table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS memory_snapshots (
                        story_id TEXT,
                        scene_id TEXT,
                        snapshot_data TEXT,
                        created_at TEXT,
                        PRIMARY KEY (story_id, scene_id)
                    )
                ''')
                
                # Create bookmarks table
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS bookmarks (
                        id TEXT PRIMARY KEY,
                        scene_id TEXT,
                        title TEXT,
                        description TEXT,
                        tags TEXT,
                        created_at REAL,
                        bookmark_data TEXT
                    )
                ''')
                
                # Create FTS5 virtual tables if supported
                if await self._has_fts5_support(conn):
                    # Scenes FTS
                    await conn.execute('''
                        CREATE VIRTUAL TABLE IF NOT EXISTS scenes_fts 
                        USING fts5(id, title, content, characters, tokenize='porter')
                    ''')
                    
                    # Characters FTS  
                    await conn.execute('''
                        CREATE VIRTUAL TABLE IF NOT EXISTS characters_fts
                        USING fts5(id, name, description, personality, tokenize='porter')
                    ''')
                    
                    # Memory FTS
                    await conn.execute('''
                        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                        USING fts5(id, content, characters, tokenize='porter')
                    ''')
                
                await conn.commit()
                return True
                
        except aiosqlite.Error as e:
            print(f"Database initialization error: {e}")
            return False
    
    async def _has_fts5_support(self, conn: aiosqlite.Connection) -> bool:
        """Check if FTS5 is available."""
        try:
            await conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts_test USING fts5(content)")
            await conn.execute("DROP TABLE IF EXISTS fts_test")
            return True
        except aiosqlite.Error:
            return False
    
    async def get_database_info(self, story_id: str, is_test: Optional[bool] = None) -> Dict[str, Any]:
        """Get database information and statistics."""
        try:
            async with self.connection_manager.get_connection(story_id, is_test) as conn:
                # Get table information
                cursor = await conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = [row[0] for row in await cursor.fetchall()]
                
                # Get database size
                cursor = await conn.execute("PRAGMA page_count")
                page_count_result = await cursor.fetchone()
                page_count = page_count_result[0] if page_count_result else 0
                cursor = await conn.execute("PRAGMA page_size")
                page_size_result = await cursor.fetchone()
                page_size = page_size_result[0] if page_size_result else 0
                db_size = page_count * page_size
                
                # Get table row counts
                table_counts = {}
                for table in tables:
                    cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count_result = await cursor.fetchone()
                    count = count_result[0] if count_result else 0
                    table_counts[table] = count
                
                return {
                    "tables": tables,
                    "size_bytes": db_size,
                    "table_counts": table_counts,
                    "has_fts5": await self._has_fts5_support(conn)
                }
                
        except aiosqlite.Error as e:
            return {"error": str(e)}
    
    async def execute_query(self, story_id: str, query: str, params: Optional[tuple] = None, 
                          is_test: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Execute SELECT query and return results."""
        async with self.connection_manager.get_connection(story_id, is_test) as conn:
            cursor = await conn.execute(query, params or ())
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def execute_update(self, story_id: str, query: str, params: Optional[tuple] = None, 
                           is_test: Optional[bool] = None) -> bool:
        """Execute UPDATE/DELETE query."""
        try:
            async with self.connection_manager.get_connection(story_id, is_test) as conn:
                await conn.execute(query, params or ())
                await conn.commit()
                return True
        except aiosqlite.Error:
            return False
    
    async def execute_insert(self, story_id: str, query: str, params: Optional[tuple] = None, 
                           is_test: Optional[bool] = None) -> Optional[int]:
        """Execute INSERT query and return row ID."""
        try:
            async with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = await conn.execute(query, params or ())
                await conn.commit()
                return cursor.lastrowid
        except aiosqlite.Error as e:
            return None
    
    async def execute_many(self, story_id: str, query: str, params_list: List[tuple], 
                         is_test: Optional[bool] = None) -> bool:
        """Execute multiple queries in a transaction."""
        try:
            async with self.connection_manager.get_connection(story_id, is_test) as conn:
                await conn.executemany(query, params_list)
                await conn.commit()
                return True
        except aiosqlite.Error as e:
            return False
    
    async def check_integrity(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Run PRAGMA integrity_check on database."""
        try:
            async with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = await conn.execute("PRAGMA integrity_check")
                result = await cursor.fetchone()
                return result[0] == "ok" if result else False
        except aiosqlite.Error:
            return False
    
    async def optimize_database(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Run VACUUM and ANALYZE on database."""
        try:
            async with self.connection_manager.get_connection(story_id, is_test) as conn:
                await conn.execute("VACUUM")
                await conn.execute("ANALYZE")
                return True
        except aiosqlite.Error:
            return False
