"""
Test suite for enhanced content classification and routing system.
"""

import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path so we can import our modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.content_analysis import ContentAnalysisOrchestrator as ContentAnalyzer


class TestContentClassification(unittest.TestCase):
    """Test enhanced content classification and routing."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock model manager
        self.mock_model_manager = Mock()
        self.mock_model_manager.config = {
            "content_routing": {
                "nsfw_models": ["ollama", "local"],
                "safe_models": ["openai", "anthropic", "gemini"],
                "creative_models": ["openai", "anthropic", "cohere"],
                "fast_models": ["groq", "ollama"],
                "analysis_models": ["anthropic", "openai", "gemini"]
            }
        }
        self.mock_model_manager.list_model_configs.return_value = {
            "openai": {"enabled": True},
            "anthropic": {"enabled": True},
            "ollama": {"enabled": True},
            "groq": {"enabled": True},
            "gemini": {"enabled": True},
            "cohere": {"enabled": True},
            "local": {"enabled": False},
            "mock": {"enabled": True}
        }
        
        self.analyzer = ContentAnalyzer(self.mock_model_manager)
    
    def test_nsfw_content_detection(self):
        """Test NSFW content detection with different severity levels."""
        # Test explicit content
        result = self.analyzer.detect_content_type("I want to have sex with you")
        self.assertEqual(result["content_type"], "nsfw")
        self.assertIn("explicit", result["content_flags"])
        self.assertGreater(result["confidence"], 0.7)
        
        # Test suggestive content
        result = self.analyzer.detect_content_type("I kiss her passionately under the moonlight")
        self.assertEqual(result["content_type"], "nsfw")
        self.assertIn("suggestive", result["content_flags"])
        self.assertGreater(result["confidence"], 0.5)
        
        # Test mature content
        result = self.analyzer.detect_content_type("I draw my sword and kill the enemy")
        self.assertEqual(result["content_type"], "nsfw")
        self.assertIn("mature", result["content_flags"])
        self.assertGreater(result["confidence"], 0.4)
    
    def test_creative_content_detection(self):
        """Test creative content detection."""
        result = self.analyzer.detect_content_type("I imagine myself as a wizard casting spells")
        self.assertEqual(result["content_type"], "creative")
        self.assertIn("creative", result["content_flags"])
        self.assertGreater(result["confidence"], 0.4)
    
    def test_analysis_content_detection(self):
        """Test analysis content detection."""
        result = self.analyzer.detect_content_type("What is the meaning of this place?")
        self.assertEqual(result["content_type"], "analysis")
        self.assertIn("analysis", result["content_flags"])
        self.assertGreater(result["confidence"], 0.3)
    
    def test_action_content_flags(self):
        """Test action content flag detection."""
        result = self.analyzer.detect_content_type("I attack the dragon with my sword")
        self.assertIn("action", result["content_flags"])
    
    def test_dialogue_content_flags(self):
        """Test dialogue content flag detection."""
        result = self.analyzer.detect_content_type('I say "Hello, who are you?"')
        self.assertIn("dialogue", result["content_flags"])
    
    def test_simple_content_flags(self):
        """Test simple content flag detection."""
        result = self.analyzer.detect_content_type("Yes")
        self.assertIn("simple", result["content_flags"])
    
    def test_model_routing_nsfw(self):
        """Test model routing for NSFW content."""
        analysis = {
            "content_type": "nsfw",
            "content_flags": ["explicit"],
            "confidence": 0.8
        }
        
        recommended = self.analyzer.recommend_generation_model(analysis)
        self.assertIn(recommended, ["ollama", "local"])
    
    def test_model_routing_creative(self):
        """Test model routing for creative content."""
        analysis = {
            "content_type": "creative",
            "content_flags": ["creative"],
            "confidence": 0.7
        }
        
        recommended = self.analyzer.recommend_generation_model(analysis)
        self.assertIn(recommended, ["openai", "anthropic", "cohere"])
    
    def test_model_routing_simple(self):
        """Test model routing for simple content."""
        analysis = {
            "content_type": "general",
            "content_flags": ["simple"],
            "confidence": 0.6,
            "word_count": 3
        }
        
        recommended = self.analyzer.recommend_generation_model(analysis)
        self.assertIn(recommended, ["groq", "ollama"])
    
    def test_model_routing_fallback(self):
        """Test model routing fallback behavior."""
        # Disable all models for a category
        self.mock_model_manager.list_model_configs.return_value = {
            "openai": {"enabled": False},
            "anthropic": {"enabled": False},
            "ollama": {"enabled": False},
            "groq": {"enabled": False},
            "gemini": {"enabled": False},
            "cohere": {"enabled": False},
            "local": {"enabled": False},
            "mock": {"enabled": True}
        }
        
        analysis = {
            "content_type": "creative",
            "content_flags": ["creative"],
            "confidence": 0.7
        }
        
        recommended = self.analyzer.recommend_generation_model(analysis)
        self.assertEqual(recommended, "mock")
    
    def test_model_routing_emergency_fallback(self):
        """Test emergency fallback when no models are enabled."""
        # Disable all models
        self.mock_model_manager.list_model_configs.return_value = {
            "openai": {"enabled": False},
            "anthropic": {"enabled": False},
            "ollama": {"enabled": False},
            "groq": {"enabled": False},
            "gemini": {"enabled": False},
            "cohere": {"enabled": False},
            "local": {"enabled": False},
            "mock": {"enabled": False}
        }
        
        analysis = {
            "content_type": "creative",
            "content_flags": ["creative"],
            "confidence": 0.7
        }
        
        recommended = self.analyzer.recommend_generation_model(analysis)
        self.assertEqual(recommended, "mock")
    
    def test_confidence_thresholds(self):
        """Test confidence-based routing thresholds."""
        # Low confidence NSFW should not trigger NSFW routing
        analysis = {
            "content_type": "nsfw",
            "content_flags": ["suggestive"],
            "confidence": 0.3
        }
        
        recommended = self.analyzer.recommend_generation_model(analysis)
        # Should fall back to safe models due to low confidence
        self.assertIn(recommended, ["openai", "anthropic", "gemini"])
    
    def test_content_detection_comprehensive(self):
        """Test comprehensive content detection with multiple flags."""
        result = self.analyzer.detect_content_type('I say "Let me cast a spell" and attack the dragon')
        
        # Should detect multiple flags
        self.assertIn("dialogue", result["content_flags"])
        self.assertIn("action", result["content_flags"])
        self.assertIn("creative", result["content_flags"])
        
        # Should classify as creative due to spell/fantasy content
        self.assertEqual(result["content_type"], "creative")


class TestContentAnalyzerIntegration(unittest.TestCase):
    """Test content analyzer integration with model fallbacks."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_model_manager = Mock()
        self.mock_model_manager.config = {
            "content_routing": {
                "nsfw_models": ["ollama"],
                "safe_models": ["openai", "anthropic"],
                "creative_models": ["openai", "anthropic"],
                "fast_models": ["groq"],
                "analysis_models": ["anthropic", "openai"]
            }
        }
        self.mock_model_manager.list_model_configs.return_value = {
            "openai": {"enabled": True},
            "anthropic": {"enabled": True},
            "ollama": {"enabled": True},
            "groq": {"enabled": True},
            "mock": {"enabled": True}
        }
        
        self.analyzer = ContentAnalyzer(self.mock_model_manager)
    
    def test_basic_analysis_fallback(self):
        """Test basic analysis fallback functionality."""
        user_input = "I explore the magical forest"
        story_context = {"story_id": "test_story"}
        
        # Test fallback with provided content detection
        content_detection = self.analyzer.detect_content_type(user_input)
        result = self.analyzer._basic_analysis_fallback(user_input, story_context, content_detection)
        
        self.assertEqual(result["content_type"], "creative")
        self.assertEqual(result["analysis_model"], "fallback")
        self.assertTrue(result["fallback_used"])
        self.assertIn("creative", result["content_flags"])
    
    def test_basic_analysis_fallback_without_detection(self):
        """Test basic analysis fallback without provided content detection."""
        user_input = "Hello there"
        story_context = {"story_id": "test_story"}
        
        result = self.analyzer._basic_analysis_fallback(user_input, story_context)
        
        self.assertEqual(result["content_type"], "general")
        self.assertEqual(result["analysis_model"], "fallback")
        self.assertTrue(result["fallback_used"])


if __name__ == '__main__':
    unittest.main()
