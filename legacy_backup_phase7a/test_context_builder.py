"""
Test suite for Context Builder

Tests context building, engine coordination, and intelligent response integration.
"""

import pytest
import asyncio
import tempfile
import shutil
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from core.context_systems.context_orchestrator import (
    ContextOrchestrator,
)
from core.memory_management.context.context_builder import (
    load_canon_snippets,
    json_to_readable_text
)
from core.model_management import ModelOrchestrator


@pytest.fixture
def temp_story_dir():
    """Create temporary story directory for testing."""
    temp_dir = tempfile.mkdtemp()
    story_path = Path(temp_dir) / "test_story"
    story_path.mkdir(parents=True)
    
    # Create sample canon files
    canon_dir = story_path / "canon"
    canon_dir.mkdir()
    
    # Create sample canon files
    (canon_dir / "world_lore.json").write_text('{"setting": "fantasy world", "magic": "common"}')
    (canon_dir / "character_guide.txt").write_text("Characters have unique personalities and goals.")
    
    yield str(story_path)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_story_data(temp_story_dir):
    """Sample story data for testing."""
    return {
        "id": "test_story",
        "path": temp_story_dir,
        "meta": {
            "title": "Test Adventure",
            "description": "A test story for context building"
        },
        "characters": {
            "Alice": {
                "personality": "curious and brave",
                "stats": {"intelligence": 8, "courage": 9}
            }
        }
    }


@pytest.fixture
def mock_model_manager():
    """Create mock ModelManager."""
    manager = Mock(spec=ModelOrchestrator)
    manager.generate_response = AsyncMock(return_value="Mock analysis response")
    manager.get_adapter_info = Mock(return_value={"max_tokens": 4096})
    return manager


class TestCanonLoading:
    """Test canon snippet loading functionality."""
    
    def test_load_canon_snippets_with_refs(self, temp_story_dir):
        """Test loading specific canon references."""
        refs = ["world_lore", "character_guide"]
        snippets = load_canon_snippets(temp_story_dir, refs=refs)
        
        assert isinstance(snippets, list)
        assert len(snippets) == 2
        assert any("fantasy world" in snippet for snippet in snippets)
        assert any("personalities" in snippet for snippet in snippets)
    
    def test_load_canon_snippets_random(self, temp_story_dir):
        """Test loading random canon snippets."""
        snippets = load_canon_snippets(temp_story_dir, limit=2)
        
        assert isinstance(snippets, list)
        assert len(snippets) <= 2
    
    def test_load_canon_snippets_missing_dir(self):
        """Test loading from non-existent canon directory."""
        snippets = load_canon_snippets("/nonexistent/path")
        
        assert snippets == []
    
    def test_json_to_readable_text(self):
        """Test JSON to readable text conversion."""
        test_data = {
            "character_name": "Alice",
            "character_stats": {"strength": 8, "intelligence": 9},
            "abilities": ["magic", "swordplay"]
        }
        
        result = json_to_readable_text(test_data)
        
        assert "Character Name: Alice" in result
        assert "Character Stats:" in result
        assert "Abilities:" in result
        assert "- magic" in result


class TestBasicContextBuilding:
    """Test basic context building functionality."""
    
    def test_build_context_basic(self, sample_story_data):
        """Test basic context building."""
        user_input = "Alice explores the forest"
        
        # Mock memory loading
        with patch('core.context_builder.load_current_memory') as mock_memory:
            mock_memory.return_value = {
                "characters": {"Alice": {"current_state": {"location": "village"}}},
                "recent_events": [{"description": "Alice arrived at the village"}]
            }
            
            result = build_context(user_input, sample_story_data)
        
        assert isinstance(result, dict)
        assert "prompt" in result
        assert "full_context" in result
        assert "memory" in result
        assert "canon_used" in result
        assert user_input in result["prompt"]
        assert sample_story_data["meta"]["title"] in result["prompt"]
    
    def test_build_context_empty_memory(self, sample_story_data):
        """Test context building with empty memory."""
        user_input = "Start the adventure"
        
        with patch('core.context_builder.load_current_memory') as mock_memory:
            mock_memory.return_value = {}
            
            result = build_context(user_input, sample_story_data)
        
        assert isinstance(result, dict)
        assert "prompt" in result
        assert user_input in result["prompt"]


class TestAdvancedContextBuilding:
    """Test advanced context building with analysis."""
    
    @pytest.mark.asyncio
    async def test_build_context_with_analysis(self, sample_story_data):
        """Test context building with content analysis."""
        user_input = "Alice investigates the mysterious sounds"
        
        with patch('core.context_builder.load_current_memory') as mock_memory:
            mock_memory.return_value = {"characters": {"Alice": {}}}
            
            with patch('core.context_builder.ContentAnalyzer') as mock_analyzer_class:
                mock_analyzer = Mock()
                mock_analyzer.analyze_user_input = AsyncMock(return_value={
                    "content_type": "exploration",
                    "emotional_tone": "curious",
                    "response_style": "descriptive",
                    "entities": {"characters": ["Alice"]}
                })
                mock_analyzer.optimize_canon_selection = AsyncMock(return_value=["world_lore"])
                mock_analyzer.optimize_memory_context = AsyncMock(return_value={"characters": {"Alice": {}}})
                mock_analyzer_class.return_value = mock_analyzer
                
                with patch('core.model_adapter.ModelManager') as mock_manager_class:
                    mock_manager = Mock()
                    mock_manager.config = {
                        "content_routing": {
                            "safe_models": ["mock"],
                            "creative_models": ["mock"],
                            "analysis_models": ["mock"],
                            "nsfw_models": ["mock"]
                        }
                    }
                    mock_manager.list_model_configs.return_value = {
                        "mock": {"enabled": True}
                    }
                    mock_manager.generate_response = AsyncMock(return_value='{"content_type": "exploration"}')
                    mock_manager_class.return_value = mock_manager
                    
                    result = await build_context_with_analysis(user_input, sample_story_data)
        
        assert isinstance(result, dict)
        assert "prompt" in result
        assert "analysis" in result
        assert "routing" in result
        assert result["analysis"]["content_type"] in ["exploration", "general"]  # Accept either based on actual analysis


class TestDynamicContextBuilding:
    """Test dynamic context building with all engines."""
    
    @pytest.mark.asyncio
    async def test_build_context_with_dynamic_models(self, sample_story_data, mock_model_manager):
        """Test full dynamic context building."""
        user_input = "Alice draws her sword and prepares for battle"
        
        with patch('core.context_builder.load_current_memory') as mock_memory:
            mock_memory.return_value = {
                "characters": {"Alice": {"current_state": {"mood": "determined"}}},
                "recent_events": [{"description": "Enemies approach"}]
            }
            
            # Mock all the engine classes
            with patch('core.context_builder.ContentAnalyzer') as mock_content_analyzer:
                mock_analyzer = Mock()
                mock_analyzer.analyze_user_input = AsyncMock(return_value={
                    "content_type": "action",
                    "emotional_tone": "intense",
                    "routing_recommendation": "mock",
                    "entities": {"characters": ["Alice"]},
                    "flags": ["combat", "action"]
                })
                mock_content_analyzer.return_value = mock_analyzer
                
                with patch('core.context_builder.CharacterStyleManager'), \
                     patch('core.context_builder.CharacterConsistencyEngine'), \
                     patch('core.context_builder.EmotionalStabilityEngine'), \
                     patch('core.context_builder.CharacterInteractionEngine'), \
                     patch('core.context_builder.CharacterStatEngine'), \
                     patch('core.context_builder.NarrativeDiceEngine') as mock_dice_engine, \
                     patch('core.context_builder.MemoryConsistencyEngine'), \
                     patch('core.context_builder.IntelligentResponseEngine'), \
                     patch('core.context_builder.TokenManager') as mock_token_manager:
                    
                    # Setup dice engine mock with proper return values
                    mock_dice_instance = Mock()
                    mock_dice_instance.get_character_performance_data.return_value = {
                        'current_streak': 1,  # Integer instead of MagicMock
                        'streak_type': 'success'
                    }
                    mock_dice_instance.get_character_performance_summary.return_value = {
                        'best_resolution_type': 'combat',
                        'worst_resolution_type': 'persuasion',
                        'recent_streak': {
                            'current_streak': 1,  # Integer instead of MagicMock
                            'streak_type': 'success'
                        }
                    }
                    mock_dice_instance.stat_mappings = {}
                    mock_dice_engine.return_value = mock_dice_instance
                    
                    mock_token_manager.return_value.estimate_tokens = Mock(return_value=500)
                    
                    # Mock the intelligent response enhancement
                    with patch('core.context_builder.enhance_context_with_intelligent_response') as mock_enhance:
                        mock_enhance.return_value = {
                            "context": "Enhanced context with intelligent guidance",
                            "recommended_model": "mock",
                            "content_analysis": {"content_type": "action"},
                            "intelligent_response": {
                                "context_analysis": {"quality": "moderate"},
                                "response_plan": {"strategy": "action_focus"}
                            }
                        }
                        
                        result = await build_context_with_dynamic_models(user_input, sample_story_data, mock_model_manager)
        
        assert isinstance(result, dict)
        assert "context" in result
        assert "intelligent_response" in result
        assert "recommended_model" in result
    
    @pytest.mark.asyncio
    async def test_build_context_character_focus(self, sample_story_data, mock_model_manager):
        """Test context building with character focus."""
        user_input = "Alice reflects on her past adventures"
        
        with patch('core.context_builder.load_current_memory') as mock_memory:
            mock_memory.return_value = {"characters": {"Alice": {}}}
            
            with patch('core.context_builder.ContentAnalyzer') as mock_content_analyzer:
                mock_analyzer = Mock()
                mock_analyzer.analyze_user_input = AsyncMock(return_value={
                    "content_type": "character",
                    "emotional_tone": "reflective",
                    "entities": {"characters": ["Alice"]}
                })
                mock_content_analyzer.return_value = mock_analyzer
                
                # Mock other engines
                with patch('core.context_builder.CharacterStyleManager'), \
                     patch('core.context_builder.CharacterConsistencyEngine'), \
                     patch('core.context_builder.EmotionalStabilityEngine'), \
                     patch('core.context_builder.CharacterInteractionEngine'), \
                     patch('core.context_builder.CharacterStatEngine'), \
                     patch('core.context_builder.NarrativeDiceEngine'), \
                     patch('core.context_builder.MemoryConsistencyEngine'), \
                     patch('core.context_builder.IntelligentResponseEngine'), \
                     patch('core.context_builder.TokenManager') as mock_token_manager:
                    
                    mock_token_manager.return_value.estimate_tokens = Mock(return_value=300)
                    
                    with patch('core.context_builder.enhance_context_with_intelligent_response') as mock_enhance:
                        mock_enhance.return_value = {
                            "context": "Character-focused context",
                            "recommended_model": "mock",
                            "content_analysis": {"content_type": "character"},
                            "active_character": "Alice"
                        }
                        
                        result = await build_context_with_dynamic_models(user_input, sample_story_data, mock_model_manager)
        
        assert isinstance(result, dict)
        assert result["content_analysis"]["content_type"] == "character"
    
    @pytest.mark.asyncio
    async def test_build_context_error_handling(self, sample_story_data, mock_model_manager):
        """Test error handling in dynamic context building."""
        user_input = "Alice does something"
        
        with patch('core.context_builder.load_current_memory') as mock_memory:
            mock_memory.return_value = {}
            
            # Make content analyzer analysis fail, not constructor
            with patch('core.context_builder.ContentAnalyzer') as mock_content_analyzer:
                mock_analyzer = Mock()
                mock_analyzer.analyze_user_input = AsyncMock(side_effect=Exception("Analysis failed"))
                mock_content_analyzer.return_value = mock_analyzer
                
                result = await build_context_with_dynamic_models(user_input, sample_story_data, mock_model_manager)
        
        # Should still return a result with fallback values
        assert isinstance(result, dict)
        assert "context" in result


class TestContextValidation:
    """Test context validation functions."""
    
    @pytest.mark.asyncio
    async def test_validate_character_consistency(self, sample_story_data):
        """Test character consistency validation."""
        from core.context_builder import validate_character_consistency
        
        # Mock consistency engine
        mock_engine = Mock()
        mock_engine.analyze_behavioral_consistency = Mock(return_value=[])
        mock_engine.get_consistency_score = Mock(return_value=0.85)
        
        result = await validate_character_consistency(
            "Alice acts bravely", "Alice", "scene_1", mock_engine
        )
        
        assert isinstance(result, dict)
        assert "violations" in result
        assert "consistency_score" in result
        assert result["character_name"] == "Alice"
    
    @pytest.mark.asyncio
    async def test_validate_emotional_stability(self, sample_story_data):
        """Test emotional stability validation."""
        from core.context_builder import validate_emotional_stability
        
        # Mock emotional engine
        mock_engine = Mock()
        mock_engine.detect_emotional_loops = Mock(return_value=[])
        mock_engine.get_emotional_context = Mock(return_value={
            "emotional_stability_score": 0.9,
            "active_cooldowns": []
        })
        
        result = await validate_emotional_stability(
            "Alice feels happy", "Alice", "scene_1", mock_engine
        )
        
        assert isinstance(result, dict)
        assert "loops" in result
        assert "stability_score" in result
        assert result["character_name"] == "Alice"


class TestUtilityFunctions:
    """Test utility functions in context builder."""
    
    def test_build_system_context(self):
        """Test system context building."""
        from core.context_builder import _build_system_context
        
        story_data = {
            "meta": {
                "title": "Test Story",
                "description": "A test story"
            }
        }
        
        result = _build_system_context(story_data)
        
        assert "Test Story" in result
        assert "A test story" in result
    
    def test_build_memory_context(self):
        """Test memory context building."""
        from core.context_builder import _build_memory_context
        
        memory = {
            "characters": {"Alice": {"current_state": {"mood": "happy"}}},
            "world_state": {"weather": "sunny"},
            "flags": [{"name": "quest_started"}],
            "recent_events": [{"description": "Alice started her journey"}]
        }
        
        result = _build_memory_context(memory)
        
        assert "=== CHARACTERS ===" in result
        assert "Alice" in result
        assert "=== WORLD STATE ===" in result
        assert "sunny" in result
    
    def test_build_canon_context(self):
        """Test canon context building."""
        from core.context_builder import _build_canon_context
        
        canon_chunks = ["The world is magical", "Characters have special abilities"]
        
        result = _build_canon_context(canon_chunks)
        
        assert "=== CANON ===" in result
        assert "magical" in result
        assert "special abilities" in result
    
    def test_assemble_context(self):
        """Test context assembly."""
        from core.context_builder import _assemble_context
        
        context_parts = {
            "system": "System context",
            "memory": "Memory context", 
            "canon": "Canon context",
            "user_input": "User input"
        }
        
        result = _assemble_context(context_parts)
        
        assert "System context" in result
        assert "Memory context" in result
        assert "=== USER INPUT ===" in result
        assert "Continue the story" in result


if __name__ == "__main__":
    pytest.main([__file__])
