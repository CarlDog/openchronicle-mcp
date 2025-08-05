"""
Basic integration validation for character management system.
Tests core functionality of Phase 4.2 component extraction.
"""

import sys
import traceback
from pathlib import Path

def test_basic_imports():
    """Test that all components can be imported."""
    try:
        from core.character_management import (
            CharacterOrchestrator,
            CharacterData,
            CharacterStorage
        )
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.presentation import PresentationStyleEngine
        
        print("✅ All components imported successfully")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        return False

def test_component_instantiation():
    """Test that components can be instantiated."""
    try:
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.presentation import PresentationStyleEngine
        
        # Test component instantiation
        stats_engine = StatsBehaviorEngine({'progression_rate': 1.2})
        interactions_engine = InteractionDynamicsEngine({'max_relationships': 10})
        consistency_engine = ConsistencyValidationEngine({'tolerance': 0.8})
        presentation_engine = PresentationStyleEngine({'default_style': 'neutral'})
        
        print("✅ All components instantiated successfully")
        print(f"   - StatsBehaviorEngine: {type(stats_engine).__name__}")
        print(f"   - InteractionDynamicsEngine: {type(interactions_engine).__name__}")
        print(f"   - ConsistencyValidationEngine: {type(consistency_engine).__name__}")
        print(f"   - PresentationStyleEngine: {type(presentation_engine).__name__}")
        
        return True
        
    except Exception as e:
        print(f"❌ Component instantiation error: {e}")
        traceback.print_exc()
        return False

def test_character_data_creation():
    """Test CharacterData creation and manipulation."""
    try:
        from core.character_management import CharacterData
        
        # Create character data
        character = CharacterData(
            character_id="test_001",
            name="Test Character",
            description="A test character for validation"
        )
        
        # Test component data
        character.set_component_data('stats', {'intelligence': 15, 'charisma': 12})
        character.set_component_data('consistency', {'personality_traits': ['brave', 'curious']})
        
        # Verify data retrieval
        stats_data = character.get_component_data('stats')
        consistency_data = character.get_component_data('consistency')
        
        assert stats_data['intelligence'] == 15
        assert 'brave' in consistency_data['personality_traits']
        
        print("✅ CharacterData creation and manipulation working")
        print(f"   - Character ID: {character.character_id}")
        print(f"   - Name: {character.name}")
        print(f"   - Stats: {stats_data}")
        
        return True
        
    except Exception as e:
        print(f"❌ CharacterData error: {e}")
        traceback.print_exc()
        return False

def test_orchestrator_initialization():
    """Test CharacterOrchestrator initialization."""
    try:
        from core.character_management import CharacterOrchestrator
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.presentation import PresentationStyleEngine
        import tempfile
        
        # Create temporary storage for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "characters"
            storage_path.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
            
            config = {
                'storage': {
                    'storage_path': str(storage_path),  # Use absolute path
                    'cache_enabled': True,
                    'auto_save': True,
                    'backup_enabled': False,  # Disable backup for simple test
                    'max_cache_size': 100
                },
                'components': {
                    'stats': {'progression_rate': 1.2},
                    'interactions': {'max_relationships': 10},
                    'consistency': {'tolerance': 0.8},
                    'presentation': {'default_style': 'neutral'}
                }
            }
            
            # Initialize orchestrator
            orchestrator = CharacterOrchestrator(config)
            
            # Manually register components for testing
            orchestrator.register_component('stats', StatsBehaviorEngine(config['components']['stats']))
            orchestrator.register_component('interactions', InteractionDynamicsEngine(config['components']['interactions']))
            orchestrator.register_component('consistency', ConsistencyValidationEngine(config['components']['consistency']))
            orchestrator.register_component('presentation', PresentationStyleEngine(config['components']['presentation']))
            
            # Verify components are present
            assert hasattr(orchestrator, 'storage')
            assert 'stats' in orchestrator.components
            assert 'interactions' in orchestrator.components
            assert 'consistency' in orchestrator.components
            assert 'presentation' in orchestrator.components
            
            print("✅ CharacterOrchestrator initialization successful")
            print(f"   - Storage system: {type(orchestrator.storage).__name__}")
            print(f"   - Registered components: {list(orchestrator.components.keys())}")
            print(f"   - State providers: {len(orchestrator.state_providers)}")
            print(f"   - Behavior providers: {len(orchestrator.behavior_providers)}")
            print(f"   - Validation providers: {len(orchestrator.validation_providers)}")
            
            return True
            
    except Exception as e:
        print(f"❌ CharacterOrchestrator error: {e}")
        traceback.print_exc()
        return False

def run_phase_4_2_validation():
    """Run complete Phase 4.2 validation suite."""
    print("🚀 Phase 4.2 Component Extraction Validation")
    print("=" * 50)
    
    tests = [
        ("Import Validation", test_basic_imports),
        ("Component Instantiation", test_component_instantiation),
        ("CharacterData Operations", test_character_data_creation),
        ("Orchestrator Initialization", test_orchestrator_initialization)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        print("-" * 30)
        
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 PHASE 4.2 VALIDATION RESULTS")
    print(f"   Tests Passed: {passed}/{total}")
    print(f"   Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 PHASE 4.2 COMPONENT EXTRACTION SUCCESSFUL!")
        print("✅ Ready to proceed to Phase 4.3 Integration Testing")
    else:
        print("⚠️  Some tests failed - investigate before proceeding")
    
    return passed == total

if __name__ == "__main__":
    success = run_phase_4_2_validation()
    sys.exit(0 if success else 1)
