"""
Shared test utilities for OpenChronicle test suite.
"""

import os
import sys
import tempfile
import shutil
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List, Optional

# Add the parent directory to the path so we can import our modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class MockModelManager:
    """Mock model manager for testing."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.adapters = {}
        self.current_adapter = None
        
    def _default_config(self) -> Dict[str, Any]:
        """Default test configuration."""
        return {
            "content_routing": {
                "nsfw_models": ["ollama", "local"],
                "safe_models": ["openai", "anthropic", "gemini"],
                "creative_models": ["openai", "anthropic", "cohere"],
                "fast_models": ["groq", "ollama"],
                "analysis_models": ["anthropic", "openai", "gemini"]
            },
            "models": {
                "openai": {"enabled": True, "type": "api"},
                "anthropic": {"enabled": True, "type": "api"},
                "ollama": {"enabled": True, "type": "local"},
                "groq": {"enabled": True, "type": "api"},
                "gemini": {"enabled": True, "type": "api"},
                "cohere": {"enabled": True, "type": "api"},
                "local": {"enabled": False, "type": "local"},
                "mock": {"enabled": True, "type": "mock"}
            }
        }
    
    def list_model_configs(self) -> Dict[str, Dict[str, Any]]:
        """Return model configurations."""
        return self.config.get("models", {})
    
    async def initialize_adapter(self, adapter_name: str) -> bool:
        """Mock adapter initialization."""
        self.current_adapter = adapter_name
        return True
    
    async def generate_response(self, prompt: str, **kwargs) -> str:
        """Mock response generation."""
        return "Mock response for testing"
    
    async def shutdown(self):
        """Mock shutdown."""
        pass


class TestStoryData:
    """Mock story data for testing."""
    
    @staticmethod
    def create_demo_story() -> Dict[str, Any]:
        """Create a demo story for testing."""
        return {
            "id": "demo-story",
            "path": "/path/to/demo-story",
            "meta": {
                "title": "Demo Adventure",
                "description": "A test story for validation",
                "version": "1.0.0",
                "author": "Test Suite"
            },
            "characters": {
                "lyra": {
                    "name": "Lyra",
                    "description": "A brave adventurer",
                    "personality": "Curious and determined"
                },
                "guard": {
                    "name": "Castle Guard", 
                    "description": "A stern castle guard",
                    "personality": "Dutiful and suspicious"
                }
            },
            "locations": {
                "forest": {
                    "name": "Enchanted Forest",
                    "description": "A mysterious woodland"
                },
                "castle": {
                    "name": "Ancient Castle",
                    "description": "A foreboding stone fortress"
                }
            }
        }
    
    @staticmethod
    def create_temp_story_dir() -> str:
        """Create a temporary story directory structure."""
        temp_dir = tempfile.mkdtemp()
        story_dir = os.path.join(temp_dir, "test-story")
        os.makedirs(story_dir)
        
        # Create canon directory
        canon_dir = os.path.join(story_dir, "canon")
        os.makedirs(canon_dir)
        
        # Create sample canon files
        with open(os.path.join(canon_dir, "world_rules.txt"), "w") as f:
            f.write("Magic exists in this world.")
        
        with open(os.path.join(canon_dir, "character_lyra.json"), "w") as f:
            f.write('{"name": "Lyra", "class": "Ranger"}')
        
        return story_dir
    
    @staticmethod
    def cleanup_temp_dir(temp_dir: str):
        """Clean up temporary directory."""
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)


class ContentTestCases:
    """Common test cases for content analysis."""
    
    # Safe content test cases
    SAFE_CONTENT = [
        "Hello, what's your name?",
        "I look around the peaceful village.",
        "The sun sets over the mountains.",
        "I greet the friendly shopkeeper.",
        "What time is it?"
    ]
    
    # Creative content test cases
    CREATIVE_CONTENT = [
        "I cast a magical fireball spell.",
        "Describe the enchanted forest scene.",
        "Create a dialogue between two characters.",
        "I imagine a dragon flying overhead.",
        "Tell me about the ancient wizard's tower."
    ]
    
    # Action content test cases
    ACTION_CONTENT = [
        "I draw my sword and attack!",
        "I run towards the castle gate.",
        "I jump over the fallen log.",
        "I climb the tall tree.",
        "I fight the approaching bandits."
    ]
    
    # Analysis content test cases
    ANALYSIS_CONTENT = [
        "What is this place?",
        "Analyze the current situation.",
        "Explain what just happened.",
        "Why did the character do that?",
        "How does magic work here?"
    ]
    
    # NSFW/Mature content test cases (for testing filters)
    NSFW_CONTENT = [
        "I seduce the tavern keeper.",
        "The character removes their clothes.",
        "They engage in intimate activities.",
        "Describe an explicit romantic scene.",
        "The scene becomes very sexual."
    ]
    
    # Violence/Mature content test cases
    VIOLENT_CONTENT = [
        "I brutally kill the enemy.",
        "Blood splatters everywhere.",
        "I torture the prisoner for information.",
        "The scene is filled with gore.",
        "I dismember the fallen foe."
    ]


class AssertionHelpers:
    """Helper methods for common test assertions."""
    
    @staticmethod
    def assert_content_analysis_structure(test_case, analysis: Dict[str, Any]):
        """Assert that content analysis has proper structure."""
        required_keys = [
            "content_type", "content_flags", "confidence", 
            "raw_text", "word_count", "analysis_method"
        ]
        
        for key in required_keys:
            test_case.assertIn(key, analysis, f"Missing required key: {key}")
        
        test_case.assertIsInstance(analysis["content_flags"], list)
        test_case.assertIsInstance(analysis["confidence"], (int, float))
        test_case.assertGreaterEqual(analysis["confidence"], 0.0)
        test_case.assertLessEqual(analysis["confidence"], 1.0)
    
    @staticmethod
    def assert_routing_recommendation_structure(test_case, recommendation: str):
        """Assert that routing recommendation is valid."""
        test_case.assertIsInstance(recommendation, str)
        test_case.assertNotEqual(recommendation, "")
    
    @staticmethod
    def assert_transformer_analysis_structure(test_case, analysis: Dict[str, Any]):
        """Assert that transformer analysis has proper structure."""
        if "transformer_analysis" in analysis:
            transformer_data = analysis["transformer_analysis"]
            test_case.assertIn("nsfw_score", transformer_data)
            test_case.assertIn("sentiment", transformer_data)
            test_case.assertIsInstance(transformer_data["nsfw_score"], (int, float))


def create_mock_content_analyzer(use_transformers: bool = False):
    """Create a mock content analyzer for testing."""
    from core.content_analyzer import ContentAnalyzer
    
    mock_model_manager = MockModelManager()
    analyzer = ContentAnalyzer(mock_model_manager, use_transformers=use_transformers)
    return analyzer


def run_content_classification_test(analyzer, test_input: str, expected_type: str = None) -> Dict[str, Any]:
    """Run a content classification test and return results."""
    result = analyzer.detect_content_type(test_input)
    
    if expected_type:
        assert result["content_type"] == expected_type, \
            f"Expected {expected_type}, got {result['content_type']} for: {test_input}"
    
    return result


def run_routing_test(analyzer, analysis: Dict[str, Any]) -> str:
    """Run a routing test and return recommendation."""
    recommendation = analyzer.recommend_generation_model(analysis)
    assert isinstance(recommendation, str), "Routing recommendation must be a string"
    assert recommendation != "", "Routing recommendation cannot be empty"
    return recommendation


# Test data generators
def generate_test_memory() -> Dict[str, Any]:
    """Generate test memory data."""
    return {
        "characters": {
            "lyra": {
                "name": "Lyra",
                "status": "active",
                "location": "forest",
                "mood": "determined"
            }
        },
        "world_state": {
            "time_of_day": "evening",
            "weather": "clear",
            "location": "enchanted_forest"
        },
        "flags": [
            {"name": "quest_started", "value": True, "timestamp": "2024-01-01T12:00:00Z"},
            {"name": "dragon_encountered", "value": False, "timestamp": "2024-01-01T12:00:00Z"}
        ],
        "recent_events": [
            "Lyra entered the forest",
            "Strange sounds heard in distance",
            "Found mysterious artifact"
        ]
    }


def generate_test_story_context() -> Dict[str, Any]:
    """Generate test story context."""
    return {
        "story_id": "test-story",
        "meta": {
            "title": "Test Adventure",
            "description": "A test story"
        },
        "characters": {
            "lyra": {"name": "Lyra", "class": "Ranger"}
        },
        "memory": generate_test_memory()
    }


# Export commonly used items
__all__ = [
    'MockModelManager',
    'TestStoryData', 
    'ContentTestCases',
    'AssertionHelpers',
    'create_mock_content_analyzer',
    'run_content_classification_test',
    'run_routing_test',
    'generate_test_memory',
    'generate_test_story_context'
]
