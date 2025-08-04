"""
Test script for Phase 6 Narrative Systems Foundation

Validates the basic orchestrator setup and shared components.
"""

import sys
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_narrative_orchestrator():
    """Test basic narrative orchestrator functionality."""
    print("Testing NarrativeOrchestrator...")
    
    try:
        from core.narrative_systems import NarrativeOrchestrator, NarrativeState
        
        # Initialize orchestrator
        orchestrator = NarrativeOrchestrator("storage/temp/test_narrative")
        print("✅ NarrativeOrchestrator initialized successfully")
        
        # Test state management
        story_id = "test_story_001"
        success = orchestrator.update_narrative_state(
            story_id,
            current_scene="intro",
            narrative_tension=0.7
        )
        print(f"✅ State update: {success}")
        
        # Get state
        state = orchestrator.get_narrative_state(story_id)
        print(f"✅ Retrieved state: {state.story_id if state else 'None'}")
        
        # Test operation processing (placeholder)
        operation = orchestrator.process_narrative_operation(
            "response.analyze_context",
            story_id,
            {"context": "test context"}
        )
        print(f"✅ Operation processed: {operation.success}")
        
        # Get system status
        status = orchestrator.get_system_status()
        print(f"✅ System status - Active stories: {status['active_stories']}")
        
        return True
        
    except Exception as e:
        print(f"❌ NarrativeOrchestrator test failed: {e}")
        return False

def test_shared_components():
    """Test shared narrative components."""
    print("\nTesting shared components...")
    
    try:
        from core.narrative_systems.shared import ValidationBase, StateManager
        
        # Test validation
        result = ValidationBase.validate_required_fields(
            {"name": "test", "value": 123},
            ["name", "value", "missing"]
        )
        print(f"✅ Validation result: {result.is_valid} (expected False)")
        
        # Test state manager
        state_manager = StateManager()
        state_manager.set_state("test", {"data": "value"})
        retrieved = state_manager.get_state("test")
        print(f"✅ State manager: {retrieved['data'] if retrieved else 'None'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Shared components test failed: {e}")
        return False

def main():
    """Run all foundation tests."""
    print("Phase 6 Narrative Systems Foundation Test")
    print("=" * 50)
    
    tests = [
        test_narrative_orchestrator,
        test_shared_components
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 Phase 6 foundation ready for component integration!")
        return True
    else:
        print("⚠️ Some tests failed - check implementation")
        return False

if __name__ == "__main__":
    main()
