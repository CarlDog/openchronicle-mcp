"""
Test async database operations.
Validates the new async database implementation.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from core.database.async_database_orchestrator import AsyncDatabaseOrchestrator
from core.shared.async_database_operations import AsyncDatabaseOperations


@pytest.mark.asyncio
class TestAsyncDatabaseOperations:
    """Test async database operations."""
    
    @pytest.fixture
    def async_orchestrator(self):
        """Create async database orchestrator for testing."""
        return AsyncDatabaseOrchestrator()
    
    @pytest.fixture
    def test_story_id(self):
        """Generate unique test story ID for each test."""
        import uuid
        return f"test_async_story_{uuid.uuid4().hex[:8]}"
    
    async def test_async_database_initialization(self, async_orchestrator, test_story_id):
        """Test async database initialization."""
        result = await async_orchestrator.init_database(test_story_id, is_test=True)
        assert result is True
        
        # Verify database was created
        info = await async_orchestrator.get_database_info(test_story_id, is_test=True)
        assert "tables" in info
        expected_tables = {"scenes", "characters", "memory", "bookmarks"}
        assert expected_tables.issubset(set(info["tables"]))
    
    async def test_async_basic_operations(self, async_orchestrator, test_story_id):
        """Test basic async CRUD operations."""
        import uuid
        scene_id_str = f"scene_{uuid.uuid4().hex[:8]}"
        
        # Initialize database first
        await async_orchestrator.init_database(test_story_id, is_test=True)
        
        # Test INSERT
        insert_query = """
            INSERT INTO scenes (id, title, content, timestamp) 
            VALUES (?, ?, ?, ?)
        """
        scene_id = await async_orchestrator.execute_insert(
            test_story_id, insert_query, 
            (scene_id_str, "Test Scene", "This is a test scene.", 1234567890.0),
            is_test=True
        )
        assert scene_id is not None
        
        # Test SELECT
        select_query = "SELECT * FROM scenes WHERE id = ?"
        results = await async_orchestrator.execute_query(
            test_story_id, select_query, (scene_id_str,), is_test=True
        )
        assert len(results) == 1
        assert results[0]["title"] == "Test Scene"
        assert results[0]["content"] == "This is a test scene."
        
        # Test UPDATE
        update_query = "UPDATE scenes SET title = ? WHERE id = ?"
        update_result = await async_orchestrator.execute_update(
            test_story_id, update_query, ("Updated Scene", scene_id_str), is_test=True
        )
        assert update_result is True
        
        # Verify update
        results = await async_orchestrator.execute_query(
            test_story_id, "SELECT title FROM scenes WHERE id = ?", 
            (scene_id_str,), is_test=True
        )
        assert results[0]["title"] == "Updated Scene"
    
    async def test_async_many_operations(self, async_orchestrator, test_story_id):
        """Test async batch operations."""
        await async_orchestrator.init_database(test_story_id, is_test=True)
        
        # Test execute_many
        insert_query = "INSERT INTO characters (id, name, description) VALUES (?, ?, ?)"
        params_list = [
            ("char_001", "Alice", "Main protagonist"),
            ("char_002", "Bob", "Supporting character"),
            ("char_003", "Charlie", "Antagonist")
        ]
        
        result = await async_orchestrator.execute_many(
            test_story_id, insert_query, params_list, is_test=True
        )
        assert result is True
        
        # Verify all characters were inserted
        results = await async_orchestrator.execute_query(
            test_story_id, "SELECT COUNT(*) as count FROM characters", is_test=True
        )
        assert results[0]["count"] == 3
    
    async def test_async_integrity_check(self, async_orchestrator, test_story_id):
        """Test async database integrity check."""
        await async_orchestrator.init_database(test_story_id, is_test=True)
        
        integrity_result = await async_orchestrator.check_integrity(test_story_id, is_test=True)
        assert integrity_result is True
    
    async def test_async_connection_check(self, async_orchestrator, test_story_id):
        """Test async connection verification."""
        connection_result = await async_orchestrator.check_connection(test_story_id, is_test=True)
        assert connection_result is True
    
    async def test_async_startup_health_check(self, async_orchestrator):
        """Test async startup health check for multiple databases."""
        story_ids = ["health_test_001", "health_test_002", "health_test_003"]
        
        # Initialize test databases
        for story_id in story_ids:
            await async_orchestrator.init_database(story_id, is_test=True)
        
        # Run health check
        health_results = await async_orchestrator.startup_health_check(story_ids)
        
        assert len(health_results) == 3
        for story_id in story_ids:
            assert health_results[story_id] is True
    
    async def test_async_concurrent_operations(self, async_orchestrator, test_story_id):
        """Test concurrent async operations."""
        import uuid
        base_id = uuid.uuid4().hex[:8]
        
        await async_orchestrator.init_database(test_story_id, is_test=True)
        
        # Create multiple concurrent insert tasks
        async def insert_scene(scene_num):
            query = "INSERT INTO scenes (id, title, content) VALUES (?, ?, ?)"
            return await async_orchestrator.execute_insert(
                test_story_id, query, 
                (f"scene_{base_id}_{scene_num:03d}", f"Scene {scene_num}", f"Content {scene_num}"),
                is_test=True
            )
        
        # Run 10 concurrent inserts
        tasks = [insert_scene(i) for i in range(1, 11)]
        results = await asyncio.gather(*tasks)
        
        # Verify all inserts succeeded
        assert all(result is not None for result in results), f"Some inserts failed: {results}"
        
        # Verify all scenes were inserted
        count_result = await async_orchestrator.execute_query(
            test_story_id, "SELECT COUNT(*) as count FROM scenes", is_test=True
        )
        assert count_result[0]["count"] == 10


@pytest.mark.asyncio
class TestAsyncDatabasePerformance:
    """Test async database performance improvements."""
    
    @pytest.fixture
    def async_orchestrator(self):
        """Create async database orchestrator for testing."""
        return AsyncDatabaseOrchestrator()
    
    @pytest.fixture
    def performance_story_id(self):
        """Generate unique performance test story ID."""
        import uuid
        return f"perf_test_async_{uuid.uuid4().hex[:8]}"
    
    async def test_async_performance_baseline(self, async_orchestrator, performance_story_id):
        """Establish performance baseline for async operations."""
        import time
        import uuid
        base_id = uuid.uuid4().hex[:8]
        
        await async_orchestrator.init_database(performance_story_id, is_test=True)
        
        # Test batch insert performance
        start_time = time.time()
        
        query = "INSERT INTO scenes (id, title, content, timestamp) VALUES (?, ?, ?, ?)"
        params_list = [
            (f"scene_{base_id}_{i:04d}", f"Scene {i}", f"Content for scene {i}", time.time())
            for i in range(100)
        ]
        
        result = await async_orchestrator.execute_many(
            performance_story_id, query, params_list, is_test=True
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        assert result is True
        assert duration < 1.0  # Should complete in under 1 second
        
        # Verify all records inserted
        count_result = await async_orchestrator.execute_query(
            performance_story_id, "SELECT COUNT(*) as count FROM scenes", is_test=True
        )
        assert count_result[0]["count"] == 100
