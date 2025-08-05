"""
Integration tests for the unified character management system.

Tests the interaction between CharacterOrchestrator and all component engines:
- StatsBehaviorEngine
- InteractionDynamicsEngine  
- ConsistencyValidationEngine
- PresentationStyleEngine

These tests validate the provider pattern implementation and component integration.
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, List

from core.character_management import (
    CharacterOrchestrator,
    CharacterData,
    CharacterStorage
)
from core.character_management.stats import StatsBehaviorEngine
from core.character_management.interactions import InteractionDynamicsEngine
from core.character_management.consistency import ConsistencyValidationEngine
from core.character_management.presentation import PresentationStyleEngine


class TestCharacterManagementIntegration:
    """Integration tests for character management system."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create temporary storage directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "characters"
            backup_path = Path(temp_dir) / "backups"
            yield {
                'storage_path': str(storage_path),
                'backup_path': str(backup_path),
                'cache_ttl_minutes': 1,
                'auto_save': True,
                'backup_enabled': True
            }
    
    @pytest.fixture
    def character_orchestrator(self, temp_storage):
        """Create character orchestrator with all components."""
        config = {
            'storage': temp_storage,
            'components': {
                'stats': {'progression_rate': 1.2, 'behavior_weight': 0.7},
                'interactions': {'relationship_decay': 0.1, 'max_active_relationships': 10},
                'consistency': {'tolerance_threshold': 0.8, 'violation_penalty': 0.2},
                'presentation': {'default_style': 'neutral', 'model_preference': 'adaptive'}
            }
        }
        
        orchestrator = CharacterOrchestrator(config)
        return orchestrator
    
    @pytest.fixture
    def sample_character_data(self):
        """Sample character data for testing."""
        return {
            'name': 'Elena Vasquez',
            'description': 'A brilliant scientist with a mysterious past',
            'personality_traits': ['intelligent', 'curious', 'secretive'],
            'background': 'Former quantum physicist turned private investigator',
            'motivation': 'Seeking the truth about her disappeared colleague',
            'stats': {
                'intelligence': 18,
                'charisma': 14,
                'perception': 16,
                'willpower': 15
            },
            'relationships': {
                'Dr. Marcus': {'type': 'colleague', 'affinity': 0.7, 'trust': 0.8},
                'Agent Smith': {'type': 'rival', 'affinity': -0.3, 'trust': 0.2}
            }
        }
    
    # =============================================================================
    # Core Integration Tests
    # =============================================================================
    
    @pytest.mark.asyncio
    async def test_character_orchestrator_initialization(self, character_orchestrator):
        """Test that orchestrator initializes with all components."""
        orchestrator = character_orchestrator
        
        # Verify components are loaded
        assert hasattr(orchestrator, 'stats_engine')
        assert hasattr(orchestrator, 'interactions_engine')
        assert hasattr(orchestrator, 'consistency_engine')
        assert hasattr(orchestrator, 'presentation_engine')
        assert hasattr(orchestrator, 'storage')
        
        # Verify component types
        assert isinstance(orchestrator.stats_engine, StatsBehaviorEngine)
        assert isinstance(orchestrator.interactions_engine, InteractionDynamicsEngine)
        assert isinstance(orchestrator.consistency_engine, ConsistencyValidationEngine)
        assert isinstance(orchestrator.presentation_engine, PresentationStyleEngine)
        assert isinstance(orchestrator.storage, CharacterStorage)
        
        # Verify event system setup
        assert len(orchestrator._event_handlers) > 0
    
    @pytest.mark.asyncio
    async def test_end_to_end_character_creation(self, character_orchestrator, sample_character_data):
        """Test complete character creation workflow."""
        orchestrator = character_orchestrator
        character_id = "test_elena_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Verify character was created
        assert character is not None
        assert character.character_id == character_id
        assert character.name == sample_character_data['name']
        
        # Verify all components have data
        stats_data = character.get_component_data('stats')
        assert stats_data is not None
        assert 'intelligence' in stats_data
        
        interactions_data = character.get_component_data('interactions')
        assert interactions_data is not None
        assert 'relationships' in interactions_data
        
        consistency_data = character.get_component_data('consistency')
        assert consistency_data is not None
        
        presentation_data = character.get_component_data('presentation')
        assert presentation_data is not None
    
    @pytest.mark.asyncio
    async def test_component_data_synchronization(self, character_orchestrator, sample_character_data):
        """Test that component data stays synchronized."""
        orchestrator = character_orchestrator
        character_id = "test_sync_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Update stats through orchestrator
        new_stats = {'intelligence': 20, 'charisma': 16}
        await orchestrator.update_character_stats(character_id, new_stats)
        
        # Verify update propagated to storage
        retrieved_character = await orchestrator.get_character(character_id)
        stats_data = retrieved_character.get_component_data('stats')
        assert stats_data['base_stats']['intelligence'] == 20
        assert stats_data['base_stats']['charisma'] == 16
        
        # Verify consistency engine was notified
        consistency_data = retrieved_character.get_component_data('consistency')
        assert 'last_stats_update' in consistency_data
    
    @pytest.mark.asyncio
    async def test_cross_component_interaction(self, character_orchestrator, sample_character_data):
        """Test interactions between different components."""
        orchestrator = character_orchestrator
        character_id = "test_interaction_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Update relationship (should affect consistency tracking)
        relationship_update = {
            'target_character': 'Dr. Marcus',
            'interaction_type': 'positive',
            'outcome': 'trust_increase',
            'magnitude': 0.2
        }
        
        await orchestrator.process_character_interaction(character_id, relationship_update)
        
        # Verify interaction was processed
        interactions_data = character.get_component_data('interactions')
        marcus_relationship = interactions_data['relationships']['Dr. Marcus']
        assert marcus_relationship['trust'] > sample_character_data['relationships']['Dr. Marcus']['trust']
        
        # Verify consistency tracking was updated
        consistency_data = character.get_component_data('consistency')
        assert 'interaction_history' in consistency_data
        assert len(consistency_data['interaction_history']) > 0
    
    # =============================================================================
    # Provider Interface Tests
    # =============================================================================
    
    @pytest.mark.asyncio
    async def test_behavior_provider_interface(self, character_orchestrator, sample_character_data):
        """Test CharacterBehaviorProvider interface implementation."""
        orchestrator = character_orchestrator
        character_id = "test_behavior_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Test behavior context generation
        context = await orchestrator.get_behavior_context(character_id, "investigation_scene")
        
        assert context is not None
        assert 'personality_influence' in context
        assert 'stat_modifiers' in context
        assert 'motivation_context' in context
        
        # Test behavior validation
        proposed_action = {
            'action': 'aggressive_confrontation',
            'target': 'suspect',
            'reasoning': 'Direct approach to get answers'
        }
        
        validation_result = await orchestrator.validate_behavior(character_id, proposed_action)
        assert 'is_valid' in validation_result
        assert 'confidence_score' in validation_result
        assert 'suggestions' in validation_result
    
    @pytest.mark.asyncio
    async def test_state_provider_interface(self, character_orchestrator, sample_character_data):
        """Test CharacterStateProvider interface implementation."""
        orchestrator = character_orchestrator
        character_id = "test_state_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Test state snapshot
        state_snapshot = await orchestrator.get_character_state(character_id)
        
        assert state_snapshot is not None
        assert 'current_stats' in state_snapshot
        assert 'active_relationships' in state_snapshot
        assert 'recent_interactions' in state_snapshot
        assert 'consistency_status' in state_snapshot
        
        # Test state restoration
        # Modify character state
        await orchestrator.update_character_stats(character_id, {'intelligence': 25})
        
        # Restore from snapshot
        restore_result = await orchestrator.restore_character_state(character_id, state_snapshot)
        assert restore_result is True
        
        # Verify restoration
        restored_character = await orchestrator.get_character(character_id)
        restored_stats = restored_character.get_component_data('stats')
        assert restored_stats['base_stats']['intelligence'] == sample_character_data['stats']['intelligence']
    
    @pytest.mark.asyncio
    async def test_validation_provider_interface(self, character_orchestrator, sample_character_data):
        """Test CharacterValidationProvider interface implementation."""
        orchestrator = character_orchestrator
        character_id = "test_validation_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Test validation rules
        validation_rules = await orchestrator.get_validation_rules(character_id)
        
        assert validation_rules is not None
        assert 'personality_constraints' in validation_rules
        assert 'stat_limits' in validation_rules
        assert 'relationship_rules' in validation_rules
        
        # Test constraint validation
        proposed_changes = {
            'personality_shift': {'trait': 'curious', 'new_value': -0.5},  # Dramatic change
            'stat_change': {'intelligence': -10},  # Significant decrease
            'relationship_change': {'Dr. Marcus': {'trust': -0.9}}  # Trust collapse
        }
        
        validation_result = await orchestrator.validate_character_changes(character_id, proposed_changes)
        
        assert 'violations' in validation_result
        assert 'warnings' in validation_result
        assert 'severity_score' in validation_result
        
        # Should flag the dramatic personality and relationship changes
        assert len(validation_result['violations']) > 0 or len(validation_result['warnings']) > 0
    
    # =============================================================================
    # Error Handling and Edge Cases
    # =============================================================================
    
    @pytest.mark.asyncio
    async def test_missing_character_handling(self, character_orchestrator):
        """Test handling of operations on non-existent characters."""
        orchestrator = character_orchestrator
        missing_id = "nonexistent_character"
        
        # Should return None for missing character
        character = await orchestrator.get_character(missing_id)
        assert character is None
        
        # Should handle gracefully without raising exceptions
        context = await orchestrator.get_behavior_context(missing_id, "test_scene")
        assert context is None or context.get('error') is not None
    
    @pytest.mark.asyncio
    async def test_invalid_component_data_handling(self, character_orchestrator, sample_character_data):
        """Test handling of invalid component data."""
        orchestrator = character_orchestrator
        character_id = "test_invalid_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Try to update with invalid stats
        invalid_stats = {'intelligence': 'very smart', 'strength': -5}
        
        update_result = await orchestrator.update_character_stats(character_id, invalid_stats)
        
        # Should handle gracefully and return error info
        assert update_result is not None
        if isinstance(update_result, dict):
            assert 'error' in update_result or 'warnings' in update_result
    
    @pytest.mark.asyncio
    async def test_concurrent_character_operations(self, character_orchestrator, sample_character_data):
        """Test concurrent operations on the same character."""
        orchestrator = character_orchestrator
        character_id = "test_concurrent_001"
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Perform concurrent updates
        async def update_stats():
            return await orchestrator.update_character_stats(character_id, {'intelligence': 19})
        
        async def update_relationship():
            return await orchestrator.process_character_interaction(character_id, {
                'target_character': 'Dr. Marcus',
                'interaction_type': 'positive',
                'outcome': 'trust_increase',
                'magnitude': 0.1
            })
        
        async def check_consistency():
            return await orchestrator.validate_character_consistency(character_id)
        
        # Run operations concurrently
        results = await asyncio.gather(
            update_stats(),
            update_relationship(),
            check_consistency(),
            return_exceptions=True
        )
        
        # Verify no exceptions were raised
        for result in results:
            assert not isinstance(result, Exception)
        
        # Verify final character state is coherent
        final_character = await orchestrator.get_character(character_id)
        assert final_character is not None
        
        # All component data should be present and valid
        stats_data = final_character.get_component_data('stats')
        interactions_data = final_character.get_component_data('interactions')
        consistency_data = final_character.get_component_data('consistency')
        
        assert all([stats_data, interactions_data, consistency_data])
    
    # =============================================================================
    # Performance and Load Tests
    # =============================================================================
    
    @pytest.mark.asyncio
    async def test_multiple_character_management(self, character_orchestrator, sample_character_data):
        """Test managing multiple characters simultaneously."""
        orchestrator = character_orchestrator
        character_count = 5
        
        # Create multiple characters
        characters = []
        for i in range(character_count):
            character_id = f"test_multi_{i:03d}"
            char_data = sample_character_data.copy()
            char_data['name'] = f"Character {i}"
            
            character = await orchestrator.create_character(character_id, char_data)
            characters.append(character)
        
        # Verify all characters were created
        assert len(characters) == character_count
        
        # Test batch operations
        character_ids = [char.character_id for char in characters]
        
        # Get all characters
        retrieved_characters = []
        for char_id in character_ids:
            char = await orchestrator.get_character(char_id)
            retrieved_characters.append(char)
        
        assert len(retrieved_characters) == character_count
        assert all(char is not None for char in retrieved_characters)
        
        # Test character listing
        all_character_ids = await orchestrator.list_characters()
        for char_id in character_ids:
            assert char_id in all_character_ids
    
    @pytest.mark.asyncio
    async def test_storage_persistence(self, character_orchestrator, sample_character_data):
        """Test that character data persists across orchestrator instances."""
        character_id = "test_persistence_001"
        
        # Create character with first orchestrator instance
        orchestrator1 = character_orchestrator
        character = await orchestrator1.create_character(character_id, sample_character_data)
        original_stats = character.get_component_data('stats')
        
        # Create new orchestrator instance with same storage config
        storage_config = orchestrator1.config['storage']
        new_config = {
            'storage': storage_config,
            'components': orchestrator1.config['components']
        }
        orchestrator2 = CharacterOrchestrator(new_config)
        
        # Retrieve character with second orchestrator
        retrieved_character = await orchestrator2.get_character(character_id)
        
        assert retrieved_character is not None
        assert retrieved_character.character_id == character_id
        assert retrieved_character.name == sample_character_data['name']
        
        # Verify component data persisted
        retrieved_stats = retrieved_character.get_component_data('stats')
        assert retrieved_stats['base_stats'] == original_stats['base_stats']
    
    # =============================================================================
    # Event System Tests
    # =============================================================================
    
    @pytest.mark.asyncio
    async def test_cross_component_event_propagation(self, character_orchestrator, sample_character_data):
        """Test that events propagate correctly between components."""
        orchestrator = character_orchestrator
        character_id = "test_events_001"
        
        # Track events
        received_events = []
        
        def event_handler(event_type, event_data):
            received_events.append((event_type, event_data))
        
        # Register event handlers on components
        orchestrator.stats_engine.add_event_handler('stats_updated', event_handler)
        orchestrator.consistency_engine.add_event_handler('consistency_check', event_handler)
        
        # Create character
        character = await orchestrator.create_character(character_id, sample_character_data)
        
        # Update stats (should trigger events)
        await orchestrator.update_character_stats(character_id, {'intelligence': 20})
        
        # Wait for event propagation
        await asyncio.sleep(0.1)
        
        # Verify events were received
        assert len(received_events) > 0
        
        event_types = [event[0] for event in received_events]
        assert 'stats_updated' in event_types
        
        # Some events should reference the character
        character_events = [event for event in received_events if character_id in str(event[1])]
        assert len(character_events) > 0
