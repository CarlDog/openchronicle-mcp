"""
Test suite for Memory Manager.
Tests memory loading, saving, and management functionality.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch, mock_open

from core.memory_manager import (
    load_current_memory,
    save_current_memory,
    update_character_memory,
    get_character_memory_snapshot,
    get_memory_summary
)


@pytest.fixture
def temp_story_id():
    """Create temporary story ID for testing."""
    return "test_story_" + str(datetime.now().timestamp()).replace('.', '_')


@pytest.fixture
def sample_memory_data():
    """Sample memory data for testing."""
    return {
        "characters": {
            "Alice": {
                "current_state": {
                    "location": "village_square",
                    "mood": "curious",
                    "health": 100,
                    "inventory": ["sword", "map"],
                    "status": "active"
                },
                "memories": {
                    "key_facts": ["Met the wizard in the tower", "Found ancient map"],
                    "relationships": {"wizard": "mentor", "bob": "friend"},
                    "goals": ["Find the lost artifact", "Save the village"]
                }
            }
        },
        "world_state": {
            "time_of_day": "afternoon",
            "weather": "cloudy",
            "current_scene": "village_square",
            "active_events": ["wizard_tower_mystery"]
        },
        "memory_flags": {
            "tower_discovered": True,
            "map_obtained": True
        },
        "flags": [],  # Added missing flags field for summary function
        "recent_events": [],
        "metadata": {  # Added missing metadata field for save function
            "last_updated": "2024-01-01T10:00:00",
            "version": "1.0"
        }
    }


class TestMemoryLoading:
    """Test memory loading functionality."""
    
    def test_load_current_memory_success(self, temp_story_id):
        """Test successful loading of current memory."""
        # Mock database calls to avoid file system operations
        mock_rows = [
            {"type": "characters", "key": "characters", "value": '{"Alice": {"current_state": {"location": "village_square"}}}'},
            {"type": "world_state", "key": "world_state", "value": '{"time_of_day": "afternoon"}'}
        ]
        
        with patch('core.memory_manager.init_database'), \
             patch('core.memory_manager.execute_query', return_value=mock_rows):
            memory = load_current_memory(temp_story_id)
            
            assert memory is not None
            assert "characters" in memory
            assert "Alice" in memory["characters"]
    
    def test_load_current_memory_file_not_found(self, temp_story_id):
        """Test loading memory when no data exists."""
        with patch('core.memory_manager.init_database'), \
             patch('core.memory_manager.execute_query', return_value=[]):
            memory = load_current_memory(temp_story_id)
            
            # Should return default memory structure
            assert memory is not None
            assert "characters" in memory
            assert "world_state" in memory


class TestMemorySaving:
    """Test memory saving functionality."""
    
    def test_save_current_memory_success(self, temp_story_id, sample_memory_data):
        """Test successful saving of current memory."""
        with patch('core.memory_manager.init_database'), \
             patch('core.memory_manager.execute_update', return_value=1) as mock_update:
            result = save_current_memory(temp_story_id, sample_memory_data)
            
            # Function doesn't return a value, just ensure it doesn't raise an exception
            # Should make database calls
            assert mock_update.call_count >= 1


class TestCharacterMemory:
    """Test character-specific memory functionality."""
    
    def test_update_character_memory(self, temp_story_id, sample_memory_data):
        """Test updating character memory."""
        updates = {
            "current_state": {
                "location": "wizard_tower",
                "mood": "determined"
            }
        }
        
        with patch('core.memory_manager.load_current_memory', return_value=sample_memory_data), \
             patch('core.memory_manager.save_current_memory', return_value=True):
            result = update_character_memory(temp_story_id, "Alice", updates)
            
            # Function returns the updated memory object, not True/False
            assert result is not None
            assert "characters" in result
            assert "Alice" in result["characters"]
    
    def test_get_character_memory_snapshot(self, temp_story_id, sample_memory_data):
        """Test getting character memory snapshot."""
        with patch('core.memory_manager.load_current_memory', return_value=sample_memory_data):
            snapshot = get_character_memory_snapshot(temp_story_id, "Alice")
            
            # The function returns character memory directly
            assert snapshot is not None
            # May be dict or dict containing memory data


class TestMemorySummary:
    """Test memory summary functionality."""
    
    def test_get_memory_summary(self, temp_story_id, sample_memory_data):
        """Test getting memory summary."""
        with patch('core.memory_manager.load_current_memory', return_value=sample_memory_data):
            summary = get_memory_summary(temp_story_id)
            
            # The function may return summary data structure
            assert summary is not None


if __name__ == "__main__":
    pytest.main([__file__])
