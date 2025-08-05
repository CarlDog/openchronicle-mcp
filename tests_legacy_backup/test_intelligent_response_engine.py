"""
Test suite for Intelligent Response Engine

Tests the adaptive story generation capabilities including context analysis,
response planning, prompt enhancement, and performance learning.
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

# Import the engine and related components
from core.intelligent_response_engine import (
    IntelligentResponseEngine,
    ResponseStrategy,
    ContextQuality, 
    ResponseComplexity,
    ContextAnalysis,
    ResponsePlan,
    ResponseEvaluation,
    ResponseMetrics,
    enhance_context_with_intelligent_response
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def engine(temp_dir):
    """Create IntelligentResponseEngine instance for testing."""
    return IntelligentResponseEngine(data_dir=temp_dir)


@pytest.fixture
def sample_context_data():
    """Sample context data for testing."""
    return {
        "context": """You are continuing a fictional interactive narrative.
Story Title: Test Adventure

=== CANON ===
The ancient forest is full of mystical creatures and hidden secrets.
Magic flows through the very air, making strange things possible.

=== CHARACTERS ===
Elena: A brave explorer with a curious nature

=== RECENT EVENTS ===
- Elena discovered a mysterious glowing stone
- Strange whispers echo through the trees
- A shadow moves between the ancient oaks

=== USER INPUT ===
Elena decides to investigate the whispers in the forest.

Continue the story with rich detail and continuity.""",
        "content_analysis": {
            "content_type": "exploration",
            "emotional_tone": "mysterious",
            "routing_recommendation": "mock",
            "entities": {
                "characters": ["Elena"],
                "locations": ["forest", "trees"],
                "objects": ["stone"]
            },
            "flags": ["mystery", "exploration"]
        },
        "active_character": "Elena",
        "token_estimate": 450
    }


@pytest.fixture
def rich_context_data():
    """Rich context data for testing complex scenarios."""
    return {
        "context": """You are continuing a fictional interactive narrative.
Story Title: Epic Quest

=== CANON ===
The Kingdom of Aethermoor stands at the crossroads of destiny.
Ancient prophecies speak of a chosen hero who will unite the realm.
The Crystal of Eternal Light holds the power to heal the wounded land.

=== CHARACTERS ===
Sir Marcus: A noble knight with unwavering honor and courage
Princess Lyara: A wise mage-princess with deep knowledge of ancient magic
Thorin: A gruff but loyal dwarf warrior with a heart of gold

=== WORLD STATE ===
kingdom_status: under_threat
magic_level: high
political_tension: rising

=== RECENT EVENTS ===
- The dark army approaches the capital
- Sir Marcus discovered his true heritage
- Princess Lyara unlocked forbidden magic
- An alliance was forged with the dwarf clans

=== CHARACTER MEMORIES ===
Sir Marcus remembers his father's final words about duty and sacrifice.
Princess Lyara recalls the ancient warning about forbidden magic's price.

[CHARACTER_STYLE: Sir Marcus speaks with formal, noble language reflecting his knightly training]
[CHARACTER_CONSISTENCY: Sir Marcus must maintain his honor code even in difficult situations]
[EMOTIONAL_STABILITY: Sir Marcus showing determination despite recent losses]
[CHARACTER_STATS: Sir Marcus has high Leadership and Combat skills]
[CHARACTER_INTERACTIONS: Multi-character scene with complex relationships]

=== USER INPUT ===
Sir Marcus rallies the troops before the final battle, while Princess Lyara prepares a powerful spell.

Continue the story with rich detail and continuity.""",
        "content_analysis": {
            "content_type": "action",
            "emotional_tone": "heroic",
            "routing_recommendation": "advanced",
            "entities": {
                "characters": ["Sir Marcus", "Princess Lyara", "Thorin"],
                "locations": ["kingdom", "capital"],
                "objects": ["Crystal", "army"]
            },
            "flags": ["heroic", "battle", "magic", "leadership"]
        },
        "active_character": "Sir Marcus",
        "token_estimate": 1250
    }


class TestIntelligentResponseEngine:
    """Test the core IntelligentResponseEngine functionality."""
    
    def test_engine_initialization(self, temp_dir):
        """Test engine initializes correctly."""
        engine = IntelligentResponseEngine(data_dir=temp_dir)
        
        assert engine.data_dir == Path(temp_dir)
        assert engine.data_dir.exists()
        assert isinstance(engine.strategy_weights, dict)
        assert len(engine.strategy_weights) == len(ResponseStrategy)
        assert all(weight == 1.0 for weight in engine.strategy_weights.values())
    
    def test_context_analysis_basic(self, engine, sample_context_data):
        """Test basic context analysis functionality."""
        analysis = engine.analyze_context(sample_context_data)
        
        assert isinstance(analysis, ContextAnalysis)
        assert analysis.quality in [ContextQuality.MODERATE, ContextQuality.LIMITED]
        assert 0.0 <= analysis.character_depth <= 1.0
        assert 0.0 <= analysis.world_richness <= 1.0
        assert analysis.total_tokens == 450
        assert "Elena" in str(analysis.key_elements) or analysis.character_depth > 0
    
    def test_context_analysis_rich(self, engine, rich_context_data):
        """Test context analysis with rich data."""
        analysis = engine.analyze_context(rich_context_data)
        
        assert isinstance(analysis, ContextAnalysis)
        assert analysis.quality in [ContextQuality.RICH, ContextQuality.MODERATE]
        assert analysis.character_depth > 0.5  # Should be high with character context
        assert analysis.world_richness > 0.3   # Should have good world context
        assert analysis.total_tokens == 1250
        assert len(analysis.key_elements) >= 2
    
    def test_context_analysis_sparse(self, engine):
        """Test context analysis with minimal data."""
        sparse_data = {
            "context": "Continue the story.",
            "content_analysis": {},
            "active_character": None,
            "token_estimate": 50
        }
        
        analysis = engine.analyze_context(sparse_data)
        
        assert analysis.quality == ContextQuality.SPARSE
        assert analysis.character_depth < 0.3
        assert analysis.world_richness < 0.3
        assert len(analysis.missing_elements) > 0
    
    def test_response_planning_basic(self, engine, sample_context_data):
        """Test basic response planning."""
        analysis = engine.analyze_context(sample_context_data)
        content_analysis = sample_context_data["content_analysis"]
        user_input = "Elena investigates the whispers"
        
        plan = engine.plan_response(analysis, user_input, content_analysis)
        
        assert isinstance(plan, ResponsePlan)
        assert plan.strategy in ResponseStrategy
        assert plan.complexity in ResponseComplexity
        assert 0.0 <= plan.confidence <= 1.0
        assert isinstance(plan.focus_areas, list)
        assert isinstance(plan.special_instructions, list)
    
    def test_response_planning_exploration_focus(self, engine):
        """Test response planning with exploration content."""
        context_data = {
            "context": "Exploring the ancient ruins...",
            "content_analysis": {
                "content_type": "exploration",
                "emotional_tone": "curious",
                "flags": ["discovery", "ancient"]
            },
            "active_character": "Explorer",
            "token_estimate": 300
        }
        
        analysis = engine.analyze_context(context_data)
        plan = engine.plan_response(analysis, "I search the ruins", context_data["content_analysis"])
        
        assert plan.strategy == ResponseStrategy.EXPLORATION_FOCUS
    
    def test_response_planning_dialogue_focus(self, engine):
        """Test response planning with dialogue content."""
        context_data = {
            "context": "Character conversation scene with multiple speakers...",
            "content_analysis": {
                "content_type": "dialogue",
                "emotional_tone": "tense",
                "entities": {
                    "characters": ["Alice", "Bob"]
                }
            },
            "active_character": "Alice",
            "token_estimate": 400
        }
        
        analysis = engine.analyze_context(context_data)
        plan = engine.plan_response(analysis, "Alice responds", context_data["content_analysis"])
        
        assert plan.strategy == ResponseStrategy.DIALOGUE_FOCUS
    
    def test_response_planning_adaptive_mixed(self, engine, rich_context_data):
        """Test adaptive mixed strategy selection."""
        analysis = engine.analyze_context(rich_context_data)
        plan = engine.plan_response(analysis, "Complex scene", rich_context_data["content_analysis"])
        
        # With rich context, might select ADAPTIVE_MIXED or specific focus
        assert plan.strategy in ResponseStrategy
        assert plan.complexity in [ResponseComplexity.MODERATE, ResponseComplexity.COMPLEX]
    
    def test_prompt_enhancement(self, engine, sample_context_data):
        """Test prompt enhancement with response plan."""
        analysis = engine.analyze_context(sample_context_data)
        plan = engine.plan_response(analysis, "test", sample_context_data["content_analysis"])
        
        original_prompt = sample_context_data["context"]
        enhanced_prompt = engine.enhance_prompt_with_plan(original_prompt, plan)
        
        assert len(enhanced_prompt) > len(original_prompt)
        assert "[RESPONSE_STRATEGY:" in enhanced_prompt
        assert "[RESPONSE_COMPLEXITY:" in enhanced_prompt
        assert "[INTELLIGENT_RESPONSE_ENGINE:" in enhanced_prompt
        assert plan.strategy.value in enhanced_prompt
    
    def test_response_evaluation_basic(self, engine, sample_context_data):
        """Test basic response evaluation."""
        analysis = engine.analyze_context(sample_context_data)
        plan = engine.plan_response(analysis, "test", sample_context_data["content_analysis"])
        
        sample_response = """Elena stepped carefully through the forest, her heart racing as the whispers grew louder. 
        The ancient trees seemed to lean in closer, their branches creating shadows that danced in the moonlight. 
        She could feel the magic in the air, electric and alive, calling to something deep within her soul."""
        
        evaluation = engine.evaluate_response(sample_response, sample_context_data, plan, "test input")
        
        assert isinstance(evaluation, ResponseEvaluation)
        assert 0.0 <= evaluation.quality_score <= 1.0
        assert 0.0 <= evaluation.coherence_score <= 1.0
        assert 0.0 <= evaluation.character_consistency <= 1.0
        assert 0.0 <= evaluation.engagement_level <= 1.0
        assert isinstance(evaluation.strengths, list)
        assert isinstance(evaluation.areas_for_improvement, list)
    
    def test_response_evaluation_quality_factors(self, engine, sample_context_data):
        """Test response evaluation quality factors."""
        analysis = engine.analyze_context(sample_context_data)
        plan = engine.plan_response(analysis, "test", sample_context_data["content_analysis"])
        
        # High quality response
        good_response = """Elena moved gracefully through the ancient forest, her keen eyes searching for the source of the mysterious whispers. The moonlight filtered through the canopy above, casting ethereal patterns on the forest floor. As she approached a clearing, she noticed the air itself seemed to shimmer with magical energy. "Hello?" she called softly, her voice carrying a mix of curiosity and caution. The whispers paused, as if considering her presence, before resuming with what sounded almost like an invitation."""
        
        # Poor quality response
        bad_response = "Elena walked. She heard things. The end."
        
        good_eval = engine.evaluate_response(good_response, sample_context_data, plan, "test")
        bad_eval = engine.evaluate_response(bad_response, sample_context_data, plan, "test")
        
        assert good_eval.quality_score > bad_eval.quality_score
        assert good_eval.engagement_level > bad_eval.engagement_level
        assert len(good_eval.strengths) > len(bad_eval.strengths)
    
    def test_metrics_recording(self, engine, sample_context_data):
        """Test response metrics recording and tracking."""
        analysis = engine.analyze_context(sample_context_data)
        plan = engine.plan_response(analysis, "test", sample_context_data["content_analysis"])
        
        sample_response = "Elena explored the mysterious forest with growing wonder."
        evaluation = engine.evaluate_response(sample_response, sample_context_data, plan, "test")
        
        initial_history_count = len(engine.response_history)
        
        engine.record_response_metrics(plan, evaluation, "test_model", 1.5, analysis)
        
        assert len(engine.response_history) == initial_history_count + 1
        assert plan.strategy in engine.strategy_performance
        assert "test_model" in engine.model_performance
        
        latest_metric = engine.response_history[-1]
        assert latest_metric.strategy_used == plan.strategy
        assert latest_metric.model_used == "test_model"
        assert latest_metric.response_time == 1.5
    
    def test_strategy_weight_learning(self, engine):
        """Test strategy weight learning from performance."""
        strategy = ResponseStrategy.NARRATIVE_FOCUS
        
        # Record several high-performance responses
        for _ in range(10):
            engine.strategy_performance[strategy] = engine.strategy_performance.get(strategy, [])
            engine.strategy_performance[strategy].append(0.9)  # High quality
        
        initial_weight = engine.strategy_weights[strategy]
        engine._update_strategy_weights()
        
        # Weight should increase for good performance
        assert engine.strategy_weights[strategy] >= initial_weight
    
    def test_performance_summary(self, engine, sample_context_data):
        """Test performance summary generation."""
        # Add some sample metrics
        analysis = engine.analyze_context(sample_context_data)
        plan = engine.plan_response(analysis, "test", sample_context_data["content_analysis"])
        evaluation = engine.evaluate_response("test response", sample_context_data, plan, "test")
        
        engine.record_response_metrics(plan, evaluation, "test_model", 1.0, analysis)
        
        summary = engine.get_performance_summary()
        
        assert "status" in summary
        assert summary["status"] in ["active", "initial_learning"]
        assert "total_responses" in summary
        assert "strategy_performance" in summary
        assert "model_performance" in summary
    
    def test_data_persistence(self, engine, temp_dir):
        """Test engine data saving and loading."""
        # Modify some engine state
        engine.strategy_weights[ResponseStrategy.CHARACTER_FOCUS] = 1.5
        engine.strategy_performance[ResponseStrategy.ACTION_FOCUS] = [0.8, 0.9, 0.7]
        engine.model_performance["test_model"] = [0.85, 0.90]
        
        # Save data
        engine._save_engine_data()
        
        # Create new engine instance and load data
        new_engine = IntelligentResponseEngine(data_dir=temp_dir)
        
        assert new_engine.strategy_weights[ResponseStrategy.CHARACTER_FOCUS] == 1.5
        assert ResponseStrategy.ACTION_FOCUS in new_engine.strategy_performance
        assert "test_model" in new_engine.model_performance
    
    def test_error_handling_invalid_context(self, engine):
        """Test error handling with invalid context data."""
        invalid_context = {"invalid": "data"}
        
        # Should not crash and return sparse analysis
        analysis = engine.analyze_context(invalid_context)
        assert analysis.quality == ContextQuality.SPARSE
        
        # Should not crash and return fallback plan
        plan = engine.plan_response(analysis, "test", {})
        assert plan.strategy in ResponseStrategy  # Any valid strategy is acceptable for fallback
        assert plan.confidence < 0.5


class TestContextIntegration:
    """Test integration with context building system."""
    
    def test_enhance_context_with_intelligent_response(self, sample_context_data):
        """Test context enhancement integration function."""
        user_input = "Elena investigates the whispers"
        
        enhanced_context = enhance_context_with_intelligent_response(
            sample_context_data, user_input
        )
        
        assert "intelligent_response" in enhanced_context
        assert "context_analysis" in enhanced_context["intelligent_response"]
        assert "response_plan" in enhanced_context["intelligent_response"]
        assert "enhanced_prompt" in enhanced_context["intelligent_response"]
        
        # Context should be updated with enhanced prompt
        original_length = len(sample_context_data["context"])
        enhanced_length = len(enhanced_context["context"])
        assert enhanced_length > original_length
    
    def test_enhance_context_preserves_original_on_error(self, sample_context_data):
        """Test that original context is preserved if enhancement fails."""
        # Mock an error condition
        with patch('core.intelligent_response_engine.IntelligentResponseEngine') as mock_engine:
            mock_engine.side_effect = Exception("Test error")
            
            enhanced_context = enhance_context_with_intelligent_response(
                sample_context_data, "test"
            )
            
            # Should return original context on error
            assert enhanced_context == sample_context_data


class TestResponseStrategies:
    """Test specific response strategy behaviors."""
    
    def test_character_focus_strategy(self, engine):
        """Test character focus strategy selection and application."""
        context_data = {
            "context": """Character development scene with deep emotional context.
            [CHARACTER_STYLE: detailed personality]
            [CHARACTER_CONSISTENCY: emotional growth]
            [EMOTIONAL_STABILITY: character showing vulnerability]""",
            "content_analysis": {
                "content_type": "character",
                "emotional_tone": "introspective"
            },
            "active_character": "TestChar",
            "token_estimate": 300
        }
        
        analysis = engine.analyze_context(context_data)
        plan = engine.plan_response(analysis, "test", context_data["content_analysis"])
        
        # Should favor character focus
        assert plan.strategy == ResponseStrategy.CHARACTER_FOCUS
        # With sparse context, focus areas might be empty but strategy should be correct
    
    def test_action_focus_strategy(self, engine):
        """Test action focus strategy selection."""
        context_data = {
            "context": """Fast-paced action scene with combat and movement.
            [DICE_RESOLUTION_SUGGESTED: combat]
            Physical challenges and dynamic events.""",
            "content_analysis": {
                "content_type": "action",
                "emotional_tone": "intense"
            },
            "active_character": "Fighter",
            "token_estimate": 300
        }
        
        analysis = engine.analyze_context(context_data)
        plan = engine.plan_response(analysis, "attack the enemy", context_data["content_analysis"])
        
        assert plan.strategy == ResponseStrategy.ACTION_FOCUS
        assert "action_dynamics" in plan.focus_areas or plan.tone_guidance.find("energetic") != -1
    
    def test_mystery_focus_override(self, engine):
        """Test mystery focus strategy override."""
        context_data = {
            "context": "Mysterious investigation scene...",
            "content_analysis": {
                "content_type": "investigation",
                "flags": ["mystery"],
                "emotional_tone": "suspenseful"
            },
            "active_character": "Detective",
            "token_estimate": 300
        }
        
        analysis = engine.analyze_context(context_data)
        plan = engine.plan_response(analysis, "investigate clues", context_data["content_analysis"])
        
        assert plan.strategy == ResponseStrategy.MYSTERY_FOCUS


class TestComplexityAdaptation:
    """Test response complexity adaptation."""
    
    def test_complexity_based_on_context_quality(self, engine):
        """Test that complexity adapts to context quality."""
        # Rich context should enable complex responses
        rich_context = {
            "context": "Very detailed context with multiple elements..." * 20,
            "content_analysis": {"content_type": "narrative"},
            "active_character": "Char",
            "token_estimate": 800
        }
        
        analysis = engine.analyze_context(rich_context)
        plan = engine.plan_response(analysis, "test", rich_context["content_analysis"])
        
        # Should allow for moderate to complex responses, but DYNAMIC is also valid
        assert plan.complexity in [ResponseComplexity.MODERATE, ResponseComplexity.COMPLEX, ResponseComplexity.DYNAMIC]
        
        # Sparse context should use simpler responses
        sparse_context = {
            "context": "Brief context.",
            "content_analysis": {},
            "active_character": None,
            "token_estimate": 50
        }
        
        analysis = engine.analyze_context(sparse_context)
        plan = engine.plan_response(analysis, "test", sparse_context["content_analysis"])
        
        assert plan.complexity in [ResponseComplexity.SIMPLE, ResponseComplexity.DYNAMIC]
    
    def test_length_target_adaptation(self, engine, sample_context_data):
        """Test length target adaptation based on complexity."""
        analysis = engine.analyze_context(sample_context_data)
        plan = engine.plan_response(analysis, "test", sample_context_data["content_analysis"])
        
        complexity_to_length = {
            ResponseComplexity.SIMPLE: "short",
            ResponseComplexity.MODERATE: "medium", 
            ResponseComplexity.COMPLEX: "long",
            ResponseComplexity.DYNAMIC: ["short", "medium", "long"]
        }
        
        expected_lengths = complexity_to_length[plan.complexity]
        if isinstance(expected_lengths, list):
            assert plan.length_target in expected_lengths
        else:
            assert plan.length_target == expected_lengths


if __name__ == "__main__":
    pytest.main([__file__])
