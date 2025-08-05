"""
Phase 4.3: Character Engine Integration Testing

Tests the complete integration of the new modular character management system
and validates migration from legacy character engines.
"""

import sys
import traceback
import tempfile
import asyncio
from pathlib import Path
from typing import Dict, Any

def test_character_lifecycle():
    """Test complete character creation, management, and deletion lifecycle."""
    try:
        print("🧪 Testing Character Lifecycle...")
        
        from core.character_management import CharacterOrchestrator
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.presentation import PresentationStyleEngine
        
        # Setup orchestrator
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "characters"
            storage_path.mkdir(parents=True, exist_ok=True)
            
            config = {
                'storage': {'storage_path': str(storage_path), 'cache_enabled': True},
                'components': {
                    'stats': {'progression_rate': 1.2},
                    'interactions': {'max_relationships': 10},
                    'consistency': {'tolerance': 0.8},
                    'presentation': {'default_style': 'neutral'}
                }
            }
            
            orchestrator = CharacterOrchestrator(config)
            
            # Register components
            orchestrator.register_component('stats', StatsBehaviorEngine(config['components']['stats']))
            orchestrator.register_component('interactions', InteractionDynamicsEngine(config['components']['interactions']))
            orchestrator.register_component('consistency', ConsistencyValidationEngine(config['components']['consistency']))
            orchestrator.register_component('presentation', PresentationStyleEngine(config['components']['presentation']))
            
            # Test character creation
            character_data = {
                'name': 'Elena Vasquez',
                'description': 'A brilliant scientist with a mysterious past',
                'personality_traits': ['intelligent', 'curious', 'secretive'],
                'stats': {'intelligence': 18, 'charisma': 14, 'perception': 16}
            }
            
            character_id = "test_elena_001"
            character = orchestrator.create_character(character_id, character_data)
            
            assert character is not None
            assert character.character_id == character_id
            assert character.name == 'Elena Vasquez'
            
            # Test character retrieval
            retrieved = orchestrator.get_character(character_id)
            assert retrieved is not None
            assert retrieved.character_id == character_id
            
            # Test character listing
            character_list = orchestrator.storage.list_characters()
            assert character_id in character_list
            
            # Test character deletion
            delete_success = orchestrator.delete_character(character_id)
            assert delete_success
            
            # Verify deletion
            deleted_character = orchestrator.get_character(character_id)
            assert deleted_character is None
            
            print("   ✅ Character lifecycle complete!")
            print(f"   - Created character: {character_id}")
            print(f"   - Retrieved character: {retrieved.name if retrieved else 'None'}")
            print(f"   - Listed characters: {len(character_list)}")
            print(f"   - Deleted successfully: {delete_success}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Character lifecycle error: {e}")
        traceback.print_exc()
        return False

def test_component_interaction():
    """Test interaction between different character components."""
    try:
        print("\n🧪 Testing Component Interaction...")
        
        from core.character_management import CharacterOrchestrator, CharacterData
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.presentation import PresentationStyleEngine
        
        # Setup orchestrator
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "characters"
            storage_path.mkdir(parents=True, exist_ok=True)
            
            config = {
                'storage': {'storage_path': str(storage_path), 'cache_enabled': True},
                'components': {
                    'stats': {'progression_rate': 1.2},
                    'interactions': {'max_relationships': 10},
                    'consistency': {'tolerance': 0.8},
                    'presentation': {'default_style': 'neutral'}
                }
            }
            
            orchestrator = CharacterOrchestrator(config)
            
            # Register components
            stats_engine = StatsBehaviorEngine(config['components']['stats'])
            interactions_engine = InteractionDynamicsEngine(config['components']['interactions'])
            consistency_engine = ConsistencyValidationEngine(config['components']['consistency'])
            presentation_engine = PresentationStyleEngine(config['components']['presentation'])
            
            orchestrator.register_component('stats', stats_engine)
            orchestrator.register_component('interactions', interactions_engine)
            orchestrator.register_component('consistency', consistency_engine)
            orchestrator.register_component('presentation', presentation_engine)
            
            # Create character
            character_id = "test_interaction_001"
            character_data = {
                'name': 'Test Character',
                'description': 'A character for testing component interactions',
                'stats': {'intelligence': 15, 'charisma': 12, 'strength': 10}
            }
            
            character = orchestrator.create_character(character_id, character_data)
            
            # Test component data access
            character.set_component_data('stats', {'intelligence': 15, 'charisma': 12})
            character.set_component_data('interactions', {'relationships': {}})
            character.set_component_data('consistency', {'personality_traits': ['brave', 'loyal']})
            character.set_component_data('presentation', {'style_profile': 'heroic'})
            
            # Save changes
            orchestrator.storage.save_character(character_id)
            
            # Retrieve and verify
            retrieved = orchestrator.get_character(character_id)
            
            stats_data = retrieved.get_component_data('stats')
            interactions_data = retrieved.get_component_data('interactions')
            consistency_data = retrieved.get_component_data('consistency')
            presentation_data = retrieved.get_component_data('presentation')
            
            assert stats_data is not None
            assert interactions_data is not None
            assert consistency_data is not None
            assert presentation_data is not None
            
            print("   ✅ Component interaction successful!")
            print(f"   - Stats data: {bool(stats_data)}")
            print(f"   - Interactions data: {bool(interactions_data)}")
            print(f"   - Consistency data: {bool(consistency_data)}")
            print(f"   - Presentation data: {bool(presentation_data)}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Component interaction error: {e}")
        traceback.print_exc()
        return False

def test_provider_interfaces():
    """Test the provider interface pattern implementation."""
    try:
        print("\n🧪 Testing Provider Interfaces...")
        
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.character_base import (
            CharacterStateProvider,
            CharacterBehaviorProvider,
            CharacterValidationProvider
        )
        
        # Test component interfaces
        stats_engine = StatsBehaviorEngine({'progression_rate': 1.2})
        interactions_engine = InteractionDynamicsEngine({'max_relationships': 10})
        consistency_engine = ConsistencyValidationEngine({'tolerance': 0.8})
        
        # Test interface implementation
        interface_tests = []
        
        # Check if engines implement expected interfaces
        if hasattr(stats_engine, 'get_behavior_context'):
            interface_tests.append("StatsBehaviorEngine implements behavior provider")
        
        if hasattr(interactions_engine, 'get_character_state'):
            interface_tests.append("InteractionDynamicsEngine implements state provider")
        
        if hasattr(consistency_engine, 'validate_character_changes'):
            interface_tests.append("ConsistencyValidationEngine implements validation provider")
        
        # Test component initialization
        character_id = "test_provider_001"
        
        stats_engine.initialize_character(character_id, intelligence=15, charisma=12)
        interactions_engine.initialize_character(character_id, name="Test Character")
        consistency_engine.initialize_character(character_id, personality_traits=['brave'])
        
        # Test data retrieval
        stats_data = stats_engine.get_character_data(character_id)
        interactions_data = interactions_engine.get_character_data(character_id)
        consistency_data = consistency_engine.get_character_data(character_id)
        
        assert stats_data is not None
        assert interactions_data is not None
        assert consistency_data is not None
        
        print("   ✅ Provider interfaces working!")
        print(f"   - Interface implementations: {len(interface_tests)}")
        for test in interface_tests:
            print(f"     * {test}")
        print(f"   - Data retrieval successful: stats={bool(stats_data)}, interactions={bool(interactions_data)}, consistency={bool(consistency_data)}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Provider interface error: {e}")
        traceback.print_exc()
        return False

def test_legacy_compatibility():
    """Test compatibility with existing character data structures."""
    try:
        print("\n🧪 Testing Legacy Compatibility...")
        
        from core.character_management import CharacterData
        
        # Test with legacy-style data
        legacy_data = {
            'character_id': 'legacy_001',
            'name': 'Legacy Character',
            'description': 'A character from the old system',
            'stats': {
                'strength': 14,
                'intelligence': 16,
                'charisma': 12,
                'perception': 15
            },
            'relationships': {
                'ally_001': {'type': 'friend', 'trust_level': 0.8},
                'enemy_001': {'type': 'rival', 'trust_level': 0.2}
            },
            'personality_traits': ['brave', 'curious', 'loyal'],
            'style_preferences': {
                'writing_style': 'descriptive',
                'dialogue_style': 'formal'
            }
        }
        
        # Create CharacterData from legacy format
        character = CharacterData(
            character_id=legacy_data['character_id'],
            name=legacy_data['name'],
            description=legacy_data['description']
        )
        
        # Set component data from legacy structure
        character.set_component_data('stats', legacy_data['stats'])
        character.set_component_data('interactions', {'relationships': legacy_data['relationships']})
        character.set_component_data('consistency', {'personality_traits': legacy_data['personality_traits']})
        character.set_component_data('presentation', {'style_preferences': legacy_data['style_preferences']})
        
        # Test serialization
        exported_data = character.to_dict()
        
        # Test deserialization
        imported_character = CharacterData.from_dict(exported_data)
        
        assert imported_character.character_id == legacy_data['character_id']
        assert imported_character.name == legacy_data['name']
        
        # Test component data preservation
        imported_stats = imported_character.get_component_data('stats')
        imported_relationships = imported_character.get_component_data('interactions')
        
        assert imported_stats['strength'] == 14
        assert imported_relationships['relationships']['ally_001']['trust_level'] == 0.8
        
        print("   ✅ Legacy compatibility working!")
        print(f"   - Legacy character: {imported_character.name}")
        print(f"   - Stats preserved: {bool(imported_stats)}")
        print(f"   - Relationships preserved: {bool(imported_relationships)}")
        print(f"   - Serialization/deserialization: ✅")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Legacy compatibility error: {e}")
        traceback.print_exc()
        return False

def run_phase_4_3_integration():
    """Run complete Phase 4.3 integration testing."""
    print("🚀 Phase 4.3: Character Engine Integration Testing")
    print("=" * 60)
    
    tests = [
        ("Character Lifecycle", test_character_lifecycle),
        ("Component Interaction", test_component_interaction),
        ("Provider Interfaces", test_provider_interfaces),
        ("Legacy Compatibility", test_legacy_compatibility)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        
        if test_func():
            passed += 1
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 60)
    print(f"📊 PHASE 4.3 INTEGRATION RESULTS")
    print(f"   Tests Passed: {passed}/{total}")
    print(f"   Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 PHASE 4.3 INTEGRATION TESTING SUCCESSFUL!")
        print("✅ Ready to proceed to legacy character engine migration")
        print("✅ Component extraction and integration validated")
        print("✅ Provider pattern implementation confirmed")
        print("✅ Legacy compatibility maintained")
    else:
        print("⚠️  Some integration tests failed - investigate before migration")
    
    return passed == total

if __name__ == "__main__":
    success = run_phase_4_3_integration()
    sys.exit(0 if success else 1)
