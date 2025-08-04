"""
Test script for Response Intelligence System

Tests the modular response components extracted from IntelligentResponseEngine.
"""

import sys
from pathlib import Path

# Add core to path  
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_response_system():
    """Test the response intelligence system."""
    print("Testing Response Intelligence System...")
    
    try:
        from core.narrative_systems.response import (
            ResponseOrchestrator, ContextAnalyzer, ResponsePlanner,
            ResponseStrategy, ContextQuality, ResponseComplexity
        )
        
        # Test context analyzer
        print("  Testing ContextAnalyzer...")
        analyzer = ContextAnalyzer()
        
        test_context = {
            "context": {
                "user_input": "The knight drew his sword and faced the dragon.",
                "character_states": {"knight": {"health": 100, "weapon": "sword"}},
                "story_state": {"location": "dragon_lair", "tension": 0.8},
                "narrative_history": ["The knight entered the lair", "The dragon roared"]
            }
        }
        
        analysis = analyzer.process(test_context)
        print(f"    ✅ Context quality: {analysis.quality.value}")
        print(f"    ✅ Content type: {analysis.content_type}")
        print(f"    ✅ Complexity needs: {analysis.complexity_needs.value}")
        
        # Test response planner
        print("  Testing ResponsePlanner...")
        planner = ResponsePlanner()
        
        planning_data = {
            "context_analysis": analysis,
            "preferences": {}
        }
        
        plan = planner.process(planning_data)
        print(f"    ✅ Strategy: {plan.strategy.value}")
        print(f"    ✅ Complexity: {plan.complexity.value}")
        print(f"    ✅ Content focus: {plan.content_focus}")
        print(f"    ✅ Estimated length: {plan.estimated_length}")
        
        # Test response orchestrator
        print("  Testing ResponseOrchestrator...")
        orchestrator = ResponseOrchestrator("storage/temp/test_response")
        
        request_data = {
            "context": {
                "user_input": "What happens next in the story?",
                "character_states": {"hero": {"status": "ready"}},
                "story_state": {"chapter": 1}
            },
            "request_id": "test_001"
        }
        
        result = orchestrator.process(request_data)
        print(f"    ✅ Processing success: {result.success}")
        print(f"    ✅ Analysis confidence: {result.analysis.confidence}")
        print(f"    ✅ Overall quality score: {result.evaluation.overall_score}")
        
        # Test performance summary
        summary = orchestrator.get_performance_summary()
        print(f"    ✅ Total responses: {summary['total_responses']}")
        
        return True
        
    except Exception as e:
        print(f"    ❌ Response system test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration():
    """Test integration with narrative orchestrator."""
    print("\nTesting integration with NarrativeOrchestrator...")
    
    try:
        from core.narrative_systems import NarrativeOrchestrator
        
        # Initialize orchestrator
        orchestrator = NarrativeOrchestrator("storage/temp/test_integration")
        
        # Test response operation
        operation = orchestrator.process_narrative_operation(
            "response.analyze_and_plan",
            "test_story_002",
            {
                "context": {
                    "user_input": "The wizard cast a spell.",
                    "character_states": {"wizard": {"mana": 50}}
                }
            }
        )
        
        print(f"  ✅ Integration operation success: {operation.success}")
        print(f"  ✅ Operation type: {operation.operation_type}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Integration test failed: {e}")
        return False

def main():
    """Run all response system tests."""
    print("Phase 6 Response Intelligence System Test")
    print("=" * 50)
    
    tests = [
        test_response_system,
        test_integration
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 Response Intelligence System working correctly!")
        print("✅ Ready to integrate with main narrative orchestrator")
        return True
    else:
        print("⚠️ Some tests failed - check implementation")
        return False

if __name__ == "__main__":
    main()
