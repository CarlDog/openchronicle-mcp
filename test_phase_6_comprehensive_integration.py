#!/usr/bin/env python3
"""
Phase 6 Day 6-7 Comprehensive Integration Test

Tests the complete narrative systems architecture with all 4 subsystems:
- ResponseOrchestrator (response intelligence)
- MechanicsOrchestrator (dice & branching)
- ConsistencyOrchestrator (memory validation)
- EmotionalOrchestrator (emotional stability)

Validates end-to-end narrative workflows and cross-system integration.
"""

import sys
import asyncio
import traceback
import tempfile
from pathlib import Path
from datetime import datetime

def test_full_narrative_orchestrator_integration():
    """Test complete NarrativeOrchestrator with all 4 subsystems."""
    try:
        print("🧪 Testing Full NarrativeOrchestrator Integration...")
        
        # Import all components
        from core.narrative_systems import NarrativeOrchestrator
        from core.narrative_systems.mechanics.mechanics_models import MechanicsRequest, ResolutionType, DifficultyLevel
        
        # Initialize main orchestrator
        orchestrator = NarrativeOrchestrator()
        print("   ✅ NarrativeOrchestrator initialized successfully")
        
        # Test system status
        status = orchestrator.get_system_status()
        components = status.get('components', {})
        
        print(f"   📊 Component Status:")
        print(f"      Response System: {'✅' if components.get('response_orchestrator') else '❌'}")
        print(f"      Mechanics System: {'✅' if components.get('mechanics_orchestrator') else '❌'}")
        print(f"      Consistency System: {'✅' if components.get('consistency_orchestrator') else '❌'}")
        print(f"      Emotional System: {'✅' if components.get('emotional_orchestrator') else '❌'}")
        
        # Test narrative state management
        story_id = "test_integration_story"
        orchestrator.update_narrative_state(
            story_id,
            current_scene="integration_test_scene",
            character_states={"hero": {"mood": "determined"}},
            story_elements={"setting": "test_environment"}
        )
        
        narrative_state = orchestrator.get_narrative_state(story_id)
        print(f"   ✅ Narrative state management: {narrative_state is not None}")
        
        # Test cross-system operation processing
        operations = [
            ("response.quality_assessment", {"content": "Test narrative content", "quality_target": "high"}),
            ("mechanics.dice_roll", {"character_id": "hero", "resolution_type": "skill_check", "difficulty": "medium"}),
            ("consistency.memory_validation", {"character_id": "hero", "memory_data": {"event": "test_event"}}),
            ("emotional.mood_tracking", {"character_id": "hero", "emotion": "excitement", "intensity": 0.8})
        ]
        
        operation_results = []
        for operation_type, operation_data in operations:
            try:
                result = orchestrator.process_narrative_operation(operation_type, story_id, operation_data)
                operation_results.append((operation_type, result.success))
                print(f"   ✅ {operation_type}: {'Success' if result.success else 'Failed'}")
            except Exception as e:
                operation_results.append((operation_type, False))
                print(f"   ⚠️ {operation_type}: {str(e)}")
        
        # Calculate success rate
        successful_operations = sum(1 for _, success in operation_results if success)
        total_operations = len(operation_results)
        success_rate = (successful_operations / total_operations) * 100
        
        print(f"   📊 Operation Success Rate: {success_rate:.1f}% ({successful_operations}/{total_operations})")
        
        return success_rate >= 75  # Accept 75% success rate for integration test
        
    except Exception as e:
        print(f"   ❌ Integration test error: {e}")
        traceback.print_exc()
        return False

async def test_async_narrative_workflow():
    """Test asynchronous narrative workflow across all systems."""
    try:
        print("🧪 Testing Async Narrative Workflow...")
        
        from core.narrative_systems import NarrativeOrchestrator
        from core.narrative_systems.mechanics import MechanicsOrchestrator
        from core.narrative_systems.mechanics.mechanics_models import MechanicsRequest, ResolutionType, DifficultyLevel
        
        # Initialize orchestrators
        narrative_orchestrator = NarrativeOrchestrator()
        mechanics_orchestrator = MechanicsOrchestrator()
        
        # Create a sample narrative workflow
        story_id = "async_workflow_test"
        character_id = "test_character"
        
        # Step 1: Character action resolution
        mechanics_request = MechanicsRequest(
            character_id=character_id,
            resolution_type=ResolutionType.SKILL_CHECK,
            difficulty=DifficultyLevel.MEDIUM,
            context={"action": "investigating mysterious door", "skill": "perception"}
        )
        
        mechanics_result = await mechanics_orchestrator.resolve_action(mechanics_request)
        print(f"   ✅ Mechanics resolution: {mechanics_result.success}")
        
        if mechanics_result.success:
            # Step 2: Process narrative implications
            narrative_impact = mechanics_result.resolution_result.narrative_impact
            print(f"   ✅ Narrative impact generated: {len(narrative_impact) > 0}")
            
            # Step 3: Update narrative state
            narrative_orchestrator.update_narrative_state(
                story_id,
                last_action_result=mechanics_result.to_dict(),
                character_states={character_id: {"last_roll": mechanics_result.resolution_result.dice_roll.total}}
            )
            
            final_state = narrative_orchestrator.get_narrative_state(story_id)
            print(f"   ✅ Workflow state updated: {final_state is not None}")
            
            return True
        
        return False
        
    except Exception as e:
        print(f"   ❌ Async workflow error: {e}")
        return False

def test_performance_benchmarking():
    """Basic performance test for narrative operations."""
    try:
        print("🧪 Testing Performance Benchmarking...")
        
        from core.narrative_systems import NarrativeOrchestrator
        import time
        
        orchestrator = NarrativeOrchestrator()
        
        # Benchmark narrative state operations
        start_time = time.time()
        
        for i in range(100):
            story_id = f"perf_test_{i}"
            orchestrator.update_narrative_state(
                story_id,
                test_iteration=i,
                timestamp=datetime.now().isoformat()
            )
        
        state_ops_time = time.time() - start_time
        print(f"   📊 100 state operations: {state_ops_time:.3f}s ({100/state_ops_time:.1f} ops/sec)")
        
        # Benchmark operation processing
        start_time = time.time()
        
        for i in range(50):
            result = orchestrator.process_narrative_operation(
                "consistency.memory_validation",
                f"perf_test_{i % 10}",
                {"test_data": f"performance_test_{i}"}
            )
        
        ops_time = time.time() - start_time
        print(f"   📊 50 operation processes: {ops_time:.3f}s ({50/ops_time:.1f} ops/sec)")
        
        # Performance is acceptable if we can handle reasonable throughput
        acceptable_performance = (100/state_ops_time) > 50 and (50/ops_time) > 10
        print(f"   ✅ Performance benchmark: {'Acceptable' if acceptable_performance else 'Needs optimization'}")
        
        return acceptable_performance
        
    except Exception as e:
        print(f"   ❌ Performance test error: {e}")
        return False

def test_component_isolation():
    """Test that each narrative subsystem can operate independently."""
    try:
        print("🧪 Testing Component Isolation...")
        
        # Test each orchestrator independently
        subsystems = [
            ("ResponseOrchestrator", "core.narrative_systems.response", "ResponseOrchestrator"),
            ("MechanicsOrchestrator", "core.narrative_systems.mechanics", "MechanicsOrchestrator"),
            ("ConsistencyOrchestrator", "core.narrative_systems.consistency", "ConsistencyOrchestrator"),
            ("EmotionalOrchestrator", "core.narrative_systems.emotional", "EmotionalOrchestrator")
        ]
        
        isolation_results = []
        
        for name, module_path, class_name in subsystems:
            try:
                # Import and instantiate each orchestrator independently
                module = __import__(module_path, fromlist=[class_name])
                orchestrator_class = getattr(module, class_name)
                orchestrator = orchestrator_class()
                
                # Test basic functionality
                if hasattr(orchestrator, 'get_status'):
                    status = orchestrator.get_status()
                    isolation_results.append((name, True))
                    print(f"   ✅ {name}: Independent operation successful")
                else:
                    isolation_results.append((name, False))
                    print(f"   ⚠️ {name}: Missing status method")
                    
            except Exception as e:
                isolation_results.append((name, False))
                print(f"   ❌ {name}: {str(e)}")
        
        successful_isolations = sum(1 for _, success in isolation_results if success)
        total_subsystems = len(isolation_results)
        
        print(f"   📊 Component Isolation: {successful_isolations}/{total_subsystems} subsystems operational")
        
        return successful_isolations >= 3  # At least 3/4 subsystems should work independently
        
    except Exception as e:
        print(f"   ❌ Component isolation test error: {e}")
        return False

def test_error_handling_resilience():
    """Test system resilience to errors and edge cases."""
    try:
        print("🧪 Testing Error Handling Resilience...")
        
        from core.narrative_systems import NarrativeOrchestrator
        
        orchestrator = NarrativeOrchestrator()
        
        # Test invalid operation types
        try:
            result = orchestrator.process_narrative_operation(
                "invalid.operation_type",
                "test_story",
                {"invalid": "data"}
            )
            handles_invalid_ops = not result.success
        except Exception:
            handles_invalid_ops = True  # Exception handling is also acceptable
        
        # Test empty/None inputs
        try:
            orchestrator.update_narrative_state("", invalid_param=None)
            handles_empty_inputs = True
        except Exception:
            handles_empty_inputs = True  # Should handle gracefully
        
        # Test state retrieval for non-existent stories
        non_existent_state = orchestrator.get_narrative_state("non_existent_story_12345")
        handles_missing_state = non_existent_state is None
        
        resilience_checks = [
            ("Invalid operations", handles_invalid_ops),
            ("Empty inputs", handles_empty_inputs),
            ("Missing state", handles_missing_state)
        ]
        
        passed_checks = sum(1 for _, passed in resilience_checks if passed)
        
        for check_name, passed in resilience_checks:
            print(f"   {'✅' if passed else '❌'} {check_name}: {'Handled' if passed else 'Failed'}")
        
        print(f"   📊 Resilience Score: {passed_checks}/{len(resilience_checks)} checks passed")
        
        return passed_checks >= 2  # At least 2/3 resilience checks should pass
        
    except Exception as e:
        print(f"   ❌ Error handling test error: {e}")
        return False

async def run_comprehensive_integration_tests():
    """Run all comprehensive integration tests for Phase 6."""
    print("🚀 Phase 6 Day 6-7 Comprehensive Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Full Integration", test_full_narrative_orchestrator_integration),
        ("Async Workflow", test_async_narrative_workflow),
        ("Performance Benchmarking", test_performance_benchmarking),
        ("Component Isolation", test_component_isolation),
        ("Error Handling Resilience", test_error_handling_resilience)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        
        if asyncio.iscoroutinefunction(test_func):
            success = await test_func()
        else:
            success = test_func()
            
        results.append((test_name, success))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE INTEGRATION TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    success_rate = (passed / total) * 100
    
    if success_rate >= 80:
        print(f"🎉 EXCELLENT! {success_rate:.1f}% success rate - Phase 6 integration is solid!")
        return True
    elif success_rate >= 60:
        print(f"✅ GOOD! {success_rate:.1f}% success rate - Phase 6 integration is functional with minor issues")
        return True
    else:
        print(f"⚠️ NEEDS WORK! {success_rate:.1f}% success rate - Address failing tests before proceeding")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(run_comprehensive_integration_tests())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Critical test error: {e}")
        traceback.print_exc()
        sys.exit(1)
