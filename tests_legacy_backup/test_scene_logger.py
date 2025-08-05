"""
Tests for the scene logger module.
Tests scene logging, retrieval, and analytics functionality.
"""

import pytest
import json
from unittest.mock import patch

# Import scene logger functions
from core.scene_systems.scene_orchestrator import (
    generate_scene_id,
    save_scene,
    load_scene,
    get_scenes_with_long_turns,
    get_scenes_by_mood,
    get_scenes_by_type,
    get_token_usage_stats,
    get_character_mood_timeline,
    list_scenes,
    update_scene_label,
    get_scenes_by_label,
    get_labeled_scenes,
    get_scene_summary_stats
)
from core.scene_systems import SceneOrchestrator


class TestSceneGeneration:
    """Test scene ID generation."""
    
    def test_generate_scene_id(self):
        """Test scene ID generation produces unique IDs."""
        scene_id_1 = generate_scene_id()
        scene_id_2 = generate_scene_id()
        
        assert scene_id_1 != scene_id_2
        assert isinstance(scene_id_1, str)
        assert isinstance(scene_id_2, str)
        assert len(scene_id_1) > 0
        assert len(scene_id_2) > 0


class TestSceneLogging:
    """Test scene logging functionality."""
    
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_update')
    @patch('core.scene_logger.generate_scene_id')
    def test_save_scene_basic(self, mock_generate_id, mock_execute_update, mock_init_db):
        """Test basic scene saving."""
        mock_generate_id.return_value = "scene_001"
        mock_execute_update.return_value = True
        
        result = save_scene("test_story", "Hello", "Hi there!")
        
        assert result == "scene_001"
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_update.assert_called_once()
        
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_update')
    @patch('core.scene_logger.generate_scene_id')
    def test_save_scene_with_memory(self, mock_generate_id, mock_execute_update, mock_init_db):
        """Test scene saving with memory snapshot."""
        mock_generate_id.return_value = "scene_002"
        mock_execute_update.return_value = True
        
        memory_snapshot = {"characters": {"Alice": {"mood": "curious"}}}
        result = save_scene("test_story", "Look around", "You see a forest.", memory_snapshot)
        
        assert result == "scene_002"
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_update.assert_called_once()


class TestSceneRetrieval:
    """Test scene retrieval functionality."""
    
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_query')
    def test_load_scene_exists(self, mock_execute_query, mock_init_db):
        """Test loading an existing scene."""
        mock_scene_row = {
            "scene_id": "scene_001",
            "timestamp": "2024-01-01T12:00:00Z",
            "input": "Hello",
            "output": "Hi there!",
            "memory_snapshot": "{}",
            "flags": "[]", 
            "canon_refs": "[]",
            "scene_label": None,
            "structured_tags": "{}"
        }
        mock_execute_query.return_value = [mock_scene_row]
        
        result = load_scene("test_story", "scene_001")
        
        expected_result = {
            "scene_id": "scene_001",
            "timestamp": "2024-01-01T12:00:00Z",
            "input": "Hello",
            "output": "Hi there!",
            "memory": {},
            "flags": [],
            "canon_refs": [],
            "scene_label": None,
            "structured_tags": {}
        }
        assert result == expected_result
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_query.assert_called_once()
        
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_query')
    def test_load_scene_not_found(self, mock_execute_query, mock_init_db):
        """Test loading a non-existent scene raises error."""
        mock_execute_query.return_value = []
        
        with pytest.raises(FileNotFoundError):
            load_scene("test_story", "nonexistent")
            
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_query.assert_called_once()
        
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_query')
    def test_list_scenes(self, mock_execute_query, mock_init_db):
        """Test listing all scenes."""
        mock_scene_rows = [
            {"scene_id": "scene_001", "timestamp": "2024-01-01T12:00:00Z", "scene_label": None, "structured_tags": "{}"},        
            {"scene_id": "scene_002", "timestamp": "2024-01-01T12:01:00Z", "scene_label": "important", "structured_tags": "{}"}  
        ]
        mock_execute_query.return_value = mock_scene_rows
        
        result = list_scenes("test_story")
        
        # Function returns enhanced scene data with mood and scene_type
        assert len(result) == 2
        assert result[0]["scene_id"] == "scene_001"
        assert result[1]["scene_id"] == "scene_002"
        assert "timestamp" in result[0]
        assert "scene_label" in result[0]
        assert "mood" in result[0]  # Added by the function
        assert "scene_type" in result[0]  # Added by the function
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_query.assert_called_once()


class TestSceneRollback:
    """Test scene rollback functionality."""
    
    # NOTE: Rollback functionality moved to TimelineOrchestrator
    # This test is commented out as rollback is no longer a scene-level operation
    
    # @patch('core.scene_logger.load_scene')
    # def test_rollback_to_scene(self, mock_load_scene):
    #     """Test rolling back to a specific scene."""
    #     mock_scene_data = {
    #         "scene_id": "scene_001",
    #         "timestamp": "2024-01-01T12:00:00Z",
    #         "input": "Hello",
    #         "output": "Hi",
    #         "memory": {},
    #         "flags": [],
    #         "canon_refs": [],
    #         "scene_label": None,
    #         "structured_tags": {}
    #     }
    #     mock_load_scene.return_value = mock_scene_data
    #     
    #     result = rollback_to_scene("test_story", "scene_001")
    #     
    #     # Function returns scene data for rebuilding state
    #     assert isinstance(result, dict)
    #     assert result["scene_id"] == "scene_001"
    #     assert result["input"] == "Hello"
    #     assert result["output"] == "Hi"
    #     assert "memory" in result
    #     assert "flags" in result
    #     mock_load_scene.assert_called_once_with("test_story", "scene_001")

    pass  # Placeholder for future timeline integration tests


class TestSceneLabeling:
    """Test scene labeling functionality."""
    
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_update')
    def test_update_scene_label(self, mock_execute_update, mock_init_db):
        """Test updating scene label."""
        mock_execute_update.return_value = True
        
        result = update_scene_label("test_story", "scene_001", "important")
        
        assert result is True
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_update.assert_called_once()
        
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_query')
    def test_get_scenes_by_label(self, mock_execute_query, mock_init_db):
        """Test getting scenes by label."""
        mock_scene_rows = [
            {
                "scene_id": "scene_001",
                "timestamp": "2024-01-01T12:00:00Z",
                "input": "Hello",
                "output": "Hi",
                "memory_snapshot": "{}",
                "flags": "[]",
                "canon_refs": "[]",
                "scene_label": "important"
            }
        ]
        mock_execute_query.return_value = mock_scene_rows
        
        result = get_scenes_by_label("test_story", "important")
        
        assert len(result) == 1
        assert result[0]["scene_id"] == "scene_001"
        assert result[0]["scene_label"] == "important"
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_query.assert_called_once()
        
    @patch('core.scene_logger.init_database')
    @patch('core.scene_logger.execute_query')
    def test_get_labeled_scenes(self, mock_execute_query, mock_init_db):
        """Test getting all labeled scenes."""
        mock_scene_rows = [
            {"scene_id": "scene_001", "timestamp": "2024-01-01T12:00:00Z", "scene_label": "important", "input": "Hello"},
            {"scene_id": "scene_002", "timestamp": "2024-01-01T12:01:00Z", "scene_label": "memorable", "input": "Goodbye"}
        ]
        mock_execute_query.return_value = mock_scene_rows
        
        result = get_labeled_scenes("test_story")
        
        assert len(result) == 2
        assert result[0]["scene_label"] == "important"
        assert result[1]["scene_label"] == "memorable"
        mock_init_db.assert_called_once_with("test_story")
        mock_execute_query.assert_called_once()
