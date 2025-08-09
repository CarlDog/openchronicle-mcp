"""
Database connection management.

Handles SQLite connection creation, path management, and context detection.
"""

import sqlite3
import os
from typing import Optional
from pathlib import Path

from .shared import DatabaseConfig


class ConnectionManager:
    """Manages database connections and file paths."""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
    
    def get_db_path(self, story_id: str, is_test: Optional[bool] = None) -> str:
        """Get the path to the SQLite database for a story."""
        base_path = self.config.get_base_path(is_test)
        return os.path.join(base_path, story_id, self.config.db_filename)
    
    def ensure_db_dir(self, story_id: str, is_test: Optional[bool] = None) -> None:
        """Ensure the database directory exists."""
        db_path = self.get_db_path(story_id, is_test)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def get_connection(self, story_id: str, is_test: Optional[bool] = None) -> sqlite3.Connection:
        """Get a database connection for the specified story."""
        self.ensure_db_dir(story_id, is_test)
        db_path = self.get_db_path(story_id, is_test)
        
        conn = sqlite3.connect(
            db_path,
            timeout=self.config.timeout,
            check_same_thread=self.config.check_same_thread
        )
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def database_exists(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Check if database file exists for the story."""
        db_path = self.get_db_path(story_id, is_test)
        return os.path.exists(db_path)
    
    def get_database_size(self, story_id: str, is_test: Optional[bool] = None) -> int:
        """Get database file size in bytes."""
        if not self.database_exists(story_id, is_test):
            return 0
        
        db_path = self.get_db_path(story_id, is_test)
        return os.path.getsize(db_path)
