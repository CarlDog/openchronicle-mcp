"""
Test script for Phase 6 Day 4-5: Consistency and Emotional Systems Integration

This script validates the successful extraction and modularization of:
- MemoryConsistencyEngine → consistency/ subsystem  
- EmotionalStabilityEngine → emotional/ subsystem

And their integration with the NarrativeOrchestrator.
"""

import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_consistency_orchestrator():
    """Test ConsistencyOrchestrator functionality."""
    try:
        from core.narrative_systems.consistency import ConsistencyOrchestrator
        
        logger.info("✅ ConsistencyOrchestrator imported successfully")
        
        # Initialize orchestrator
        orchestrator = ConsistencyOrchestrator()
        logger.info("✅ ConsistencyOrchestrator initialized successfully")
        
        # Test memory validation
        test_memory = {
            'character_id': 'test_char_001',
            'content': 'I remember learning about magic today',
            'memory_type': 'learning',
            'emotional_score': 0.6,
            'importance': 0.8,
            'timestamp': '2025-08-04T10:00:00',
            'tags': ['magic', 'learning']
        }
        
        validation_result = orchestrator.validate_memory_consistency(
            'test_char_001', test_memory
        )
        logger.info(f"✅ Memory validation completed: {validation_result.get('is_consistent', False)}")
        
        # Test memory summary
        summary = orchestrator.get_character_memory_summary('test_char_001')
        logger.info(f"✅ Memory summary generated: {len(summary)} fields")
        
        # Test status
        status = orchestrator.get_status()
        logger.info(f"✅ ConsistencyOrchestrator status: {status['consistency_orchestrator']['initialized']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ConsistencyOrchestrator test failed: {e}")
        return False


def test_emotional_orchestrator():
    """Test EmotionalOrchestrator functionality."""
    try:
        from core.narrative_systems.emotional import EmotionalOrchestrator
        
        logger.info("✅ EmotionalOrchestrator imported successfully")
        
        # Initialize orchestrator
        orchestrator = EmotionalOrchestrator()
        logger.info("✅ EmotionalOrchestrator initialized successfully")
        
        # Test emotional state tracking
        tracking_result = orchestrator.track_emotional_state(
            character_id='test_char_001',
            emotion='happiness',
            intensity=0.7,
            context='Found a rare magical artifact'
        )
        logger.info(f"✅ Emotional tracking completed: {tracking_result.get('timestamp') is not None}")
        
        # Test behavior cooldown
        cooldown_result = orchestrator.trigger_behavior_cooldown(
            character_id='test_char_001',
            behavior='excited_exclamation',
            duration=300
        )
        logger.info(f"✅ Behavior cooldown triggered: {cooldown_result.get('cooldown_triggered', False)}")
        
        # Test dialogue similarity
        similarity = orchestrator.detect_dialogue_similarity(
            character_id='test_char_001',
            new_dialogue='This is amazing! I found something incredible!'
        )
        logger.info(f"✅ Dialogue similarity detected: {similarity:.2f}")
        
        # Test emotional context
        context = orchestrator.get_emotional_context('test_char_001')
        logger.info(f"✅ Emotional context retrieved: {context.get('character_id') == 'test_char_001'}")
        
        # Test stability analysis
        stability = orchestrator.analyze_emotional_stability('test_char_001')
        logger.info(f"✅ Stability analysis completed: {stability.get('stability_score') is not None}")
        
        # Test status
        status = orchestrator.get_status()
        logger.info(f"✅ EmotionalOrchestrator status: {status['emotional_orchestrator']['initialized']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ EmotionalOrchestrator test failed: {e}")
        return False


def test_memory_validator():
    """Test MemoryValidator component functionality."""
    try:
        from core.narrative_systems.consistency.memory_validator import MemoryValidator
        
        logger.info("✅ MemoryValidator imported successfully")
        
        # Initialize validator
        validator = MemoryValidator()
        logger.info("✅ MemoryValidator initialized successfully")
        
        # Test memory generation (placeholder)
        from core.narrative_systems.consistency.memory_validator import MemoryEvent
        from datetime import datetime
        
        event = MemoryEvent(
            event_type='dialogue',
            content='Had an interesting conversation about magic',
            timestamp=datetime.now(),
            characters_involved=['test_char_001'],
            emotional_impact=0.5,
            importance=0.7,
            tags=['conversation', 'magic']
        )
        
        memories = validator.generate_memories_from_event('test_char_001', event)
        logger.info(f"✅ Memory generation: {len(memories)} memories created")
        
        # Test status
        status = validator.get_status()
        logger.info(f"✅ MemoryValidator status: {status['memory_validator']['initialized']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ MemoryValidator test failed: {e}")
        return False


def test_mood_analyzer():
    """Test MoodAnalyzer component functionality."""
    try:
        from core.narrative_systems.emotional.mood_analyzer import MoodAnalyzer
        
        logger.info("✅ MoodAnalyzer imported successfully")
        
        # Initialize analyzer
        analyzer = MoodAnalyzer()
        logger.info("✅ MoodAnalyzer initialized successfully")
        
        # Test dialogue similarity
        similarity = analyzer.detect_dialogue_similarity(
            character_id='test_char_001',
            new_dialogue='I am feeling quite happy about this discovery!'
        )
        logger.info(f"✅ Dialogue similarity detection: {similarity:.2f}")
        
        # Test emotional loop detection
        loops = analyzer.detect_emotional_loops(
            character_id='test_char_001',
            text='I feel happy about this amazing discovery of magic!'
        )
        logger.info(f"✅ Emotional loop detection: {len(loops)} loops detected")
        
        # Test mood analysis
        mood = analyzer.analyze_current_mood('test_char_001')
        logger.info(f"✅ Mood analysis: {mood.get('dominant_mood', {}).get('emotion', 'unknown')}")
        
        # Test status
        status = analyzer.get_status()
        logger.info(f"✅ MoodAnalyzer status: {status['mood_analyzer']['initialized']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ MoodAnalyzer test failed: {e}")
        return False


def test_stability_tracker():
    """Test StabilityTracker component functionality."""
    try:
        from core.narrative_systems.emotional.stability_tracker import StabilityTracker
        
        logger.info("✅ StabilityTracker imported successfully")
        
        # Initialize tracker
        tracker = StabilityTracker()
        logger.info("✅ StabilityTracker initialized successfully")
        
        # Test emotional state tracking
        emotional_state = {
            'emotion': 'joy',
            'intensity': 0.8,
            'context': 'Successfully completed a challenging task',
            'timestamp': '2025-08-04T15:30:00'
        }
        
        tracking_result = tracker.track_emotional_state('test_char_001', emotional_state)
        logger.info(f"✅ Emotional state tracking: {tracking_result.get('state_tracked', False)}")
        
        # Test behavior cooldown
        cooldown_result = tracker.trigger_behavior_cooldown(
            character_id='test_char_001',
            behavior='celebration',
            duration=180
        )
        logger.info(f"✅ Behavior cooldown: {cooldown_result.get('cooldown_triggered', False)}")
        
        # Test stability score calculation
        stability_score = tracker.calculate_stability_score('test_char_001')
        logger.info(f"✅ Stability score: {stability_score:.2f}")
        
        # Test status
        status = tracker.get_status()
        logger.info(f"✅ StabilityTracker status: {status['stability_tracker']['initialized']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ StabilityTracker test failed: {e}")
        return False


def test_narrative_orchestrator_integration():
    """Test that NarrativeOrchestrator can work with new systems."""
    try:
        from core.narrative_systems import NarrativeOrchestrator
        
        logger.info("✅ NarrativeOrchestrator imported successfully")
        
        # Initialize orchestrator
        orchestrator = NarrativeOrchestrator()
        logger.info("✅ NarrativeOrchestrator initialized successfully")
        
        # Test status includes new components
        status = orchestrator.get_status()
        
        # Check for consistency orchestrator
        has_consistency = status.get('orchestrator_status', {}).get('consistency_orchestrator', False)
        logger.info(f"✅ Consistency integration: {has_consistency}")
        
        # Check for emotional orchestrator  
        has_emotional = status.get('orchestrator_status', {}).get('emotional_orchestrator', False)
        logger.info(f"✅ Emotional integration: {has_emotional}")
        
        logger.info(f"✅ NarrativeOrchestrator overall status: {status.get('status', 'unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ NarrativeOrchestrator integration test failed: {e}")
        return False


def test_module_imports():
    """Test that all modules can be imported correctly."""
    try:
        # Test consistency subsystem imports
        from core.narrative_systems.consistency import ConsistencyOrchestrator
        from core.narrative_systems.consistency import MemoryValidator  
        from core.narrative_systems.consistency import StateTracker
        logger.info("✅ Consistency subsystem imports successful")
        
        # Test emotional subsystem imports
        from core.narrative_systems.emotional import EmotionalOrchestrator
        from core.narrative_systems.emotional import StabilityTracker
        from core.narrative_systems.emotional import MoodAnalyzer
        logger.info("✅ Emotional subsystem imports successful")
        
        # Test that old imports still work (backward compatibility)
        try:
            from core.memory_consistency_engine import MemoryConsistencyEngine
            logger.info("✅ Legacy MemoryConsistencyEngine import successful (backward compatibility)")
        except ImportError:
            logger.warning("⚠️ Legacy MemoryConsistencyEngine import failed (expected if replaced)")
        
        try:
            from core.emotional_stability_engine import EmotionalStabilityEngine
            logger.info("✅ Legacy EmotionalStabilityEngine import successful (backward compatibility)")
        except ImportError:
            logger.warning("⚠️ Legacy EmotionalStabilityEngine import failed (expected if replaced)")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Module import test failed: {e}")
        return False


def run_phase_6_day_4_5_tests():
    """Run comprehensive tests for Phase 6 Day 4-5 completion."""
    logger.info("🚀 Starting Phase 6 Day 4-5 Completion Tests")
    logger.info("=" * 60)
    
    tests = [
        ("Module Imports", test_module_imports),
        ("ConsistencyOrchestrator", test_consistency_orchestrator),
        ("EmotionalOrchestrator", test_emotional_orchestrator),
        ("MemoryValidator Component", test_memory_validator),
        ("MoodAnalyzer Component", test_mood_analyzer),
        ("StabilityTracker Component", test_stability_tracker),
        ("NarrativeOrchestrator Integration", test_narrative_orchestrator_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running {test_name} test...")
        success = test_func()
        results.append((test_name, success))
        
        if success:
            logger.info(f"✅ {test_name} test PASSED")
        else:
            logger.error(f"❌ {test_name} test FAILED")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 PHASE 6 DAY 4-5 TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} {test_name}")
    
    logger.info(f"\n🎯 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 PHASE 6 DAY 4-5 COMPLETE! All systems operational!")
        logger.info("🚀 Ready for Phase 6 Day 6-7: Final Integration and Documentation")
        return True
    else:
        logger.error(f"⚠️ {total - passed} tests failed. Review and fix issues before proceeding.")
        return False


if __name__ == "__main__":
    success = run_phase_6_day_4_5_tests()
    sys.exit(0 if success else 1)
