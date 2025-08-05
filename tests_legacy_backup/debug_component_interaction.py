"""
Debug the component interaction test specifically
"""

import sys
import traceback
import tempfile
from pathlib import Path

def debug_component_interaction():
    """Debug the component interaction test."""
    try:
        print("🔍 Debugging Component Interaction...")
        
        from core.character_management import CharacterOrchestrator, CharacterData
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.presentation import PresentationStyleEngine
        
        # Setup orchestrator (same as working tests)
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
            print("   ✅ Orchestrator created")
            
            # Register components
            stats_engine = StatsBehaviorEngine(config['components']['stats'])
            interactions_engine = InteractionDynamicsEngine(config['components']['interactions'])
            consistency_engine = ConsistencyValidationEngine(config['components']['consistency'])
            presentation_engine = PresentationStyleEngine(config['components']['presentation'])
            
            orchestrator.register_component('stats', stats_engine)
            orchestrator.register_component('interactions', interactions_engine)
            orchestrator.register_component('consistency', consistency_engine)
            orchestrator.register_component('presentation', presentation_engine)
            print("   ✅ All components registered")
            
            # Create character (simple version first)
            character_id = "test_interaction_001"
            character_data = {
                'name': 'Test Character',
                'description': 'A character for testing component interactions'
            }
            
            character = orchestrator.create_character(character_id, character_data)
            print(f"   ✅ Character created: {character.name}")
            
            # Test component data access (step by step)
            print("   🔧 Testing component data operations...")
            
            # Set component data individually
            character.set_component_data('stats', {'intelligence': 15, 'charisma': 12})
            print("   ✅ Stats data set")
            
            character.set_component_data('interactions', {'relationships': {}})
            print("   ✅ Interactions data set")
            
            character.set_component_data('consistency', {'personality_traits': ['brave', 'loyal']})
            print("   ✅ Consistency data set")
            
            character.set_component_data('presentation', {'style_profile': 'heroic'})
            print("   ✅ Presentation data set")
            
            # Save changes
            save_result = orchestrator.storage.save_character(character_id)
            print(f"   ✅ Character saved: {save_result}")
            
            # Retrieve and verify (step by step)
            print("   🔧 Testing data retrieval...")
            
            retrieved = orchestrator.get_character(character_id)
            if not retrieved:
                print("   ❌ Character retrieval failed!")
                return False
            
            print(f"   ✅ Character retrieved: {retrieved.name}")
            
            # Test each component data retrieval
            stats_data = retrieved.get_component_data('stats')
            print(f"   📊 Stats data: {stats_data}")
            
            interactions_data = retrieved.get_component_data('interactions')
            print(f"   📊 Interactions data: {interactions_data}")
            
            consistency_data = retrieved.get_component_data('consistency')
            print(f"   📊 Consistency data: {consistency_data}")
            
            presentation_data = retrieved.get_component_data('presentation')
            print(f"   📊 Presentation data: {presentation_data}")
            
            # Verify all data is present
            assert stats_data is not None, "Stats data should not be None"
            assert interactions_data is not None, "Interactions data should not be None"
            assert consistency_data is not None, "Consistency data should not be None"
            assert presentation_data is not None, "Presentation data should not be None"
            
            print("   ✅ Component interaction debugging complete!")
            return True
            
    except Exception as e:
        print(f"   ❌ Component interaction error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    debug_component_interaction()
