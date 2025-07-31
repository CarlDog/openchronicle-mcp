"""Tests for shared database operations."""

import pytest
import tempfile
import os
from pathlib import Path

from core.shared.database_operations import DatabaseOperations, QueryBuilder

@pytest.fixture
def temp_story_id():
    """Create temporary story ID for testing."""
    return "test_story_" + str(os.getpid())

def test_database_operations_init(temp_story_id):
    """Test DatabaseOperations initialization."""
    db_ops = DatabaseOperations(temp_story_id, is_test=True)
    assert db_ops.story_id == temp_story_id
    assert db_ops.is_test is True
    assert "test_data" in db_ops.db_path

def test_query_builder():
    """Test QueryBuilder functionality."""
    builder = QueryBuilder()
    query, params = (builder
                    .select(["id", "name"])
                    .from_table("users")
                    .where("age > ?", 18)
                    .where("status = ?", "active")
                    .order_by("name")
                    .limit(10)
                    .build())
    
    expected = "SELECT id, name FROM users WHERE age > ? AND status = ? ORDER BY name ASC LIMIT 10"
    assert query == expected
    assert params == (18, "active")

def test_query_builder_reset():
    """Test QueryBuilder reset functionality."""
    builder = QueryBuilder()
    builder.select("id").from_table("test")
    builder.reset()
    query, params = builder.select("name").from_table("users").build()
    
    expected = "SELECT name FROM users"
    assert query == expected
    assert params == ()

def test_database_operations_context_detection():
    """Test automatic test context detection."""
    # Should detect we're in pytest
    db_ops = DatabaseOperations("test_story")
    assert db_ops.is_test is True

def test_backward_compatibility_functions(temp_story_id):
    """Test that backward compatibility functions work."""
    from core.shared.database_operations import get_db_path, get_connection
    
    # Test get_db_path
    db_path = get_db_path(temp_story_id, is_test=True)
    assert "test_data" in db_path
    assert temp_story_id in db_path
    
    # Test get_connection
    with get_connection(temp_story_id, is_test=True) as conn:
        assert conn is not None
        # Should be able to execute a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
