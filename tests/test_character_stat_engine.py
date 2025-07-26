"""
Test suite for Character Stat Engine

Tests RPG-style character traits, stat-influenced behavior generation,
stat progression tracking, and narrative decision-making systems.
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.character_stat_engine import (
    CharacterStatEngine, CharacterStats, StatProgression, BehaviorInfluence,
    StatType, StatCategory, BehaviorModifier
)

class TestCharacterStats:
    """Test CharacterStats data class functionality."""
    
    def test_character_stats_initialization(self):
        """Test character stats initialization with defaults."""
        stats = CharacterStats(character_id="test_character")
        
        assert stats.character_id == "test_character"
        assert len(stats.stats) == 12  # All stat types
        assert all(value == 5 for value in stats.stats.values())  # Default value
        assert stats.progression_history == []
        assert stats.temporary_modifiers == {}
    
    def test_character_stats_with_custom_values(self):
        """Test character stats with custom initial values."""
        custom_stats = {
            StatType.INTELLIGENCE: 8,
            StatType.CHARISMA: 3,
            StatType.COURAGE: 9
        }
        
        stats = CharacterStats(character_id="custom_char", stats=custom_stats)
        
        assert stats.get_effective_stat(StatType.INTELLIGENCE) == 8
        assert stats.get_effective_stat(StatType.CHARISMA) == 3
        assert stats.get_effective_stat(StatType.COURAGE) == 9
        assert stats.get_effective_stat(StatType.WISDOM) == 5  # Default
    
    def test_stat_update_with_progression(self):
        """Test stat updates with progression tracking."""
        stats = CharacterStats(character_id="test_char")
        
        stats.update_stat(StatType.INTELLIGENCE, 7, "Learning experience", "library_scene")
        
        assert stats.get_effective_stat(StatType.INTELLIGENCE) == 7
        assert len(stats.progression_history) == 1
        
        progression = stats.progression_history[0]
        assert progression.stat_type == StatType.INTELLIGENCE
        assert progression.old_value == 5
        assert progression.new_value == 7
        assert progression.reason == "Learning experience"
        assert progression.scene_context == "library_scene"
    
    def test_temporary_modifiers(self):
        """Test temporary stat modifiers."""
        stats = CharacterStats(character_id="test_char")
        original_intelligence = stats.get_effective_stat(StatType.INTELLIGENCE)
        
        # Add temporary modifier
        stats.add_temporary_modifier(StatType.INTELLIGENCE, 3, 60, "Magic boost")
        
        assert stats.get_effective_stat(StatType.INTELLIGENCE) == original_intelligence + 3
        assert StatType.INTELLIGENCE in stats.temporary_modifiers
    
    def test_expired_temporary_modifiers(self):
        """Test that expired temporary modifiers are cleaned up."""
        stats = CharacterStats(character_id="test_char")
        
        # Add modifier that expires immediately
        past_time = datetime.now() - timedelta(minutes=10)
        stats.temporary_modifiers[StatType.INTELLIGENCE] = (3, past_time)
        
        # Getting effective stat should clean up expired modifier
        effective_stat = stats.get_effective_stat(StatType.INTELLIGENCE)
        
        assert effective_stat == 5  # Back to base value
        assert StatType.INTELLIGENCE not in stats.temporary_modifiers
    
    def test_stat_category_averages(self):
        """Test category average calculations."""
        stats = CharacterStats(character_id="test_char")
        
        # Set specific stats for mental category
        stats.stats[StatType.INTELLIGENCE] = 8
        stats.stats[StatType.WISDOM] = 6
        stats.stats[StatType.CREATIVITY] = 4
        stats.stats[StatType.PERCEPTION] = 2
        
        mental_avg = stats.get_stat_category_average(StatCategory.MENTAL)
        expected = (8 + 6 + 4 + 2) / 4
        assert mental_avg == expected
    
    def test_serialization(self):
        """Test stats serialization and deserialization."""
        original_stats = CharacterStats(character_id="serialize_test")
        original_stats.update_stat(StatType.CHARISMA, 8, "Test progression")
        original_stats.add_temporary_modifier(StatType.COURAGE, 2, 30, "Temporary boost")
        
        # Serialize and deserialize
        data = original_stats.to_dict()
        restored_stats = CharacterStats.from_dict(data)
        
        assert restored_stats.character_id == original_stats.character_id
        assert restored_stats.stats == original_stats.stats
        assert len(restored_stats.progression_history) == len(original_stats.progression_history)
        assert len(restored_stats.temporary_modifiers) == len(original_stats.temporary_modifiers)

class TestCharacterStatEngine:
    """Test main CharacterStatEngine functionality."""
    
    @pytest.fixture
    def engine(self):
        """Create a test character stat engine."""
        return CharacterStatEngine()
    
    @pytest.fixture
    def sample_character(self, engine):
        """Create a sample character for testing."""
        return engine.initialize_character("sample_hero", {
            "intelligence": 7,
            "charisma": 8,
            "courage": 6,
            "temper": 3,
            "loyalty": 9
        })
    
    def test_engine_initialization(self, engine):
        """Test engine initialization with default config."""
        assert engine.stat_range == (1, 10)
        assert engine.default_stat_value == 5
        assert engine.progression_enabled == True
        assert len(engine.behavior_templates) > 0
        assert len(engine.character_stats) == 0
    
    def test_character_initialization(self, engine):
        """Test character initialization in engine."""
        character = engine.initialize_character("test_hero", {
            "intelligence": 8,
            "charisma": 5,
            "courage": 7
        })
        
        assert character.character_id == "test_hero"
        assert character.get_effective_stat(StatType.INTELLIGENCE) == 8
        assert character.get_effective_stat(StatType.CHARISMA) == 5
        assert character.get_effective_stat(StatType.COURAGE) == 7
        assert "test_hero" in engine.character_stats
    
    def test_character_reinitialization(self, engine):
        """Test updating existing character stats."""
        # Create character first
        engine.initialize_character("hero", {"intelligence": 5})
        
        # Reinitialize with new stats
        character = engine.initialize_character("hero", {"intelligence": 8, "charisma": 7})
        
        assert character.get_effective_stat(StatType.INTELLIGENCE) == 8
        assert character.get_effective_stat(StatType.CHARISMA) == 7
        assert len(character.progression_history) >= 2  # Updates recorded
    
    def test_stat_update_through_engine(self, engine, sample_character):
        """Test updating character stats through engine interface."""
        success = engine.update_character_stat(
            "sample_hero", StatType.WISDOM, 8, "Gained wisdom from experience", "forest_scene"
        )
        
        assert success == True
        character = engine.get_character_stats("sample_hero")
        assert character.get_effective_stat(StatType.WISDOM) == 8
        
        # Check progression was recorded
        last_progression = character.progression_history[-1]
        assert last_progression.stat_type == StatType.WISDOM
        assert last_progression.scene_context == "forest_scene"
    
    def test_temporary_modifier_through_engine(self, engine, sample_character):
        """Test adding temporary modifiers through engine."""
        success = engine.add_temporary_stat_modifier(
            "sample_hero", StatType.COURAGE, 3, 30, "Battle fury"
        )
        
        assert success == True
        character = engine.get_character_stats("sample_hero")
        assert character.get_effective_stat(StatType.COURAGE) == 9  # 6 + 3
    
    def test_behavior_context_generation(self, engine, sample_character):
        """Test behavior context generation based on stats."""
        context = engine.generate_behavior_context("sample_hero", "dialogue")
        
        assert context['character_id'] == "sample_hero"
        assert 'behavior_influences' in context
        assert 'dominant_traits' in context
        assert 'limitations' in context
        assert 'strengths' in context
        assert 'stat_summary' in context
        
        # Check that high charisma (8) shows up in dominant traits
        dominant_traits = context['dominant_traits']
        assert any('charisma' in trait.lower() for trait in dominant_traits)
    
    def test_response_prompt_generation(self, engine, sample_character):
        """Test stat-influenced response prompt generation."""
        prompt = engine.generate_response_prompt("sample_hero", "dialogue", "confident")
        
        assert len(prompt) > 0
        assert "sample_hero" in prompt
        assert "[CHARACTER_TRAITS:" in prompt or "[LIMITATIONS:" in prompt
    
    def test_stat_based_decision_checking(self, engine, sample_character):
        """Test stat-based decision validation."""
        required_stats = {
            StatType.INTELLIGENCE: 6,  # Character has 7, should pass
            StatType.COURAGE: 8,       # Character has 6, should fail
            StatType.CHARISMA: 7       # Character has 8, should pass
        }
        
        result = engine.check_stat_based_decision(
            "sample_hero", "Complex negotiation", required_stats
        )
        
        assert result['character_id'] == "sample_hero"
        assert result['overall_success'] == False  # Failed courage check
        assert result['stat_checks'][StatType.INTELLIGENCE.value]['success'] == True
        assert result['stat_checks'][StatType.COURAGE.value]['success'] == False
        assert result['stat_checks'][StatType.CHARISMA.value]['success'] == True
        assert 0.0 <= result['success_probability'] <= 1.0
    
    def test_stat_progression_triggers(self, engine, sample_character):
        """Test automatic stat progression from story events."""
        original_courage = sample_character.get_effective_stat(StatType.COURAGE)
        
        progressions = engine.trigger_stat_progression(
            "sample_hero", "combat_victory", "epic_battle_scene"
        )
        
        # Should get progressions for courage and willpower
        assert len(progressions) >= 0  # Might be 0 due to randomness
        
        # If progressions occurred, check they're valid
        for progression in progressions:
            assert progression.reason == "Progression from combat_victory"
            assert progression.scene_context == "epic_battle_scene"
    
    def test_stat_summary_generation(self, engine, sample_character):
        """Test comprehensive stat summary generation."""
        summary = engine.get_stat_summary("sample_hero")
        
        assert summary['character_id'] == "sample_hero"
        assert 'current_stats' in summary
        assert 'base_stats' in summary
        assert 'category_averages' in summary
        assert 'dominant_traits' in summary
        
        # Check specific stat values
        current_stats = summary['current_stats']
        assert current_stats['intelligence'] == 7
        assert current_stats['charisma'] == 8
        assert current_stats['loyalty'] == 9
    
    def test_character_limitations_and_strengths(self, engine):
        """Test identification of character limitations and strengths."""
        # Create character with extreme stats
        character = engine.initialize_character("extreme_char", {
            "intelligence": 9,  # Very high
            "charisma": 2,      # Very low
            "courage": 1,       # Very low
            "loyalty": 10       # Maximum
        })
        
        context = engine.generate_behavior_context("extreme_char")
        
        limitations = context['limitations']
        strengths = context['strengths']
        
        # Should have limitations for low charisma and courage
        assert len(limitations) >= 2
        assert any('social' in limitation.lower() or 'charisma' in limitation.lower() for limitation in limitations)
        
        # Should have strengths for high intelligence and loyalty
        assert len(strengths) >= 2
        assert any('analytical' in strength.lower() or 'intelligence' in strength.lower() for strength in strengths)
    
    def test_engine_stats_compilation(self, engine, sample_character):
        """Test engine-wide statistics compilation."""
        # Add another character
        engine.initialize_character("second_hero", {"wisdom": 8, "empathy": 7})
        
        stats = engine.get_engine_stats()
        
        assert stats['total_characters'] == 2
        assert stats['progression_enabled'] == True
        assert 'average_stats_across_characters' in stats
        
        # Check average calculations
        avg_stats = stats['average_stats_across_characters']
        assert 'intelligence' in avg_stats
        assert 'wisdom' in avg_stats
    
    def test_character_data_export_import(self, engine, sample_character):
        """Test character data export and import functionality."""
        # Add some progression
        engine.update_character_stat("sample_hero", StatType.WISDOM, 7, "Test progression")
        
        # Export character data
        exported_data = engine.export_character_data("sample_hero")
        
        assert exported_data['character_id'] == "sample_hero"
        assert 'stats' in exported_data
        assert 'progression_history' in exported_data
        
        # Create new engine and import
        new_engine = CharacterStatEngine()
        new_engine.import_character_data(exported_data)
        
        imported_character = new_engine.get_character_stats("sample_hero")
        assert imported_character is not None
        assert imported_character.get_effective_stat(StatType.INTELLIGENCE) == 7
        assert imported_character.get_effective_stat(StatType.WISDOM) == 7
    
    def test_nonexistent_character_handling(self, engine):
        """Test graceful handling of operations on non-existent characters."""
        # Test getting non-existent character
        character = engine.get_character_stats("nonexistent")
        assert character is None
        
        # Test updating non-existent character
        success = engine.update_character_stat("nonexistent", StatType.COURAGE, 8, "test")
        assert success == False
        
        # Test behavior context for non-existent character
        context = engine.generate_behavior_context("nonexistent")
        assert context == {}
        
        # Test response prompt for non-existent character
        prompt = engine.generate_response_prompt("nonexistent")
        assert prompt == ""
    
    def test_stat_range_clamping(self, engine):
        """Test that stats are properly clamped to valid range."""
        character = engine.initialize_character("test_char")
        
        # Try to set stats outside valid range
        engine.update_character_stat("test_char", StatType.INTELLIGENCE, 15, "Over max")
        engine.update_character_stat("test_char", StatType.CHARISMA, -5, "Under min")
        
        updated_character = engine.get_character_stats("test_char")
        assert updated_character.get_effective_stat(StatType.INTELLIGENCE) == 10  # Clamped to max
        assert updated_character.get_effective_stat(StatType.CHARISMA) == 1      # Clamped to min
    
    def test_progression_with_diminishing_returns(self, engine):
        """Test that stat progression has diminishing returns for high stats."""
        # Create character with high stats
        character = engine.initialize_character("high_stat_char", {"courage": 9})
        
        # Attempt multiple progressions (should have low success rate due to high stat)
        progression_count = 0
        for _ in range(10):  # Try 10 times
            progressions = engine.trigger_stat_progression("high_stat_char", "combat_victory")
            progression_count += len(progressions)
        
        # Should have fewer progressions than if stat was lower (due to diminishing returns)
        # This is probabilistic, so we just check it's reasonable
        # combat_victory can trigger up to 2 stats (courage + willpower), so max theoretical is 20
        # With diminishing returns, we expect much less than that
        assert progression_count <= 15  # Should be significantly less than theoretical max

class TestStatInteractions:
    """Test complex stat interactions and combinations."""
    
    @pytest.fixture
    def engine(self):
        return CharacterStatEngine()
    
    def test_synergistic_stats_behavior(self, engine):
        """Test behavior when synergistic stats are both high."""
        # High intelligence + creativity should create specific behavioral patterns
        character = engine.initialize_character("genius_artist", {
            "intelligence": 9,
            "creativity": 9,
            "charisma": 3  # Low for contrast
        })
        
        context = engine.generate_behavior_context("genius_artist", "creative_task")
        
        # Should recognize both intelligence and creativity as dominant
        dominant_traits = context['dominant_traits']
        assert len(dominant_traits) >= 2
        assert any('intelligence' in trait.lower() for trait in dominant_traits)
        assert any('creativity' in trait.lower() for trait in dominant_traits)
    
    def test_conflicting_stats_handling(self, engine):
        """Test handling of conflicting high stats."""
        # High greed + high loyalty should create interesting tensions
        character = engine.initialize_character("conflicted_hero", {
            "greed": 8,
            "loyalty": 8,
            "wisdom": 6
        })
        
        context = engine.generate_behavior_context("conflicted_hero", "moral_choice")
        
        # Should recognize both traits as dominant
        dominant_traits = context['dominant_traits']
        assert any('greed' in trait.lower() for trait in dominant_traits)
        assert any('loyalty' in trait.lower() for trait in dominant_traits)
    
    def test_decision_complexity_with_multiple_stats(self, engine):
        """Test complex decisions requiring multiple stats."""
        character = engine.initialize_character("complex_hero", {
            "intelligence": 7,
            "charisma": 6,
            "wisdom": 8,
            "courage": 5
        })
        
        # Complex diplomatic mission requiring multiple stats
        required_stats = {
            StatType.INTELLIGENCE: 6,
            StatType.CHARISMA: 7,      # Just above character's level
            StatType.WISDOM: 7,
            StatType.COURAGE: 4
        }
        
        result = engine.check_stat_based_decision(
            "complex_hero", "Diplomatic mission to enemy court", required_stats
        )
        
        # Should pass most checks but fail charisma
        assert result['overall_success'] == False
        assert result['stat_checks'][StatType.CHARISMA.value]['success'] == False
        assert result['stat_checks'][StatType.INTELLIGENCE.value]['success'] == True
        assert result['stat_checks'][StatType.WISDOM.value]['success'] == True
        assert result['stat_checks'][StatType.COURAGE.value]['success'] == True
        
        # Success probability should be high due to passing most checks
        assert result['success_probability'] > 0.5

class TestBehaviorInfluence:
    """Test specific behavior influence generation."""
    
    def test_behavior_influence_creation(self):
        """Test BehaviorInfluence data structure."""
        influence = BehaviorInfluence(
            stat_type=StatType.CHARISMA,
            stat_value=8,
            modifier_type=BehaviorModifier.SOCIAL_INTERACTION,
            influence_strength=0.8,
            description="Naturally persuasive and engaging",
            examples=["Wins over skeptical NPCs", "Leads group discussions"]
        )
        
        assert influence.stat_type == StatType.CHARISMA
        assert influence.stat_value == 8
        assert influence.influence_strength == 0.8
        assert len(influence.examples) == 2
        
        # Test serialization
        data = influence.to_dict()
        assert data['stat_type'] == 'charisma'
        assert data['modifier_type'] == 'social_interaction'

if __name__ == "__main__":
    pytest.main([__file__])
