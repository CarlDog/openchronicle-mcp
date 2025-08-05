"""
Test suite for Narrative Dice Engine

Tests RPG-style success/failure resolution system, dice mechanics,
story branching, and character performance tracking.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.narrative_dice_engine import (
    NarrativeDiceEngine, ResolutionResult, ResolutionConfig, NarrativeBranch,
    DiceType, ResolutionType, DifficultyLevel, OutcomeType
)

class TestResolutionConfig:
    """Test ResolutionConfig data class functionality."""
    
    def test_resolution_config_defaults(self):
        """Test default configuration values."""
        config = ResolutionConfig()
        
        assert config.enabled == True
        assert config.dice_type == DiceType.D20
        assert config.modifier_tolerance == 3
        assert config.skill_dependency == True
        assert config.failure_narrative_required == True
        assert config.critical_range == 1
        assert config.advantage_enabled == True
        assert config.disadvantage_enabled == True
    
    def test_resolution_config_serialization(self):
        """Test config serialization and deserialization."""
        original_config = ResolutionConfig(
            enabled=False,
            dice_type=DiceType.D10,
            modifier_tolerance=5,
            critical_range=2
        )
        
        # Serialize and deserialize
        data = original_config.to_dict()
        restored_config = ResolutionConfig.from_dict(data)
        
        assert restored_config.enabled == original_config.enabled
        assert restored_config.dice_type == original_config.dice_type
        assert restored_config.modifier_tolerance == original_config.modifier_tolerance
        assert restored_config.critical_range == original_config.critical_range

class TestResolutionResult:
    """Test ResolutionResult data class functionality."""
    
    def test_resolution_result_creation(self):
        """Test creating a resolution result."""
        result = ResolutionResult(
            resolution_id="test_001",
            character_id="hero",
            resolution_type=ResolutionType.PERSUASION,
            dice_rolled=[15],
            total_roll=15,
            modifiers={"charisma": 2},
            final_result=17,
            difficulty=14,
            outcome=OutcomeType.SUCCESS,
            success=True,
            margin=3,
            narrative_impact="Successfully convinces the guard",
            timestamp=datetime.now()
        )
        
        assert result.character_id == "hero"
        assert result.resolution_type == ResolutionType.PERSUASION
        assert result.success == True
        assert result.margin == 3
        assert result.final_result == 17
    
    def test_resolution_result_serialization(self):
        """Test result serialization and deserialization."""
        original_result = ResolutionResult(
            resolution_id="test_002",
            character_id="mage",
            resolution_type=ResolutionType.INVESTIGATION,
            dice_rolled=[8, 7],
            total_roll=15,
            modifiers={"intelligence": 3},
            final_result=18,
            difficulty=16,
            outcome=OutcomeType.SUCCESS,
            success=True,
            margin=2,
            narrative_impact="Discovers hidden clue",
            timestamp=datetime.now(),
            scene_context="library_search"
        )
        
        # Serialize and deserialize
        data = original_result.to_dict()
        restored_result = ResolutionResult.from_dict(data)
        
        assert restored_result.resolution_id == original_result.resolution_id
        assert restored_result.character_id == original_result.character_id
        assert restored_result.resolution_type == original_result.resolution_type
        assert restored_result.dice_rolled == original_result.dice_rolled
        assert restored_result.success == original_result.success
        assert restored_result.scene_context == original_result.scene_context

class TestNarrativeDiceEngine:
    """Test main NarrativeDiceEngine functionality."""
    
    @pytest.fixture
    def engine(self):
        """Create a test narrative dice engine."""
        return NarrativeDiceEngine()
    
    @pytest.fixture
    def sample_character_stats(self):
        """Sample character stats for testing."""
        return {
            "charisma": 8,
            "intelligence": 6,
            "courage": 7,
            "wisdom": 5,
            "perception": 4
        }
    
    def test_engine_initialization(self, engine):
        """Test engine initialization with default config."""
        assert engine.config.enabled == True
        assert engine.config.dice_type == DiceType.D20
        assert len(engine.resolution_history) == 0
        assert len(engine.character_performance) == 0
        assert len(engine.dice_functions) == 8  # All dice types
    
    def test_engine_with_custom_config(self):
        """Test engine initialization with custom config."""
        config = {
            'enabled': False,
            'dice_type': 'd10',
            'modifier_tolerance': 5
        }
        
        engine = NarrativeDiceEngine(config)
        
        assert engine.config.enabled == False
        assert engine.config.dice_type == DiceType.D10
        assert engine.config.modifier_tolerance == 5
    
    def test_basic_resolution_success(self, engine, sample_character_stats):
        """Test basic successful resolution."""
        with patch.object(engine, '_roll_dice', return_value=[15]):
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.PERSUASION,
                difficulty=DifficultyLevel.MODERATE,
                character_stats=sample_character_stats
            )
        
        assert result.character_id == "hero"
        assert result.resolution_type == ResolutionType.PERSUASION
        assert result.success == True  # 15 + 3 (charisma modifier) = 18 vs 12
        assert result.final_result == 18
        assert result.difficulty == 12
        assert result.margin == 6
        assert len(engine.resolution_history) == 1
    
    def test_basic_resolution_failure(self, engine, sample_character_stats):
        """Test basic failed resolution."""
        with patch.object(engine, '_roll_dice', return_value=[5]):
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.PERSUASION,
                difficulty=DifficultyLevel.HARD,
                character_stats=sample_character_stats
            )
        
        assert result.character_id == "hero"
        assert result.success == False  # 5 + 3 = 8 vs 16
        assert result.final_result == 8
        assert result.difficulty == 16
        assert result.margin == -8
        assert result.outcome in [OutcomeType.FAILURE, OutcomeType.CRITICAL_FAILURE]
    
    def test_critical_success_and_failure(self, engine, sample_character_stats):
        """Test critical success and failure detection."""
        # Test critical success (natural 20)
        with patch.object(engine, '_roll_dice', return_value=[20]):
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.ATHLETICS,
                difficulty=DifficultyLevel.HARD,
                character_stats=sample_character_stats
            )
        
        assert result.outcome == OutcomeType.CRITICAL_SUCCESS
        
        # Test critical failure (natural 1)
        with patch.object(engine, '_roll_dice', return_value=[1]):
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.ATHLETICS,
                difficulty=DifficultyLevel.EASY,
                character_stats=sample_character_stats
            )
        
        assert result.outcome == OutcomeType.CRITICAL_FAILURE
    
    def test_stat_modifiers(self, engine):
        """Test character stat modifiers calculation."""
        high_charisma_stats = {"charisma": 10, "intelligence": 3}
        
        with patch.object(engine, '_roll_dice', return_value=[10]):
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.PERSUASION,
                difficulty=15,
                character_stats=high_charisma_stats
            )
        
        # Should have +3 modifier from charisma (clamped by tolerance)
        assert "charisma" in result.modifiers
        assert result.modifiers["charisma"] == 3  # Clamped to tolerance
        assert result.final_result == 13  # 10 + 3
    
    def test_disabled_engine(self):
        """Test engine behavior when disabled."""
        config = {'enabled': False}
        engine = NarrativeDiceEngine(config)
        
        result = engine.resolve_action(
            character_id="hero",
            resolution_type=ResolutionType.COMBAT,
            difficulty=DifficultyLevel.LEGENDARY
        )
        
        assert result.success == True  # Always succeeds when disabled
        assert result.outcome == OutcomeType.SUCCESS
        assert result.narrative_impact == "Automatic success in combat"
    
    def test_advantage_and_disadvantage(self, engine, sample_character_stats):
        """Test advantage and disadvantage mechanics."""
        # Test advantage (roll twice, take higher)
        with patch.object(engine, '_roll_dice', return_value=[18]):  # Mocked to return higher
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.PERCEPTION,
                difficulty=15,
                character_stats=sample_character_stats,
                advantage=True
            )
        
        assert result.success == True
        
        # Test disadvantage (roll twice, take lower)
        with patch.object(engine, '_roll_dice', return_value=[5]):  # Mocked to return lower
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.PERCEPTION,
                difficulty=15,
                character_stats=sample_character_stats,
                disadvantage=True
            )
        
        assert result.success == False
    
    def test_different_dice_types(self, sample_character_stats):
        """Test different dice type configurations."""
        dice_configs = [
            DiceType.D6,
            DiceType.D10,
            DiceType.D12,
            DiceType.TWO_D10,
            DiceType.THREE_D6
        ]
        
        for dice_type in dice_configs:
            config = {'dice_type': dice_type.value}
            engine = NarrativeDiceEngine(config)
            
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.SOCIAL,
                difficulty=10,
                character_stats=sample_character_stats
            )
            
            assert result is not None
            assert isinstance(result.dice_rolled, list)
            assert len(result.dice_rolled) > 0
    
    def test_narrative_branches_creation(self, engine):
        """Test narrative branch creation for different outcomes."""
        branches = engine.create_narrative_branches(
            ResolutionType.DECEPTION,
            "tavern_scene"
        )
        
        assert len(branches) == 5  # One for each OutcomeType
        assert OutcomeType.CRITICAL_SUCCESS in branches
        assert OutcomeType.FAILURE in branches
        
        # Check branch content
        success_branch = branches[OutcomeType.SUCCESS]
        assert success_branch.outcome_type == OutcomeType.SUCCESS
        assert "deception" in success_branch.narrative_text.lower()
        assert success_branch.emotional_impact != ""
    
    def test_resolution_prompt_generation(self, engine, sample_character_stats):
        """Test resolution prompt generation."""
        with patch.object(engine, '_roll_dice', return_value=[15]):
            result = engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.INTIMIDATION,
                difficulty=12,
                character_stats=sample_character_stats
            )
        
        prompt = engine.get_resolution_prompt(result)
        
        assert "[RESOLUTION_RESULT:" in prompt
        assert "hero" in prompt
        assert "intimidation" in prompt
        assert "SUCCESS" in prompt
        assert "[RESULT_CONTEXT:" in prompt
        assert "[NARRATIVE_GUIDANCE:" in prompt
    
    def test_character_performance_tracking(self, engine, sample_character_stats):
        """Test character performance tracking over multiple resolutions."""
        # Perform multiple resolutions
        with patch.object(engine, '_roll_dice', return_value=[15]):
            for i in range(3):
                engine.resolve_action(
                    character_id="hero",
                    resolution_type=ResolutionType.PERSUASION,
                    difficulty=10,
                    character_stats=sample_character_stats
                )
        
        with patch.object(engine, '_roll_dice', return_value=[5]):
            for i in range(2):
                engine.resolve_action(
                    character_id="hero",
                    resolution_type=ResolutionType.ATHLETICS,
                    difficulty=15,
                    character_stats=sample_character_stats
                )
        
        # Check performance summary
        performance = engine.get_character_performance_summary("hero")
        
        assert performance['character_id'] == "hero"
        assert performance['total_resolutions'] == 5
        assert performance['total_successes'] == 3
        assert performance['overall_success_rate'] == 0.6
        assert 'performance_by_type' in performance
        assert 'persuasion' in performance['performance_by_type']
        assert 'athletics' in performance['performance_by_type']
    
    def test_resolution_simulation(self, engine):
        """Test resolution simulation for probability analysis."""
        character_stats = {"charisma": 8}
        
        simulation = engine.simulate_resolution(
            ResolutionType.PERSUASION,
            difficulty=15,
            character_stats=character_stats,
            iterations=100
        )
        
        assert simulation['resolution_type'] == 'persuasion'
        assert simulation['difficulty'] == 15
        assert simulation['iterations'] == 100
        assert 0 <= simulation['success_probability'] <= 1
        assert 'outcome_distribution' in simulation
        assert 'average_margin' in simulation
        assert 'modifiers_applied' in simulation
    
    def test_engine_data_export_import(self, engine, sample_character_stats):
        """Test engine data export and import functionality."""
        # Perform some resolutions to create data
        with patch.object(engine, '_roll_dice', return_value=[12]):
            engine.resolve_action(
                character_id="hero",
                resolution_type=ResolutionType.PERCEPTION,
                difficulty=10,
                character_stats=sample_character_stats
            )
        
        # Create narrative branches
        engine.create_narrative_branches(ResolutionType.COMBAT, "battle_scene")
        
        # Export data
        exported_data = engine.export_engine_data()
        
        assert 'config' in exported_data
        assert 'resolution_history' in exported_data
        assert 'narrative_branches' in exported_data
        assert 'character_performance' in exported_data
        
        # Create new engine and import
        new_engine = NarrativeDiceEngine()
        new_engine.import_engine_data(exported_data)
        
        assert len(new_engine.resolution_history) == len(engine.resolution_history)
        assert len(new_engine.character_performance) == len(engine.character_performance)
        assert len(new_engine.narrative_branches) == len(engine.narrative_branches)
    
    def test_engine_statistics(self, engine, sample_character_stats):
        """Test engine statistics compilation."""
        # Perform various resolutions
        resolution_types = [ResolutionType.PERSUASION, ResolutionType.ATHLETICS, ResolutionType.INVESTIGATION]
        
        for res_type in resolution_types:
            with patch.object(engine, '_roll_dice', return_value=[15]):
                engine.resolve_action(
                    character_id="hero",
                    resolution_type=res_type,
                    difficulty=12,
                    character_stats=sample_character_stats
                )
        
        stats = engine.get_engine_stats()
        
        assert stats['total_resolutions'] == 3
        assert stats['total_successes'] >= 0
        assert 0 <= stats['overall_success_rate'] <= 1
        assert 'outcome_distribution' in stats
        assert 'resolution_type_distribution' in stats
        assert stats['engine_enabled'] == True
        assert stats['dice_type'] == 'd20'

class TestDiceRolling:
    """Test dice rolling mechanics."""
    
    @pytest.fixture
    def engine(self):
        return NarrativeDiceEngine()
    
    def test_d20_rolling(self, engine):
        """Test d20 dice rolling."""
        rolls = []
        for _ in range(100):
            roll = engine._roll_d20()
            rolls.extend(roll)
        
        # Check that all rolls are in valid range
        assert all(1 <= roll <= 20 for roll in rolls)
        assert len(set(rolls)) > 10  # Should have reasonable distribution
    
    def test_multiple_dice_rolling(self, engine):
        """Test multiple dice rolling systems."""
        # Test 2d10
        rolls_2d10 = engine._roll_2d10()
        assert len(rolls_2d10) == 2
        assert all(1 <= roll <= 10 for roll in rolls_2d10)
        
        # Test 3d6
        rolls_3d6 = engine._roll_3d6()
        assert len(rolls_3d6) == 3
        assert all(1 <= roll <= 6 for roll in rolls_3d6)
        
        # Test 4d6 drop lowest
        rolls_4d6dl = engine._roll_4d6_drop_lowest()
        assert len(rolls_4d6dl) == 3  # 4 rolled, 1 dropped
        assert all(1 <= roll <= 6 for roll in rolls_4d6dl)
    
    def test_advantage_disadvantage_rolling(self, engine):
        """Test advantage and disadvantage rolling mechanics."""
        # Create a mock function that returns predictable results
        mock_results = [[5], [15]]
        call_count = 0
        
        def mock_roll():
            nonlocal call_count
            result = mock_results[call_count % len(mock_results)]
            call_count += 1
            return result
        
        # Temporarily replace the dice function
        original_func = engine.dice_functions[DiceType.D20]
        engine.dice_functions[DiceType.D20] = mock_roll
        
        try:
            # Test advantage (should take higher: 15)
            call_count = 0  # Reset counter
            advantage_roll = engine._roll_dice(advantage=True)
            assert advantage_roll == [15]
            
            # Test disadvantage (should take lower: 5)
            call_count = 0  # Reset counter
            disadvantage_roll = engine._roll_dice(disadvantage=True)
            assert disadvantage_roll == [5]
        finally:
            # Restore original function
            engine.dice_functions[DiceType.D20] = original_func

class TestResolutionTypes:
    """Test different resolution types and their stat mappings."""
    
    @pytest.fixture
    def engine(self):
        return NarrativeDiceEngine()
    
    def test_stat_mappings(self, engine):
        """Test that resolution types map to correct stats."""
        assert engine.stat_mappings[ResolutionType.PERSUASION] == "charisma"
        assert engine.stat_mappings[ResolutionType.INVESTIGATION] == "intelligence"
        assert engine.stat_mappings[ResolutionType.PERCEPTION] == "perception"
        assert engine.stat_mappings[ResolutionType.ATHLETICS] == "willpower"
        assert engine.stat_mappings[ResolutionType.COMBAT] == "courage"
    
    def test_modifier_calculation(self, engine):
        """Test modifier calculation for different stats."""
        character_stats = {
            "charisma": 8,    # Should give +3 modifier
            "intelligence": 3, # Should give -2 modifier
            "perception": 5,   # Should give 0 modifier
            "courage": 10      # Should give +3 modifier (clamped)
        }
        
        # Test charisma modifier
        modifiers = engine._calculate_modifiers("hero", ResolutionType.PERSUASION, character_stats)
        assert modifiers.get("charisma") == 3
        
        # Test intelligence modifier
        modifiers = engine._calculate_modifiers("hero", ResolutionType.INVESTIGATION, character_stats)
        assert modifiers.get("intelligence") == -2
        
        # Test no modifier for average stat
        modifiers = engine._calculate_modifiers("hero", ResolutionType.PERCEPTION, character_stats)
        assert modifiers.get("perception") == 0
        
        # Test clamping at tolerance level
        modifiers = engine._calculate_modifiers("hero", ResolutionType.COMBAT, character_stats)
        assert modifiers.get("courage") == 3  # Clamped from +5 to +3

class TestOutcomeTypes:
    """Test outcome determination logic."""
    
    @pytest.fixture
    def engine(self):
        return NarrativeDiceEngine()
    
    def test_outcome_determination(self, engine):
        """Test outcome determination based on dice and margins."""
        # Test critical success (natural 20)
        outcome = engine._determine_outcome([20], 25, 15)
        assert outcome == OutcomeType.CRITICAL_SUCCESS
        
        # Test critical failure (natural 1)
        outcome = engine._determine_outcome([1], 6, 15)
        assert outcome == OutcomeType.CRITICAL_FAILURE
        
        # Test regular success with high margin
        outcome = engine._determine_outcome([15], 25, 15)
        assert outcome == OutcomeType.CRITICAL_SUCCESS
        
        # Test regular success
        outcome = engine._determine_outcome([12], 15, 15)
        assert outcome == OutcomeType.SUCCESS
        
        # Test partial success
        outcome = engine._determine_outcome([8], 12, 15)
        assert outcome == OutcomeType.PARTIAL_SUCCESS
        
        # Test failure
        outcome = engine._determine_outcome([5], 8, 15)
        assert outcome == OutcomeType.FAILURE
        
        # Test critical failure by margin
        outcome = engine._determine_outcome([2], 2, 15)
        assert outcome == OutcomeType.CRITICAL_FAILURE

class TestNarrativeBranches:
    """Test narrative branch functionality."""
    
    def test_narrative_branch_creation(self):
        """Test narrative branch data structure."""
        branch = NarrativeBranch(
            branch_id="test_branch",
            outcome_type=OutcomeType.SUCCESS,
            narrative_text="The character succeeds admirably.",
            emotional_impact="confidence, pride",
            stat_changes={"charisma": 1},
            scene_transitions=["next_scene"],
            character_consequences=["Gains reputation"]
        )
        
        assert branch.branch_id == "test_branch"
        assert branch.outcome_type == OutcomeType.SUCCESS
        assert branch.narrative_text == "The character succeeds admirably."
        assert branch.stat_changes == {"charisma": 1}
        assert len(branch.character_consequences) == 1
        
        # Test serialization
        data = branch.to_dict()
        assert data['outcome_type'] == 'success'
        assert data['emotional_impact'] == "confidence, pride"

if __name__ == "__main__":
    pytest.main([__file__])
