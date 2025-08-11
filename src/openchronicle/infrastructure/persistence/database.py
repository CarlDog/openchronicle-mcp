"""
Database operations for OpenChronicle.

This module provides a clean interface to the modular database system.
The original monolithic database.py (479 lines) has been replaced with
an organized modular architecture using DatabaseOrchestrator.

Direct replacement approach (no backwards compatibility needed):
- All original functions maintained through DatabaseOrchestrator
- Improved organization with specialized components
- Enhanced error handling and performance optimization
"""

# Import the orchestrator and expose all functionality
from .database_orchestrator import DatabaseOrchestrator

# Create global orchestrator instance
_orchestrator = DatabaseOrchestrator()


# Core database operations (maintaining original function signatures)
def init_database(story_id: str, is_test=None):
    """Initialize the database with required tables."""
    return _orchestrator.init_database(story_id, is_test)


def get_connection(story_id: str, is_test=None):
    """Get database connection for story."""
    return _orchestrator.get_connection(story_id, is_test)


def execute_query(story_id: str, query: str, params=None, is_test=None):
    """Execute SELECT query and return results."""
    return _orchestrator.execute_query(story_id, query, params, is_test)


def execute_update(story_id: str, query: str, params=None, is_test=None):
    """Execute UPDATE/DELETE query and return affected rows."""
    return _orchestrator.execute_update(story_id, query, params, is_test)


def execute_insert(story_id: str, query: str, params=None, is_test=None):
    """Execute INSERT query and return last row ID."""
    return _orchestrator.execute_insert(story_id, query, params, is_test)


# FTS operations
def has_fts5_support():
    """Check if SQLite supports FTS5."""
    return _orchestrator.has_fts5_support()


def optimize_fts_index(story_id: str, is_test=None):
    """Optimize FTS indexes for better performance."""
    return _orchestrator.optimize_fts_index(story_id, is_test)


def rebuild_fts_index(story_id: str, is_test=None):
    """Rebuild FTS indexes from scratch."""
    return _orchestrator.rebuild_fts_index(story_id, is_test)


def get_fts_stats(story_id: str, is_test=None):
    """Get FTS index statistics."""
    return _orchestrator.get_fts_stats(story_id, is_test)


def check_fts_support():
    """Legacy alias for has_fts5_support."""
    return _orchestrator.check_fts_support()


# Migration operations
def migrate_from_json(story_id: str):
    """Migrate data from JSON files to database."""
    return _orchestrator.migrate_from_json(story_id)


def cleanup_json_files(story_id: str):
    """Clean up JSON files after successful migration."""
    return _orchestrator.cleanup_json_files(story_id)


# Utility operations
def get_database_stats(story_id: str, is_test=None):
    """Get comprehensive database statistics."""
    stats = _orchestrator.get_database_stats(story_id, is_test)
    return stats.to_dict() if hasattr(stats, "to_dict") else stats


def get_db_path(story_id: str, is_test=None):
    """Get database file path for story."""
    return _orchestrator.get_db_path(story_id, is_test)


def ensure_db_dir(story_id: str, is_test=None):
    """Ensure database directory exists."""
    return _orchestrator.ensure_db_dir(story_id, is_test)


# Internal test functions (maintained for compatibility)
def _is_test_context():
    """Detect if we're running in a test context."""
    return _orchestrator._config._is_test_context()


# Direct orchestrator access for advanced usage
def get_orchestrator():
    """Get the DatabaseOrchestrator instance for advanced operations."""
    return _orchestrator
