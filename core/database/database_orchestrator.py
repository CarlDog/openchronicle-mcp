"""
DatabaseOrchestrator - Main coordination for all database operations.

This orchestrator provides a unified interface for all database operations,
replacing the monolithic database.py module with organized components.
"""

from typing import Optional, Dict, Any, List, Tuple
import sqlite3
import os
import asyncio
from pathlib import Path

from .connection import ConnectionManager
from .operations import DatabaseOperations  
from .fts import FTSManager
from .migration import MigrationManager
from .health_checker import DatabaseHealthChecker
from .shared import DatabaseConfig, DatabaseStats


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
            self._migration_manager = MigrationManager(self.connection_manager, self.operations)
        return self._migration_manager
    
    @property
    def health_checker(self) -> DatabaseHealthChecker:
        """Lazy-loaded health checker."""
        if self._health_checker is None:
            self._health_checker = DatabaseHealthChecker(self.connection_manager)
        return self._health_checker
    
    # Main Database Operations API
    def init_database(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Initialize database with required tables."""
        return self.operations.init_database(story_id, is_test)
    
    def get_connection(self, story_id: str, is_test: Optional[bool] = None) -> sqlite3.Connection:
        """Get database connection for story."""
        return self.connection_manager.get_connection(story_id, is_test)
    
    def execute_query(self, story_id: str, query: str, params: Optional[tuple] = None, 
                     is_test: Optional[bool] = None) -> List[sqlite3.Row]:
        """Execute SELECT query and return results."""
        return self.operations.execute_query(story_id, query, params, is_test)
    
    def execute_update(self, story_id: str, query: str, params: Optional[tuple] = None,
                      is_test: Optional[bool] = None) -> int:
        """Execute UPDATE/DELETE query and return affected rows."""
        return self.operations.execute_update(story_id, query, params, is_test)
    
    def execute_insert(self, story_id: str, query: str, params: Optional[tuple] = None,
                      is_test: Optional[bool] = None) -> int:
        """Execute INSERT query and return last row ID."""
        return self.operations.execute_insert(story_id, query, params, is_test)
    
    # FTS Operations API
    def has_fts5_support(self) -> bool:
        """Check if SQLite supports FTS5."""
        return self.fts_manager.has_fts5_support()
    
    def optimize_fts_index(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Optimize FTS indexes for better performance."""
        return self.fts_manager.optimize_fts_index(story_id, is_test)
    
    def rebuild_fts_index(self, story_id: str, is_test: Optional[bool] = None) -> bool:
        """Rebuild FTS indexes from scratch."""
        return self.fts_manager.rebuild_fts_index(story_id, is_test)
    
    def get_fts_stats(self, story_id: str, is_test: Optional[bool] = None) -> Dict[str, Any]:
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
    def get_database_stats(self, story_id: str, is_test: Optional[bool] = None) -> DatabaseStats:
        """Get comprehensive database statistics."""
        return self.operations.get_database_stats(story_id, is_test)
    
    def get_db_path(self, story_id: str, is_test: Optional[bool] = None) -> str:
        """Get database file path for story."""
        return self.connection_manager.get_db_path(story_id, is_test)
    
    def ensure_db_dir(self, story_id: str, is_test: Optional[bool] = None) -> None:
        """Ensure database directory exists."""
        self.connection_manager.ensure_db_dir(story_id, is_test)
    
    # Health Check Operations API
    async def startup_health_check(self) -> Dict[str, Any]:
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
    
    def get_all_databases(self) -> List[str]:
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


# Convenience instance for backward compatibility
database_orchestrator = DatabaseOrchestrator()

# Legacy function compatibility (for seamless transition)
def init_database(story_id: str, is_test: Optional[bool] = None) -> bool:
    """Legacy compatibility function."""
    return database_orchestrator.init_database(story_id, is_test)

def get_connection(story_id: str, is_test: Optional[bool] = None) -> sqlite3.Connection:
    """Legacy compatibility function.""" 
    return database_orchestrator.get_connection(story_id, is_test)

def execute_query(story_id: str, query: str, params: Optional[tuple] = None, 
                 is_test: Optional[bool] = None) -> List[sqlite3.Row]:
    """Legacy compatibility function."""
    return database_orchestrator.execute_query(story_id, query, params, is_test)

def execute_update(story_id: str, query: str, params: Optional[tuple] = None,
                  is_test: Optional[bool] = None) -> int:
    """Legacy compatibility function."""
    return database_orchestrator.execute_update(story_id, query, params, is_test)

def execute_insert(story_id: str, query: str, params: Optional[tuple] = None,
                  is_test: Optional[bool] = None) -> int:
    """Legacy compatibility function."""
    return database_orchestrator.execute_insert(story_id, query, params, is_test)

def has_fts5_support() -> bool:
    """Legacy compatibility function."""
    return database_orchestrator.has_fts5_support()

def optimize_fts_index(story_id: str, is_test: Optional[bool] = None) -> bool:
    """Legacy compatibility function."""
    return database_orchestrator.optimize_fts_index(story_id, is_test)

def rebuild_fts_index(story_id: str, is_test: Optional[bool] = None) -> bool:
    """Legacy compatibility function."""
    return database_orchestrator.rebuild_fts_index(story_id, is_test)

def get_fts_stats(story_id: str, is_test: Optional[bool] = None) -> Dict[str, Any]:
    """Legacy compatibility function."""
    return database_orchestrator.get_fts_stats(story_id, is_test)

def migrate_from_json(story_id: str) -> bool:
    """Legacy compatibility function."""
    return database_orchestrator.migrate_from_json(story_id)

def cleanup_json_files(story_id: str) -> bool:
    """Legacy compatibility function."""
    return database_orchestrator.cleanup_json_files(story_id)

def get_database_stats(story_id: str, is_test: Optional[bool] = None) -> Dict[str, Any]:
    """Legacy compatibility function."""
    stats = database_orchestrator.get_database_stats(story_id, is_test)
    return stats.to_dict() if hasattr(stats, 'to_dict') else stats

def get_db_path(story_id: str, is_test: Optional[bool] = None) -> str:
    """Legacy compatibility function."""
    return database_orchestrator.get_db_path(story_id, is_test)

def ensure_db_dir(story_id: str, is_test: Optional[bool] = None) -> None:
    """Legacy compatibility function."""
    return database_orchestrator.ensure_db_dir(story_id, is_test)

def check_fts_support() -> bool:
    """Legacy compatibility function."""
    return database_orchestrator.check_fts_support()

async def startup_health_check() -> Dict[str, Any]:
    """
    Legacy compatibility function for startup health check.
    
    Implementation as specified in Development Master Plan Phase 1 Week 4:
    ```python
    async def startup_health_check():
        for db_path in self.get_all_databases():
            async with aiosqlite.connect(db_path) as conn:
                result = await conn.execute("PRAGMA integrity_check")
                if result != "ok":
                    log_error(f"Database corruption detected: {db_path}")
    ```
    """
    return await database_orchestrator.startup_health_check()

def get_all_databases() -> List[str]:
    """Legacy compatibility function."""
    return database_orchestrator.get_all_databases()
