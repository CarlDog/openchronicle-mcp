"""
Test suite for Rollback Engine

Tests story rollback, state restoration, and version management functionality.
"""

import pytest
import tempfile
import shutil
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from core.rollback_engine import (
    create_rollback_point,
    list_rollback_points,
    get_scenes_after,
    backup_scenes_for_rollback,
    rollback_to_scene,
    rollback_to_timestamp,
    get_rollback_candidates,
    validate_rollback_integrity,
    cleanup_old_rollback_data
)


@pytest.fixture
def temp_story_id():
    """Create temporary story ID for testing."""
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


@pytest.fixture
def sample_scene_data():
    """Sample scene data for testing."""
    return {
        "scene_id": "test_scene_001",
        "timestamp": "2024-01-01T10:00:00",
        "input": "Alice approaches the mysterious tower.",
        "output": "The ancient tower looms before Alice, its dark stones weathered by centuries.",
        "memory_snapshot": {
            "characters": {
                "Alice": {
                    "current_state": {"location": "tower_entrance", "mood": "curious"}
                }
            }
        }
    }


class TestRollbackPointCreation:
    """Test rollback point creation functionality."""
    
    def test_create_rollback_point_success(self, temp_story_id, temp_storage_dir, sample_scene_data):
        """Test creating a rollback point successfully."""
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.load_scene', return_value=sample_scene_data), \
             patch('core.rollback_engine.execute_update', return_value=1):
            
            result = create_rollback_point(temp_story_id, "test_scene_001", "Test rollback point")
            
            assert result is not None
            assert isinstance(result, dict)
            assert "id" in result
            assert "scene_id" in result
            assert result["scene_id"] == "test_scene_001"
            assert result["description"] == "Test rollback point"
    
    def test_create_rollback_point_default_description(self, temp_story_id, temp_storage_dir, sample_scene_data):
        """Test creating rollback point with default description."""
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.load_scene', return_value=sample_scene_data), \
             patch('core.rollback_engine.execute_update', return_value=1):
            
            result = create_rollback_point(temp_story_id, "test_scene_001")
            
            assert result is not None
            assert result["description"] == "Manual rollback point"


class TestRollbackPointListing:
    """Test rollback point listing functionality."""
    
    def test_list_rollback_points_empty(self, temp_story_id, temp_storage_dir):
        """Test listing rollback points when none exist."""
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.execute_query', return_value=[]):
            
            result = list_rollback_points(temp_story_id)
            
            assert isinstance(result, list)
            assert len(result) == 0
    
    def test_list_rollback_points_with_data(self, temp_story_id, temp_storage_dir, sample_scene_data):
        """Test listing rollback points with existing data."""
        mock_rows = [
            {
                "rollback_id": "rollback_test_001",
                "scene_id": "test_scene_001", 
                "timestamp": "2024-01-01T10:00:00",
                "description": "Test point",
                "scene_data": json.dumps(sample_scene_data)
            }
        ]
        
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.execute_query', return_value=mock_rows):
            
            result = list_rollback_points(temp_story_id)
            
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["id"] == "rollback_test_001"  # Function returns "id" not "rollback_id"


class TestSceneQueries:
    """Test scene query functionality."""
    
    def test_get_scenes_after(self, temp_story_id, temp_storage_dir):
        """Test getting scenes after a target scene."""
        # Mock scenes that include the target scene
        mock_scenes = ["scene_001", "scene_002", "scene_003", "scene_004"]
        
        with patch('core.rollback_engine.list_scenes', return_value=mock_scenes):
            result = get_scenes_after(temp_story_id, "scene_001")
            
            # Function should return scenes that come after the target
            assert isinstance(result, list)
            assert result == ["scene_002", "scene_003", "scene_004"]
    
    def test_get_rollback_candidates(self, temp_story_id, temp_storage_dir):
        """Test getting rollback candidates."""
        mock_candidates = [
            {
                "scene_id": "scene_001", 
                "timestamp": "2024-01-01T10:00:00",
                "input": "Test input for scene 001",
                "flags": "[]",
                "memory_snapshot": "{}"
            },
            {
                "scene_id": "scene_002", 
                "timestamp": "2024-01-01T11:00:00",
                "input": "Test input for scene 002",
                "flags": "[]",
                "memory_snapshot": "{}"
            }
        ]
        
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.execute_query', return_value=mock_candidates):
            result = get_rollback_candidates(temp_story_id, limit=5)
            
            assert isinstance(result, list)
            assert len(result) == 2


class TestRollbackOperations:
    """Test rollback operations."""
    
    def test_backup_scenes_for_rollback(self, temp_story_id, temp_storage_dir):
        """Test backing up scenes for rollback."""
        scenes_to_backup = ["scene_002", "scene_003"]
        
        with patch('core.rollback_engine.load_scene', return_value={"test": "data"}), \
             patch('core.rollback_engine.execute_update', return_value=1):
            
            # Function returns None but doesn't raise an exception
            backup_scenes_for_rollback(temp_story_id, scenes_to_backup)
            # Test passes if no exception is raised
    
    def test_rollback_to_scene_with_backup(self, temp_story_id, temp_storage_dir):
        """Test rolling back to a specific scene with backup."""
        with patch('core.rollback_engine.get_scenes_after', return_value=["scene_002"]), \
             patch('core.rollback_engine.backup_scenes_for_rollback'), \
             patch('core.rollback_engine.load_scene', return_value={"scene_id": "scene_001"}), \
             patch('core.rollback_engine.execute_update', return_value=1), \
             patch('core.rollback_engine.restore_memory_from_snapshot'):
            
            result = rollback_to_scene(temp_story_id, "scene_001", create_backup=True)
            
            assert isinstance(result, dict)
            assert "success" in result
    
    def test_rollback_to_scene_without_backup(self, temp_story_id, temp_storage_dir):
        """Test rolling back to a specific scene without backup."""
        with patch('core.rollback_engine.get_scenes_after', return_value=["scene_002"]), \
             patch('core.rollback_engine.load_scene', return_value={"scene_id": "scene_001"}), \
             patch('core.rollback_engine.execute_update', return_value=1), \
             patch('core.rollback_engine.restore_memory_from_snapshot'):
            
            result = rollback_to_scene(temp_story_id, "scene_001", create_backup=False)
            
            assert isinstance(result, dict)
            assert "success" in result
    
    def test_rollback_to_timestamp(self, temp_story_id, temp_storage_dir):
        """Test rolling back to a specific timestamp."""
        target_timestamp = "2024-01-01T10:00:00"
        
        with patch('core.rollback_engine.execute_query', return_value=[{"scene_id": "scene_001"}]), \
             patch('core.rollback_engine.rollback_to_scene', return_value={"success": True}):
            
            result = rollback_to_timestamp(temp_story_id, target_timestamp)
            
            assert isinstance(result, dict)


class TestRollbackValidation:
    """Test rollback validation functionality."""
    
    def test_validate_rollback_integrity_success(self, temp_story_id, temp_storage_dir):
        """Test validating rollback integrity when everything is correct."""
        mock_rollback_points = [
            {"rollback_id": "test_001", "scene_id": "scene_001", "scene_data": '{"valid": "data"}'}
        ]
        
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.execute_query', return_value=mock_rollback_points), \
             patch('core.rollback_engine.load_scene', return_value={"valid": "data"}):
            
            result = validate_rollback_integrity(temp_story_id)
            
            assert isinstance(result, list)  # Function returns a list of issues
    
    def test_validate_rollback_integrity_issues(self, temp_story_id, temp_storage_dir):
        """Test validation when there are integrity issues."""
        mock_rollback_points = [
            {"rollback_id": "test_001", "scene_id": "missing_scene", "scene_data": '{"data": "test"}'}
        ]
        
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.execute_query', return_value=mock_rollback_points), \
             patch('core.rollback_engine.load_scene', side_effect=FileNotFoundError):
            
            result = validate_rollback_integrity(temp_story_id)
            
            assert isinstance(result, list)  # Function returns a list of issues


class TestRollbackCleanup:
    """Test rollback cleanup functionality."""
    
    def test_cleanup_old_rollback_data_default_days(self, temp_story_id, temp_storage_dir):
        """Test cleaning up old rollback data with default retention."""
        with patch('core.rollback_engine.execute_update', return_value=2):
            result = cleanup_old_rollback_data(temp_story_id)
            
            assert isinstance(result, dict)
            assert "cleaned" in result
    
    def test_cleanup_old_rollback_data_custom_days(self, temp_story_id, temp_storage_dir):
        """Test cleaning up old rollback data with custom retention."""
        with patch('core.rollback_engine.execute_update', return_value=1):
            result = cleanup_old_rollback_data(temp_story_id, days_to_keep=7)
            
            assert isinstance(result, dict)
            assert "cleaned" in result
    
    def test_cleanup_old_rollback_data_no_old_data(self, temp_story_id, temp_storage_dir):
        """Test cleanup when no old data exists."""
        with patch('core.rollback_engine.execute_update', return_value=0):
            result = cleanup_old_rollback_data(temp_story_id)
            
            assert isinstance(result, dict)
            assert "cleaned" in result
            assert result["cleaned"] == 0


class TestErrorHandling:
    """Test error handling in rollback operations."""
    
    def test_create_rollback_point_missing_scene(self, temp_story_id, temp_storage_dir):
        """Test creating rollback point for non-existent scene."""
        with patch('core.rollback_engine.init_database'), \
             patch('core.rollback_engine.load_scene', side_effect=FileNotFoundError):
            
            with pytest.raises(FileNotFoundError):
                create_rollback_point(temp_story_id, "missing_scene")
    
    def test_rollback_to_scene_invalid_target(self, temp_story_id, temp_storage_dir):
        """Test rollback to invalid scene ID."""
        with patch('core.rollback_engine.get_scenes_after', return_value=[]), \
             patch('core.rollback_engine.load_scene', side_effect=FileNotFoundError("No scene found")):
            
            # Should raise FileNotFoundError for invalid scene
            with pytest.raises(FileNotFoundError):
                rollback_to_scene(temp_story_id, "invalid_scene")


if __name__ == "__main__":
    pytest.main([__file__])
