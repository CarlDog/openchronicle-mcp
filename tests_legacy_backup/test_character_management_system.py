"""
Test Character Management System

Comprehensive tests for the new modular character management system that replaces
the legacy character engines.
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.character_management import CharacterOrchestrator
from core.character_management.character_data import CharacterData, CharacterStatType


class TestCharacterManagementSystem:
    """Test suite for the modular character management system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        
        # Initialize character orchestrator with test config
        config = {
            'storage': {
                'base_path': self.temp_dir,
                'auto_save': True
            },
            'auto_load_components': True
        }
        self.orchestrator = CharacterOrchestrator(config)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_character_orchestrator_initialization(self):
        """Test CharacterOrchestrator initializes correctly with all components."""
        # Test basic initialization
        assert self.orchestrator is not None
        
        # Test components are loaded
        assert hasattr(self.orchestrator, 'stats_component')
        assert hasattr(self.orchestrator, 'interactions_component')
        assert hasattr(self.orchestrator, 'consistency_component')
        assert hasattr(self.orchestrator, 'presentation_component')
        
        # Test component registration
        assert 'stats' in self.orchestrator.components
        assert 'interactions' in self.orchestrator.components
        assert 'consistency' in self.orchestrator.components
        assert 'presentation' in self.orchestrator.components
    
    def test_character_lifecycle_management(self):
        """Test complete character lifecycle: create, read, update, delete."""
        # Test character creation
        char_data = {
            'name': 'Test Character',
            'physical_description': 'A brave adventurer',
            'personality_traits': ['brave', 'curious'],
            'stats': {
                'strength': 8,
                'intelligence': 7,
                'charisma': 6
            }
        }
        
        char_id = self.orchestrator.create_character('test_char_001', char_data)
        assert isinstance(char_id, str)
        assert char_id == 'test_char_001'
        
        # Test character retrieval
        character = self.orchestrator.get_character(char_id)
        assert character is not None
        assert character.name == 'Test Character'
        assert character.physical_description == 'A brave adventurer'
        
        # Test character listing
        char_list = self.orchestrator.list_characters()
        assert len(char_list) >= 1
        assert char_id in [char.character_id for char in char_list]
        
        # Test character deletion
        success = self.orchestrator.delete_character(char_id)
        assert success == True
        
        # Verify deletion
        character = self.orchestrator.get_character(char_id)
        assert character is None
    
    def test_component_provider_interfaces(self):
        """Test that components implement required provider interfaces correctly."""
        # Create test character
        char_data = {'name': 'Provider Test Character'}
        char_id = self.orchestrator.create_character('provider_test', char_data)
        
        # Test CharacterBehaviorProvider (stats component)
        behavior_context = self.orchestrator.stats_component.get_behavior_context(
            char_id, 'dialogue'
        )
        assert isinstance(behavior_context, dict)
        
        response_modifiers = self.orchestrator.stats_component.generate_response_modifiers(
            char_id, 'dialogue'
        )
        assert isinstance(response_modifiers, dict)
        
        # Test CharacterValidationProvider (consistency component)
        action = {'type': 'dialogue', 'content': 'Hello world'}
        is_valid, message = self.orchestrator.consistency_component.validate_character_action(
            char_id, action
        )
        assert isinstance(is_valid, bool)
        
        consistency_score = self.orchestrator.consistency_component.get_consistency_score(char_id)
        assert isinstance(consistency_score, float)
        assert 0.0 <= consistency_score <= 1.0
        
        # Test CharacterStateProvider (interactions component)
        state = self.orchestrator.interactions_component.get_character_state(char_id)
        assert isinstance(state, dict)
        
        # Cleanup
        self.orchestrator.delete_character(char_id)
    
    def test_stats_component_functionality(self):
        """Test stats component RPG-style functionality."""
        # Create character with stats
        char_data = {
            'name': 'Stats Test Character',
            'stats': {
                'strength': 10,
                'intelligence': 8,
                'charisma': 6
            }
        }
        char_id = self.orchestrator.create_character('stats_test', char_data)
        
        # Test stat retrieval
        strength = self.orchestrator.stats_component.get_effective_stat(
            char_id, CharacterStatType.STRENGTH
        )
        assert strength == 10
        
        # Test stat modification
        self.orchestrator.stats_component.update_character_stat(
            char_id, CharacterStatType.STRENGTH, 12
        )
        
        new_strength = self.orchestrator.stats_component.get_effective_stat(
            char_id, CharacterStatType.STRENGTH
        )
        assert new_strength == 12
        
        # Test behavior context generation
        behavior_context = self.orchestrator.stats_component.get_behavior_context(
            char_id, 'combat'
        )
        assert 'strength_influence' in behavior_context
        assert 'primary_stats' in behavior_context
        
        # Cleanup
        self.orchestrator.delete_character(char_id)
    
    def test_consistency_component_functionality(self):
        """Test consistency component validation functionality."""
        # Create character with personality traits
        char_data = {
            'name': 'Consistency Test Character',
            'personality_traits': ['brave', 'honest', 'loyal'],
            'core_motivations': ['protect others', 'seek truth']
        }
        char_id = self.orchestrator.create_character('consistency_test', char_data)
        
        # Test action validation - should be consistent
        brave_action = {
            'type': 'dialogue',
            'content': 'I will stand and fight!',
            'context': 'combat_situation'
        }
        is_valid, message = self.orchestrator.consistency_component.validate_character_action(
            char_id, brave_action
        )
        assert is_valid == True
        
        # Test consistency score
        score = self.orchestrator.consistency_component.get_consistency_score(char_id)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        
        # Cleanup
        self.orchestrator.delete_character(char_id)
    
    def test_interactions_component_functionality(self):
        """Test interactions component relationship functionality."""
        # Create two characters for relationship testing
        char1_data = {'name': 'Character One'}
        char2_data = {'name': 'Character Two'}
        
        char1_id = self.orchestrator.create_character('char1', char1_data)
        char2_id = self.orchestrator.create_character('char2', char2_data)
        
        # Test relationship initialization
        self.orchestrator.interactions_component.initialize_relationship(
            char1_id, char2_id, 'friendship'
        )
        
        # Test relationship retrieval
        relationship = self.orchestrator.interactions_component.get_relationship(
            char1_id, char2_id
        )
        assert relationship is not None
        assert relationship['type'] == 'friendship'
        
        # Test character state
        state = self.orchestrator.interactions_component.get_character_state(char1_id)
        assert isinstance(state, dict)
        assert 'relationships' in state
        
        # Cleanup
        self.orchestrator.delete_character(char1_id)
        self.orchestrator.delete_character(char2_id)
    
    def test_presentation_component_functionality(self):
        """Test presentation component style functionality."""
        # Create character with style preferences
        char_data = {
            'name': 'Presentation Test Character',
            'style_preferences': {
                'formality': 'casual',
                'verbosity': 'moderate',
                'personality_emphasis': 'high'
            }
        }
        char_id = self.orchestrator.create_character('presentation_test', char_data)
        
        # Test style profile retrieval
        style_profile = self.orchestrator.presentation_component.get_character_style_profile(char_id)
        assert isinstance(style_profile, dict)
        assert 'formality' in style_profile
        
        # Test model selection
        model_selection = self.orchestrator.presentation_component.select_appropriate_model(
            char_id, 'dialogue'
        )
        assert isinstance(model_selection, dict)
        
        # Cleanup
        self.orchestrator.delete_character(char_id)
    
    def test_error_handling(self):
        """Test error handling for invalid operations."""
        # Test retrieving non-existent character
        character = self.orchestrator.get_character('nonexistent_character')
        assert character is None
        
        # Test deleting non-existent character
        success = self.orchestrator.delete_character('nonexistent_character')
        assert success == False
        
        # Test component operations on non-existent character
        with pytest.raises(Exception):
            self.orchestrator.stats_component.get_effective_stat(
                'nonexistent_character', CharacterStatType.STRENGTH
            )
    
    def test_storage_persistence(self):
        """Test that character data persists correctly."""
        # Create character
        char_data = {
            'name': 'Persistence Test Character',
            'stats': {'strength': 10}
        }
        char_id = self.orchestrator.create_character('persistence_test', char_data)
        
        # Create new orchestrator instance (simulating restart)
        new_config = {
            'storage': {
                'base_path': self.temp_dir,
                'auto_save': True
            },
            'auto_load_components': True
        }
        new_orchestrator = CharacterOrchestrator(new_config)
        
        # Verify character data persisted
        persisted_character = new_orchestrator.get_character(char_id)
        assert persisted_character is not None
        assert persisted_character.name == 'Persistence Test Character'
        
        # Cleanup
        new_orchestrator.delete_character(char_id)


if __name__ == '__main__':
    pytest.main([__file__])
