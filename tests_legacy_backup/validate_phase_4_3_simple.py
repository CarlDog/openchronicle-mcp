"""
Simplified Phase 4.3 integration test to debug issues step by step.
"""

import sys
import traceback
import tempfile
from pathlib import Path

def test_basic_orchestrator_setup():
    """Test basic orchestrator setup with all components."""
    try:
        print("🧪 Testing Basic Orchestrator Setup...")
        
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
            print(f"   ✅ Orchestrator created")
            
            # Register components one by one and test
            stats_engine = StatsBehaviorEngine(config['components']['stats'])
            orchestrator.register_component('stats', stats_engine)
            print(f"   ✅ Stats engine registered")
            
            interactions_engine = InteractionDynamicsEngine(config['components']['interactions'])
            orchestrator.register_component('interactions', interactions_engine)
            print(f"   ✅ Interactions engine registered")
            
            consistency_engine = ConsistencyValidationEngine(config['components']['consistency'])
            orchestrator.register_component('consistency', consistency_engine)
            print(f"   ✅ Consistency engine registered")
            
            presentation_engine = PresentationStyleEngine(config['components']['presentation'])
            orchestrator.register_component('presentation', presentation_engine)
            print(f"   ✅ Presentation engine registered")
            
            print(f"   📊 Total components: {len(orchestrator.components)}")
            print(f"   📊 Component names: {list(orchestrator.components.keys())}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Setup error: {e}")
        traceback.print_exc()
        return False

def test_simple_character_creation():
    """Test simple character creation without complex data."""
    try:
        print("\n🧪 Testing Simple Character Creation...")
        
        from core.character_management import CharacterOrchestrator
        from core.character_management.stats import StatsBehaviorEngine
        
        # Minimal setup
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "characters"
            storage_path.mkdir(parents=True, exist_ok=True)
            
            config = {
                'storage': {'storage_path': str(storage_path), 'cache_enabled': True}
            }
            
            orchestrator = CharacterOrchestrator(config)
            stats_engine = StatsBehaviorEngine({'progression_rate': 1.2})
            orchestrator.register_component('stats', stats_engine)
            
            # Simple character data
            character_data = {
                'name': 'Simple Test',
                'description': 'A simple test character'
            }
            
            character_id = "simple_001"
            character = orchestrator.create_character(character_id, character_data)
            
            print(f"   ✅ Character created: {character.name}")
            print(f"   📝 Character ID: {character.character_id}")
            
            # Test retrieval
            retrieved = orchestrator.get_character(character_id)
            print(f"   ✅ Character retrieved: {retrieved.name if retrieved else 'None'}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Character creation error: {e}")
        traceback.print_exc()
        return False

def test_character_data_operations():
    """Test CharacterData class operations in isolation."""
    try:
        print("\n🧪 Testing CharacterData Operations...")
        
        from core.character_management import CharacterData
        
        # Create character data
        character = CharacterData(
            character_id="data_test_001",
            name="Data Test Character",
            description="Testing character data operations"
        )
        
        print(f"   ✅ CharacterData created: {character.name}")
        
        # Test component data setting/getting
        character.set_component_data('stats', {'intelligence': 15, 'strength': 12})
        stats_data = character.get_component_data('stats')
        
        print(f"   ✅ Component data set and retrieved")
        print(f"   📊 Stats data: {stats_data}")
        
        # Test serialization
        data_dict = character.to_dict()
        print(f"   ✅ Serialized to dict: {len(data_dict)} keys")
        
        # Test deserialization
        new_character = CharacterData.from_dict(data_dict)
        print(f"   ✅ Deserialized: {new_character.name}")
        
        # Verify data integrity
        new_stats = new_character.get_component_data('stats')
        assert new_stats['intelligence'] == 15
        print(f"   ✅ Data integrity verified")
        
        return True
        
    except Exception as e:
        print(f"   ❌ CharacterData error: {e}")
        traceback.print_exc()
        return False

def test_component_engines_individually():
    """Test each component engine individually."""
    try:
        print("\n🧪 Testing Component Engines Individually...")
        
        from core.character_management.stats import StatsBehaviorEngine
        from core.character_management.interactions import InteractionDynamicsEngine
        from core.character_management.consistency import ConsistencyValidationEngine
        from core.character_management.presentation import PresentationStyleEngine
        
        character_id = "component_test_001"
        results = []
        
        # Test StatsBehaviorEngine
        try:
            stats_engine = StatsBehaviorEngine({'progression_rate': 1.2})
            stats_engine.initialize_character(character_id, intelligence=15, strength=12)
            stats_data = stats_engine.get_character_data(character_id)
            results.append(f"Stats engine: {bool(stats_data)}")
        except Exception as e:
            results.append(f"Stats engine: ERROR - {e}")
        
        # Test InteractionDynamicsEngine
        try:
            interactions_engine = InteractionDynamicsEngine({'max_relationships': 10})
            interactions_engine.initialize_character(character_id, name="Test Character")
            interactions_data = interactions_engine.get_character_data(character_id)
            results.append(f"Interactions engine: {bool(interactions_data)}")
        except Exception as e:
            results.append(f"Interactions engine: ERROR - {e}")
        
        # Test ConsistencyValidationEngine
        try:
            consistency_engine = ConsistencyValidationEngine({'tolerance': 0.8})
            consistency_engine.initialize_character(character_id, personality_traits=['brave'])
            consistency_data = consistency_engine.get_character_data(character_id)
            results.append(f"Consistency engine: {bool(consistency_data)}")
        except Exception as e:
            results.append(f"Consistency engine: ERROR - {e}")
        
        # Test PresentationStyleEngine
        try:
            presentation_engine = PresentationStyleEngine({'default_style': 'neutral'})
            presentation_engine.initialize_character(character_id, style_profile='heroic')
            presentation_data = presentation_engine.get_character_data(character_id)
            results.append(f"Presentation engine: {bool(presentation_data)}")
        except Exception as e:
            results.append(f"Presentation engine: ERROR - {e}")
        
        print("   📊 Component test results:")
        for result in results:
            print(f"     - {result}")
        
        # Check if all succeeded
        all_success = all('ERROR' not in result for result in results)
        
        if all_success:
            print("   ✅ All component engines working")
        else:
            print("   ⚠️  Some component engines had issues")
        
        return all_success
        
    except Exception as e:
        print(f"   ❌ Component engine error: {e}")
        traceback.print_exc()
        return False

def run_simplified_integration():
    """Run simplified integration testing."""
    print("🚀 Simplified Phase 4.3 Integration Testing")
    print("=" * 50)
    
    tests = [
        ("Basic Orchestrator Setup", test_basic_orchestrator_setup),
        ("Simple Character Creation", test_simple_character_creation),
        ("CharacterData Operations", test_character_data_operations),
        ("Component Engines Individual", test_component_engines_individually)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"📊 SIMPLIFIED INTEGRATION RESULTS")
    print(f"   Tests Passed: {passed}/{total}")
    print(f"   Success Rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("🎉 BASIC INTEGRATION WORKING!")
        print("✅ Ready for advanced integration testing")
    else:
        print("⚠️  Basic integration issues found")
    
    return passed == total

if __name__ == "__main__":
    success = run_simplified_integration()
    sys.exit(0 if success else 1)
