"""
Test suite for Database

Tests database operations, story data management, and persistence.
"""

import pytest
import tempfile
import shutil
import json
import sqlite3
import os
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from core.database import (
    has_fts5_support,
    get_db_path,
    ensure_db_dir,
    init_database,
    get_connection,
    execute_query,
    execute_update,
    execute_insert,
    migrate_from_json,
    cleanup_json_files,
    get_database_stats,
    optimize_fts_index,
    rebuild_fts_index,
    get_fts_stats,
    check_fts_support
)


@pytest.fixture
def temp_story_id():
    """Create temporary story ID for testing."""
    from datetime import datetime
    return "test_story_" + str(datetime.now().timestamp()).replace('.', '_')


@pytest.fixture
def temp_storage_dir():
    """Create temporary storage directory for testing."""
    temp_dir = tempfile.mkdtemp()
    original_cwd = os.getcwd()
    
    # Create storage subdirectory
    storage_path = os.path.join(temp_dir, "storage")
    os.makedirs(storage_path, exist_ok=True)
    
    # Change to temp directory so database operations work
    os.chdir(temp_dir)
    
    yield temp_dir
    
    # Cleanup
    os.chdir(original_cwd)
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestDatabaseUtilities:
    """Test database utility functions."""
    
    def test_has_fts5_support(self):
        """Test FTS5 support detection."""
        # This should work on most modern SQLite installations
        result = has_fts5_support()
        assert isinstance(result, bool)
    
    def test_get_db_path(self, temp_story_id):
        """Test database path generation."""
        # Test with explicit test flag
        path = get_db_path(temp_story_id, is_test=True)
        expected = os.path.join("storage", "temp", "test_data", temp_story_id, "openchronicle.db")
        assert path == expected
        
        # Test production path
        prod_path = get_db_path(temp_story_id, is_test=False)
        expected_prod = os.path.join("storage", "storypacks", temp_story_id, "openchronicle.db")
        assert prod_path == expected_prod
    
    def test_ensure_db_dir(self, temp_story_id, temp_storage_dir):
        """Test database directory creation."""
        ensure_db_dir(temp_story_id, is_test=True)
        
        expected_dir = os.path.join(temp_storage_dir, "storage", "temp", "test_data", temp_story_id)
        assert os.path.exists(expected_dir)
    
    def test_check_fts_support(self):
        """Test FTS support checking."""
        result = check_fts_support()
        assert isinstance(result, bool)


class TestDatabaseInitialization:
    """Test database initialization."""
    
    def test_init_database(self, temp_story_id, temp_storage_dir):
        """Test database initialization creates required tables."""
        init_database(temp_story_id)
        
        db_path = get_db_path(temp_story_id)
        assert os.path.exists(db_path)
        
        # Check that tables were created
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check scenes table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scenes'")
            assert cursor.fetchone() is not None
            
            # Check memory table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory'")
            assert cursor.fetchone() is not None


class TestDatabaseOperations:
    """Test basic database operations."""
    
    def test_get_connection(self, temp_story_id, temp_storage_dir):
        """Test getting database connection."""
        init_database(temp_story_id)
        
        conn = get_connection(temp_story_id)
        assert conn is not None
        
        # Test that we can execute a query
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        assert len(tables) > 0
        
        conn.close()
    
    def test_execute_query(self, temp_story_id, temp_storage_dir):
        """Test executing a query."""
        init_database(temp_story_id)
        
        # Test simple query
        result = execute_query(temp_story_id, "SELECT name FROM sqlite_master WHERE type='table'")
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_execute_query_with_params(self, temp_story_id, temp_storage_dir):
        """Test executing a query with parameters."""
        init_database(temp_story_id)
        
        # Test query with parameters
        result = execute_query(
            temp_story_id, 
            "SELECT name FROM sqlite_master WHERE type=? AND name=?", 
            ('table', 'scenes')
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['name'] == 'scenes'
    
    def test_execute_update(self, temp_story_id, temp_storage_dir):
        """Test executing an update query."""
        init_database(temp_story_id)
        
        # Test insert operation
        rows_affected = execute_update(
            temp_story_id,
            '''INSERT INTO scenes (scene_id, timestamp, input, output) 
               VALUES (?, ?, ?, ?)''',
            ('test_scene_1', '2024-01-01T10:00:00', 'test input', 'test output')
        )
        
        assert rows_affected == 1
        
        # Verify the insert worked
        result = execute_query(temp_story_id, "SELECT * FROM scenes WHERE scene_id=?", ('test_scene_1',))
        assert len(result) == 1
        assert result[0]['scene_id'] == 'test_scene_1'
    
    def test_execute_insert(self, temp_story_id, temp_storage_dir):
        """Test executing an insert query."""
        init_database(temp_story_id)
        
        # Test insert operation
        last_row_id = execute_insert(
            temp_story_id,
            '''INSERT INTO scenes (scene_id, timestamp, input, output) 
               VALUES (?, ?, ?, ?)''',
            ('test_scene_2', '2024-01-01T11:00:00', 'test input 2', 'test output 2')
        )
        
        assert last_row_id is not None
        
        # Verify the insert worked
        result = execute_query(temp_story_id, "SELECT * FROM scenes WHERE scene_id=?", ('test_scene_2',))
        assert len(result) == 1
        assert result[0]['scene_id'] == 'test_scene_2'


class TestDatabaseStats:
    """Test database statistics and management."""
    
    def test_get_database_stats(self, temp_story_id, temp_storage_dir):
        """Test getting database statistics."""
        init_database(temp_story_id)
        
        # Add some test data
        execute_insert(
            temp_story_id,
            '''INSERT INTO scenes (scene_id, timestamp, input, output) 
               VALUES (?, ?, ?, ?)''',
            ('test_scene', '2024-01-01T10:00:00', 'test input', 'test output')
        )
        
        stats = get_database_stats(temp_story_id)
        assert isinstance(stats, dict)
        # Check for actual stats fields returned by the function
        assert 'database_size_mb' in stats
    
    def test_get_fts_stats(self, temp_story_id, temp_storage_dir):
        """Test getting FTS statistics."""
        init_database(temp_story_id)
        
        stats = get_fts_stats(temp_story_id)
        assert isinstance(stats, dict)
        # FTS stats depend on FTS5 support - check for actual fields
        if has_fts5_support():
            assert 'fts_tables' in stats


class TestDatabaseMigration:
    """Test database migration functionality."""
    
    def test_migrate_from_json_no_files(self, temp_story_id, temp_storage_dir):
        """Test migration when no JSON files exist."""
        init_database(temp_story_id)
        
        # Should complete without error even if no JSON files exist
        result = migrate_from_json(temp_story_id)
        # Function returns a dict with migration info
        assert isinstance(result, dict)
        assert 'migrated' in result
    
    def test_cleanup_json_files_no_files(self, temp_story_id, temp_storage_dir):
        """Test JSON cleanup when no files exist."""
        init_database(temp_story_id)
        
        # Should complete without error even if no JSON files exist
        result = cleanup_json_files(temp_story_id)
        # Function returns a dict with cleanup info
        assert isinstance(result, dict)
        assert 'cleaned' in result


class TestFTSOperations:
    """Test Full-Text Search operations."""
    
    def test_optimize_fts_index(self, temp_story_id, temp_storage_dir):
        """Test FTS index optimization."""
        init_database(temp_story_id)
        
        # Should complete without error
        result = optimize_fts_index(temp_story_id)
        assert result is None  # Function returns None
    
    def test_rebuild_fts_index(self, temp_story_id, temp_storage_dir):
        """Test FTS index rebuilding."""
        init_database(temp_story_id)
        
        # Should complete without error
        result = rebuild_fts_index(temp_story_id)
        assert result is None  # Function returns None


if __name__ == "__main__":
    pytest.main([__file__])
