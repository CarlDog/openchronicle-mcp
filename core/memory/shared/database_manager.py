"""
Database Manager for Memory Management System
====================

Provides database connectivity and operations for the memory management system.
This module acts as a bridge between the memory components and the underlying
database infrastructure.

Created as part of Phase 5B Memory Management Enhancement
"""

import sqlite3
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Database manager for memory management operations.
    
    Provides a simplified interface to database operations specifically
    for the memory management system components.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to database file. If None, uses default.
        """
        self.db_path = db_path or "storage/data/memory.db"
        self.connection = None
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure database file and directory exist."""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Create basic tables if they don't exist
        if not db_file.exists():
            self._create_memory_tables()
    
    def _create_memory_tables(self):
        """Create basic memory management tables."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Basic memory storage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT NOT NULL,
                    character_id TEXT,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance_score REAL DEFAULT 0.0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)
            
            # Character state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS character_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT NOT NULL,
                    character_id TEXT NOT NULL,
                    state_data TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(story_id, character_id)
                )
            """)
            
            # World state table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS world_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_id TEXT NOT NULL,
                    world_data TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(story_id)
                )
            """)
            
            conn.commit()
            logger.info("Memory management database tables created successfully")
            
        except Exception as e:
            logger.error(f"Error creating memory tables: {e}")
            raise
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get database connection.
        
        Returns:
            SQLite connection object
        """
        if self.connection is None or self._connection_closed():
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access
        
        return self.connection
    
    def _connection_closed(self) -> bool:
        """Check if connection is closed."""
        try:
            self.connection.execute("SELECT 1")
            return False
        except (sqlite3.ProgrammingError, AttributeError):
            return True
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            # Convert rows to dictionaries
            columns = [description[0] for description in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """
        Execute an INSERT/UPDATE/DELETE query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            
            return cursor.rowcount
            
        except Exception as e:
            logger.error(f"Error executing update: {e}")
            raise
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """
        Execute a batch of queries with different parameters.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
            
        Returns:
            Total number of affected rows
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            
            return cursor.rowcount
            
        except Exception as e:
            logger.error(f"Error executing batch: {e}")
            raise
    
    def get_memory_entries(self, story_id: str, character_id: Optional[str] = None,
                          memory_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve memory entries from database.
        
        Args:
            story_id: Story identifier
            character_id: Optional character filter
            memory_type: Optional memory type filter
            limit: Maximum number of entries to return
            
        Returns:
            List of memory entry dictionaries
        """
        query = "SELECT * FROM memory_entries WHERE story_id = ?"
        params = [story_id]
        
        if character_id:
            query += " AND character_id = ?"
            params.append(character_id)
        
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        return self.execute_query(query, tuple(params))
    
    def store_memory_entry(self, story_id: str, memory_type: str, content: str,
                          character_id: Optional[str] = None, importance_score: float = 0.0,
                          metadata: Optional[str] = None) -> int:
        """
        Store a memory entry in the database.
        
        Args:
            story_id: Story identifier
            memory_type: Type of memory (e.g., 'event', 'dialogue', 'description')
            content: Memory content
            character_id: Optional character identifier
            importance_score: Importance score (0.0 to 1.0)
            metadata: Optional metadata JSON string
            
        Returns:
            ID of inserted entry
        """
        query = """
            INSERT INTO memory_entries 
            (story_id, character_id, memory_type, content, importance_score, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        params = (story_id, character_id, memory_type, content, importance_score, metadata)
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        
        return cursor.lastrowid
    
    def get_character_state(self, story_id: str, character_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve character state from database.
        
        Args:
            story_id: Story identifier
            character_id: Character identifier
            
        Returns:
            Character state dictionary or None if not found
        """
        query = "SELECT * FROM character_states WHERE story_id = ? AND character_id = ?"
        results = self.execute_query(query, (story_id, character_id))
        
        return results[0] if results else None
    
    def store_character_state(self, story_id: str, character_id: str, state_data: str) -> None:
        """
        Store character state in database.
        
        Args:
            story_id: Story identifier
            character_id: Character identifier
            state_data: JSON-serialized character state
        """
        query = """
            INSERT OR REPLACE INTO character_states 
            (story_id, character_id, state_data)
            VALUES (?, ?, ?)
        """
        self.execute_update(query, (story_id, character_id, state_data))
    
    def get_world_state(self, story_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve world state from database.
        
        Args:
            story_id: Story identifier
            
        Returns:
            World state dictionary or None if not found
        """
        query = "SELECT * FROM world_states WHERE story_id = ?"
        results = self.execute_query(query, (story_id,))
        
        return results[0] if results else None
    
    def store_world_state(self, story_id: str, world_data: str) -> None:
        """
        Store world state in database.
        
        Args:
            story_id: Story identifier
            world_data: JSON-serialized world state
        """
        query = """
            INSERT OR REPLACE INTO world_states 
            (story_id, world_data)
            VALUES (?, ?)
        """
        self.execute_update(query, (story_id, world_data))
    
    def cleanup_old_memories(self, story_id: str, days_to_keep: int = 30) -> int:
        """
        Clean up old memory entries.
        
        Args:
            story_id: Story identifier
            days_to_keep: Number of days of memories to keep
            
        Returns:
            Number of entries deleted
        """
        query = """
            DELETE FROM memory_entries 
            WHERE story_id = ? 
            AND datetime(timestamp) < datetime('now', '-{} days')
        """.format(days_to_keep)
        
        return self.execute_update(query, (story_id,))
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function for getting a database manager instance
def get_database_manager(db_path: Optional[str] = None) -> DatabaseManager:
    """
    Get a database manager instance.
    
    Args:
        db_path: Optional path to database file
        
    Returns:
        DatabaseManager instance
    """
    return DatabaseManager(db_path)
