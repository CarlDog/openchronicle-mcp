"""
Core database operations.

Handles basic CRUD operations, database initialization, and statistics.
"""

import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, UTC

from .connection import ConnectionManager
from .shared import DatabaseStats


class DatabaseOperations:
    """Core database operations and initialization."""

    def __init__(self, connection_manager: ConnectionManager):
        self.connection_manager = connection_manager

    def init_database(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Initialize the database with required tables."""
        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()

                # Create scenes table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS scenes (
                        scene_id TEXT PRIMARY KEY,
                        timestamp TEXT,
                        input TEXT,
                        output TEXT,
                        memory_snapshot TEXT,
                        flags TEXT,
                        canon_refs TEXT,
                        analysis TEXT,
                        scene_label TEXT,
                        structured_tags TEXT,
                        story_id TEXT
                    )
                """
                )

                # Create characters table
                cursor.execute(
                    """
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
                """
                )

                # Create memory table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory (
                        story_id TEXT,
                        type TEXT,
                        key TEXT,
                        value TEXT,
                        updated_at TEXT,
                        PRIMARY KEY (story_id, type, key)
                    )
                """
                )

                # Create bookmarks table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS bookmarks (
                        id TEXT PRIMARY KEY,
                        scene_id TEXT,
                        title TEXT,
                        description TEXT,
                        tags TEXT,
                        created_at REAL,
                        bookmark_data TEXT
                    )
                """
                )

                # Create rollback_points table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rollback_points (
                        rollback_id TEXT PRIMARY KEY,
                        scene_id TEXT,
                        timestamp TEXT,
                        description TEXT,
                        scene_data TEXT,
                        state_snapshot TEXT,
                        created_at TEXT,
                        last_used TEXT,
                        usage_count INTEGER DEFAULT 0
                    )
                """
                )

                # Create FTS5 virtual tables if supported
                if self._has_fts5_support():
                    # Scenes FTS
                    cursor.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS scenes_fts 
                        USING fts5(id, title, content, characters, tokenize='porter')
                    """
                    )

                    # Characters FTS
                    cursor.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS characters_fts
                        USING fts5(id, name, description, personality, tokenize='porter')
                    """
                    )

                    # Memory FTS
                    cursor.execute(
                        """
                        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                        USING fts5(id, content, characters, tokenize='porter')
                    """
                    )

                # Create indexes for better performance
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_scenes_timestamp ON scenes(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memory_type ON memory(type)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memory_importance ON memory(importance)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_bookmarks_scene_id ON bookmarks(scene_id)"
                )

                conn.commit()
                return True

        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

    def execute_query(
        self,
        story_id: str,
        query: str,
        params: Optional[tuple] = None,
        is_test: Optional[bool] = None,
    ) -> List[sqlite3.Row]:
        """Execute SELECT query and return results."""
        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"Query execution error: {e}")
            return []

    def execute_update(
        self,
        story_id: str,
        query: str,
        params: Optional[tuple] = None,
        is_test: Optional[bool] = None,
    ) -> int:
        """Execute UPDATE/DELETE query and return affected rows."""
        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            print(f"Update execution error: {e}")
            return 0

    def execute_insert(
        self,
        story_id: str,
        query: str,
        params: Optional[tuple] = None,
        is_test: Optional[bool] = None,
    ) -> int:
        """Execute INSERT query and return last row ID."""
        try:
            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                conn.commit()
                return cursor.lastrowid or 0
        except Exception as e:
            print(f"Insert execution error: {e}")
            return 0

    def get_database_stats(
        self, story_id: str, is_test: Optional[bool] = None
    ) -> DatabaseStats:
        """Get comprehensive database statistics."""
        stats = DatabaseStats()

        try:
            # Get database path and size
            stats.database_path = self.connection_manager.get_db_path(story_id, is_test)

            if not self.connection_manager.database_exists(story_id, is_test):
                return stats

            stats.total_size_bytes = self.connection_manager.get_database_size(
                story_id, is_test
            )
            stats.total_size_mb = round(stats.total_size_bytes / (1024 * 1024), 2)

            # Get file modification time
            try:
                mtime = os.path.getmtime(stats.database_path)
                stats.last_modified = datetime.fromtimestamp(mtime, UTC).isoformat()
            except (OSError, ValueError):
                stats.last_modified = None

            with self.connection_manager.get_connection(story_id, is_test) as conn:
                cursor = conn.cursor()

                # Count records in each table
                tables_queries = [
                    ("scenes_count", "SELECT COUNT(*) FROM scenes"),
                    ("characters_count", "SELECT COUNT(*) FROM characters"),
                    ("memory_entries_count", "SELECT COUNT(*) FROM memory"),
                    ("bookmarks_count", "SELECT COUNT(*) FROM bookmarks"),
                ]

                for attr_name, query in tables_queries:
                    try:
                        cursor.execute(query)
                        count = cursor.fetchone()[0]
                        setattr(stats, attr_name, count)
                    except sqlite3.OperationalError:
                        # Table doesn't exist yet
                        setattr(stats, attr_name, 0)

                # Count total tables
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """
                )
                stats.total_tables = cursor.fetchone()[0]

                # Count indexes
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """
                )
                stats.index_count = cursor.fetchone()[0]

                # FTS statistics
                stats.fts_enabled = self._has_fts5_support()
                if stats.fts_enabled:
                    # Count FTS tables
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM sqlite_master 
                        WHERE type='table' AND name LIKE '%_fts'
                    """
                    )
                    stats.fts_indexes_count = cursor.fetchone()[0]

                    # Total FTS documents (approximate)
                    fts_tables = ["scenes_fts", "characters_fts", "memory_fts"]
                    total_docs = 0
                    for table in fts_tables:
                        try:
                            cursor.execute(f"SELECT COUNT(*) FROM {table}")
                            total_docs += cursor.fetchone()[0]
                        except sqlite3.OperationalError:
                            # FTS table doesn't exist
                            continue
                    stats.fts_total_docs = total_docs

        except Exception as e:
            print(f"Error getting database stats: {e}")

        return stats

    def _has_fts5_support(self) -> bool:
        """Check if SQLite supports FTS5."""
        try:
            with sqlite3.connect(":memory:") as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
                cursor.execute("DROP TABLE test_fts")
                return True
        except sqlite3.OperationalError:
            return False
