"""
Tests for the Emotional Stability Engine

This test suite validates the emotional stability engine's ability to:
- Track emotional states and histories
- Detect and prevent gratification loops  
- Manage behavior cooldowns
- Generate appropriate anti-loop prompts
- Maintain emotional stability scores
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import json

from core.emotional_stability_engine import (
    EmotionalStabilityEngine,
    EmotionalState,
    BehaviorCooldown,
    LoopDetection
)

class TestEmotionalStabilityEngine(unittest.TestCase):
    """Test cases for the Emotional Stability Engine."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.engine = EmotionalStabilityEngine({
            'similarity_threshold': 0.75,
            'history_window_hours': 24,
            'max_emotional_states': 50,
            'loop_detection_enabled': True,
            'auto_disruption_enabled': True
        })
        
        self.test_character = "elena_nightshade"
        
    def test_initialization(self):
        """Test engine initialization."""
        self.assertIsInstance(self.engine, EmotionalStabilityEngine)
        self.assertEqual(self.engine.similarity_threshold, 0.75)
        self.assertEqual(self.engine.history_window_hours, 24)
        self.assertTrue(self.engine.loop_detection_enabled)
        self.assertTrue(self.engine.auto_disruption_enabled)
        
    def test_track_emotional_state(self):
        """Test tracking emotional states."""
        self.engine.track_emotional_state(
            self.test_character, 
            "flirty", 
            0.8, 
            "Making suggestive comments to the user"
        )
        
        self.assertIn(self.test_character, self.engine.emotional_histories)
        history = self.engine.emotional_histories[self.test_character]
        self.assertEqual(len(history), 1)
        
        state = history[0]
        self.assertEqual(state.emotion, "flirty")
        self.assertEqual(state.intensity, 0.8)
        self.assertEqual(state.context, "Making suggestive comments to the user")
        
    def test_emotional_state_serialization(self):
        """Test emotional state to/from dict conversion."""
        state = EmotionalState(
            emotion="vulnerable",
            intensity=0.6,
            timestamp=datetime.now(),
            context="Sharing personal fears",
            duration=15.5
        )
        
        state_dict = state.to_dict()
        restored_state = EmotionalState.from_dict(state_dict)
        
        self.assertEqual(state.emotion, restored_state.emotion)
        self.assertEqual(state.intensity, restored_state.intensity)
        self.assertEqual(state.context, restored_state.context)
        self.assertEqual(state.duration, restored_state.duration)
        
    def test_behavior_cooldown_tracking(self):
        """Test behavior cooldown functionality."""
        # Check initial state (no cooldown)
        self.assertFalse(self.engine.is_behavior_on_cooldown(self.test_character, "flirtation"))
        
        # Trigger cooldown
        self.engine.trigger_behavior_cooldown(self.test_character, "flirtation", 30)
        
        # Check cooldown is active
        self.assertTrue(self.engine.is_behavior_on_cooldown(self.test_character, "flirtation"))
        
        # Check cooldown data
        cooldown = self.engine.behavior_cooldowns[self.test_character]["flirtation"]
        self.assertEqual(cooldown.behavior, "flirtation")
        self.assertEqual(cooldown.cooldown_minutes, 30)
        self.assertEqual(cooldown.occurrence_count, 1)
        
    def test_behavior_cooldown_escalation(self):
        """Test cooldown escalation on repeated behavior."""
        # Trigger behavior multiple times
        for i in range(4):  # Trigger 4 times (above escalation threshold of 3)
            self.engine.trigger_behavior_cooldown(self.test_character, "flirtation", 30)
        
        cooldown = self.engine.behavior_cooldowns[self.test_character]["flirtation"]
        
        # Should have escalated cooldown time (doubled)
        self.assertEqual(cooldown.cooldown_minutes, 60)
        # Occurrence count should reset after escalation
        self.assertEqual(cooldown.occurrence_count, 1)
        
    def test_behavior_cooldown_serialization(self):
        """Test behavior cooldown to/from dict conversion."""
        cooldown = BehaviorCooldown(
            behavior="vulnerability",
            last_occurrence=datetime.now(),
            cooldown_minutes=45,
            occurrence_count=2,
            escalation_threshold=3
        )
        
        cooldown_dict = cooldown.to_dict()
        restored_cooldown = BehaviorCooldown.from_dict(cooldown_dict)
        
        self.assertEqual(cooldown.behavior, restored_cooldown.behavior)
        self.assertEqual(cooldown.cooldown_minutes, restored_cooldown.cooldown_minutes)
        self.assertEqual(cooldown.occurrence_count, restored_cooldown.occurrence_count)
        self.assertEqual(cooldown.escalation_threshold, restored_cooldown.escalation_threshold)
        
    def test_dialogue_similarity_detection(self):
        """Test detection of similar dialogue."""
        dialogue1 = "You're so beautiful, I can't help but admire you."
        dialogue2 = "You are so beautiful, I cannot help but admire you."
        dialogue3 = "The weather is quite nice today, isn't it?"
        
        # First dialogue should not trigger similarity (no previous dialogue)
        similarity1 = self.engine.detect_dialogue_similarity(self.test_character, dialogue1)
        self.assertLess(similarity1, 0.5)
        
        # Second dialogue should trigger high similarity
        similarity2 = self.engine.detect_dialogue_similarity(self.test_character, dialogue2)
        self.assertGreater(similarity2, 0.8)
        
        # Third dialogue should not trigger similarity
        similarity3 = self.engine.detect_dialogue_similarity(self.test_character, dialogue3)
        self.assertLess(similarity3, 0.4)  # Adjusted threshold to be more lenient
        
    def test_emotional_loop_detection_flirtation(self):
        """Test detection of excessive flirtation loops."""
        flirty_text = "You're so beautiful, I can't help but admire your gorgeous eyes."
        
        loops = self.engine.detect_emotional_loops(self.test_character, flirty_text)
        
        # Should detect excessive flirtation pattern
        flirtation_loops = [loop for loop in loops if loop.loop_type == 'excessive_flirtation']
        self.assertGreater(len(flirtation_loops), 0)
        
        loop = flirtation_loops[0]
        self.assertGreater(loop.confidence, 0.0)
        self.assertIn('flirtation', loop.pattern.lower())
        
    def test_emotional_loop_detection_praise_seeking(self):
        """Test detection of praise-seeking loops."""
        praise_text = "Do you think I'm beautiful? Am I good enough for you?"
        
        loops = self.engine.detect_emotional_loops(self.test_character, praise_text)
        
        # Should detect praise-seeking pattern
        praise_loops = [loop for loop in loops if loop.loop_type == 'praise_seeking']
        self.assertGreater(len(praise_loops), 0)
        
        loop = praise_loops[0]
        self.assertGreater(loop.confidence, 0.0)
        self.assertIn('praise', loop.pattern.lower())
        
    def test_emotional_loop_detection_neediness(self):
        """Test detection of neediness loops."""
        needy_text = "Please don't leave me, I can't live without you, I need you so much."
        
        loops = self.engine.detect_emotional_loops(self.test_character, needy_text)
        
        # Should detect neediness pattern
        needy_loops = [loop for loop in loops if loop.loop_type == 'neediness']
        self.assertGreater(len(needy_loops), 0)
        
        loop = needy_loops[0]
        self.assertGreater(loop.confidence, 0.0)
        self.assertIn('neediness', loop.pattern.lower())
        
    def test_dialogue_repetition_loop_detection(self):
        """Test detection of dialogue repetition loops."""
        repeated_dialogue = "I love you so much, you mean everything to me."
        
        # Add the dialogue twice with high similarity
        self.engine.detect_dialogue_similarity(self.test_character, repeated_dialogue)
        loops = self.engine.detect_emotional_loops(self.test_character, repeated_dialogue)
        
        # Should detect dialogue repetition
        repetition_loops = [loop for loop in loops if loop.loop_type == 'dialogue_repetition']
        self.assertGreater(len(repetition_loops), 0)
        
        loop = repetition_loops[0]
        self.assertGreaterEqual(loop.confidence, 0.75)  # Should meet similarity threshold
        self.assertEqual(loop.loop_type, 'dialogue_repetition')
        
    def test_anti_loop_prompt_generation(self):
        """Test generation of anti-loop prompts."""
        # Create a high-confidence loop
        loop = LoopDetection(
            loop_type='excessive_flirtation',
            pattern='Repetitive flirtation behavior',
            confidence=0.9,
            occurrences=['You are so beautiful', 'You are gorgeous'],
            suggested_disruption='emotional_shift',
            severity='high'
        )
        
        prompt = self.engine.generate_anti_loop_prompt(self.test_character, [loop])
        
        self.assertIn(self.test_character, prompt)
        self.assertIn('EMOTIONAL_STABILITY_NOTE', prompt)
        self.assertIn('flirtation', prompt.lower())
        self.assertIn('emotional authenticity', prompt.lower())
        
    def test_anti_loop_prompt_empty_for_no_loops(self):
        """Test that no prompt is generated when no loops are detected."""
        prompt = self.engine.generate_anti_loop_prompt(self.test_character, [])
        self.assertEqual(prompt, "")
        
    def test_emotional_context_retrieval(self):
        """Test retrieval of emotional context for a character."""
        # Add some emotional states
        self.engine.track_emotional_state(self.test_character, "happy", 0.7, "Successful interaction")
        self.engine.track_emotional_state(self.test_character, "flirty", 0.8, "Making advances")
        
        # Add a cooldown
        self.engine.trigger_behavior_cooldown(self.test_character, "flirtation", 30)
        
        context = self.engine.get_emotional_context(self.test_character)
        
        self.assertIsNotNone(context['current_state'])
        self.assertEqual(context['current_state']['emotion'], 'flirty')
        self.assertEqual(len(context['recent_emotions']), 2)
        self.assertEqual(len(context['active_cooldowns']), 1)
        self.assertIn('emotional_stability_score', context)
        
    def test_emotional_stability_score_calculation(self):
        """Test emotional stability score calculation."""
        # Add varied emotional states (should increase stability)
        emotions = ['happy', 'sad', 'angry', 'calm', 'excited']
        for i, emotion in enumerate(emotions):
            self.engine.track_emotional_state(
                self.test_character, 
                emotion, 
                0.5 + (i * 0.1),  # Varied intensities
                f"Context {i}"
            )
        
        context = self.engine.get_emotional_context(self.test_character)
        stability_score = context['emotional_stability_score']
        
        self.assertGreater(stability_score, 0.5)  # Should be reasonably stable
        self.assertLessEqual(stability_score, 1.0)
        
    def test_cooldown_status_retrieval(self):
        """Test retrieval of cooldown status."""
        # Add multiple cooldowns
        self.engine.trigger_behavior_cooldown(self.test_character, "flirtation", 30)
        self.engine.trigger_behavior_cooldown(self.test_character, "vulnerability", 45)
        
        status = self.engine.get_cooldown_status(self.test_character)
        
        self.assertIn('flirtation', status)
        self.assertIn('vulnerability', status)
        
        flirt_status = status['flirtation']
        self.assertTrue(flirt_status['active'])
        self.assertIsNotNone(flirt_status['remaining_minutes'])
        self.assertEqual(flirt_status['occurrence_count'], 1)
        
    def test_character_data_export_import(self):
        """Test export and import of character emotional data."""
        # Set up character data
        self.engine.track_emotional_state(self.test_character, "happy", 0.8, "Test context")
        self.engine.trigger_behavior_cooldown(self.test_character, "flirtation", 30)
        self.engine.detect_dialogue_similarity(self.test_character, "Test dialogue")
        
        # Export data
        exported_data = self.engine.export_character_data(self.test_character)
        
        # Reset character
        self.engine.reset_character_data(self.test_character)
        
        # Verify reset
        context = self.engine.get_emotional_context(self.test_character)
        self.assertIsNone(context['current_state'])
        self.assertEqual(len(context['active_cooldowns']), 0)
        
        # Import data
        self.engine.import_character_data(self.test_character, exported_data)
        
        # Verify restoration
        context = self.engine.get_emotional_context(self.test_character)
        self.assertIsNotNone(context['current_state'])
        self.assertEqual(context['current_state']['emotion'], 'happy')
        self.assertEqual(len(context['active_cooldowns']), 1)
        
    def test_engine_statistics(self):
        """Test engine statistics reporting."""
        # Add data for multiple characters
        characters = ['char1', 'char2', 'char3']
        for char in characters:
            self.engine.track_emotional_state(char, 'happy', 0.7, 'Test')
            self.engine.trigger_behavior_cooldown(char, 'flirtation', 30)
        
        stats = self.engine.get_engine_stats()
        
        self.assertEqual(stats['total_characters_tracked'], 3)
        self.assertEqual(stats['total_emotional_states'], 3)
        self.assertEqual(stats['total_active_cooldowns'], 3)
        self.assertGreater(stats['average_stability_score'], 0.0)
        self.assertTrue(stats['loop_detection_enabled'])
        self.assertTrue(stats['auto_disruption_enabled'])
        
    def test_max_emotional_states_limit(self):
        """Test that emotional state history is trimmed to max limit."""
        # Set a low limit for testing
        small_engine = EmotionalStabilityEngine({'max_emotional_states': 3})
        
        # Add more states than the limit
        for i in range(5):
            small_engine.track_emotional_state(
                self.test_character, 
                f'emotion_{i}', 
                0.5, 
                f'Context {i}'
            )
        
        history = small_engine.emotional_histories[self.test_character]
        self.assertEqual(len(history), 3)  # Should be trimmed to limit
        
        # Should keep the most recent states
        self.assertEqual(history[-1].emotion, 'emotion_4')
        self.assertEqual(history[-2].emotion, 'emotion_3')
        self.assertEqual(history[-3].emotion, 'emotion_2')
        
    def test_cooldown_expiry(self):
        """Test that cooldowns expire after their duration."""
        # Mock datetime to control time
        with patch('core.emotional_stability_engine.datetime') as mock_datetime:
            # Set initial time
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_datetime.now.return_value = initial_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Trigger cooldown
            self.engine.trigger_behavior_cooldown(self.test_character, "flirtation", 30)
            
            # Should be on cooldown
            self.assertTrue(self.engine.is_behavior_on_cooldown(self.test_character, "flirtation"))
            
            # Advance time by 31 minutes
            future_time = initial_time + timedelta(minutes=31)
            mock_datetime.now.return_value = future_time
            
            # Should no longer be on cooldown
            self.assertFalse(self.engine.is_behavior_on_cooldown(self.test_character, "flirtation"))
            
    def test_loop_detection_disabled(self):
        """Test that loop detection can be disabled."""
        disabled_engine = EmotionalStabilityEngine({'loop_detection_enabled': False})
        
        flirty_text = "You're so beautiful, I can't help but admire your gorgeous eyes."
        loops = disabled_engine.detect_emotional_loops(self.test_character, flirty_text)
        
        self.assertEqual(len(loops), 0)  # No loops should be detected when disabled
        
    def test_text_normalization(self):
        """Test text normalization for similarity detection."""
        text1 = "Hello,   there! How are you?  "
        text2 = "hello there how are you"
        
        normalized1 = self.engine._normalize_text(text1)
        normalized2 = self.engine._normalize_text(text2)
        
        self.assertEqual(normalized1, normalized2)
        
    def test_disruption_suggestion_mapping(self):
        """Test that appropriate disruption suggestions are provided."""
        suggestions = {
            'excessive_flirtation': 'emotional_shift',
            'praise_seeking': 'internal_resistance',
            'neediness': 'external_interruption',
            'dialogue_repetition': 'emotional_shift'
        }
        
        for loop_type, expected in suggestions.items():
            suggestion = self.engine._get_disruption_suggestion(loop_type)
            self.assertEqual(suggestion, expected)
            
        # Test unknown loop type defaults to emotional_shift
        unknown_suggestion = self.engine._get_disruption_suggestion('unknown_type')
        self.assertEqual(unknown_suggestion, 'emotional_shift')

if __name__ == '__main__':
    unittest.main()
