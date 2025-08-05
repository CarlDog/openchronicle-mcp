"""
OpenChronicle Core - Mechanics System Tests

Test the extracted mechanics system components.
Validates Day 3 mechanics extraction completion.

Author: OpenChronicle Development Team
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from core.narrative_systems.mechanics import (
    DiceEngine, NarrativeBranchingEngine, MechanicsOrchestrator,
    DiceType, ResolutionType, DifficultyLevel, OutcomeType,
    MechanicsRequest, ResolutionConfig
)


class TestDiceEngine:
    """Test dice rolling mechanics."""
    
    def test_dice_engine_initialization(self):
        """Test dice engine initializes correctly."""
        engine = DiceEngine()
        assert engine.config is not None
        assert engine.config.dice_type == DiceType.D20
    
    def test_basic_d20_roll(self):
        """Test basic d20 rolling."""
        engine = DiceEngine()
        roll = engine.roll_d20()
        
        assert roll.dice_type == DiceType.D20
        assert len(roll.rolls) == 1
        assert 1 <= roll.rolls[0] <= 20
        assert roll.total == roll.rolls[0]
    
    def test_roll_with_modifier(self):
        """Test dice rolling with modifiers."""
        engine = DiceEngine()
        roll = engine.roll_d20(modifier=5)
        
        assert roll.modifier == 5
        assert roll.total == roll.rolls[0] + 5
    
    def test_advantage_roll(self):
        """Test advantage rolling mechanism."""
        engine = DiceEngine()
        roll = engine.roll_d20(advantage=True)
        
        assert roll.advantage is True
        assert len(roll.rolls) == 1  # Result is the higher of two rolls
        assert 1 <= roll.rolls[0] <= 20
    
    def test_difficulty_check_calculation(self):
        """Test difficulty check calculations."""
        engine = DiceEngine()
        
        # Mock a successful roll
        roll = engine.roll_d20()
        roll.total = 18
        
        success, margin, outcome = engine.calculate_difficulty_check(
            roll, difficulty=15, character_skill=2
        )
        
        assert success is True
        assert margin == (18 + 2) - 15  # total + skill - difficulty
        assert outcome in [OutcomeType.SUCCESS, OutcomeType.CRITICAL_SUCCESS]
    
    def test_dice_string_parsing(self):
        """Test dice notation parsing."""
        engine = DiceEngine()
        
        # Test basic notation
        roll = engine.roll_multiple("1d20+5")
        assert roll.dice_type == DiceType.D20
        assert roll.modifier == 5
        
        # Test different dice types
        roll = engine.roll_multiple("1d6")
        assert roll.dice_type == DiceType.D6


class TestNarrativeBranchingEngine:
    """Test narrative branching mechanics."""
    
    def test_branching_engine_initialization(self):
        """Test branching engine initializes correctly."""
        engine = NarrativeBranchingEngine()
        assert engine.outcome_templates is not None
        assert OutcomeType.CRITICAL_SUCCESS in engine.outcome_templates
    
    def test_branch_creation_for_success(self):
        """Test branch creation for successful outcomes."""
        engine = NarrativeBranchingEngine()
        
        # Create mock resolution result
        mock_result = Mock()
        mock_result.resolution_type = ResolutionType.SKILL_CHECK
        mock_result.outcome = OutcomeType.SUCCESS
        mock_result.character_id = "test_character"
        mock_result.success_margin = 5
        
        branches = engine.create_narrative_branches(mock_result)
        
        assert len(branches) >= 1
        assert all(branch.probability > 0 for branch in branches)
        assert all(branch.description for branch in branches)
    
    def test_branch_probability_normalization(self):
        """Test that branch probabilities are normalized."""
        engine = NarrativeBranchingEngine()
        
        mock_result = Mock()
        mock_result.resolution_type = ResolutionType.COMBAT_ACTION
        mock_result.outcome = OutcomeType.CRITICAL_SUCCESS
        mock_result.character_id = "test_character"
        mock_result.success_margin = 15
        
        branches = engine.create_narrative_branches(mock_result, max_branches=3)
        
        total_probability = sum(branch.probability for branch in branches)
        assert abs(total_probability - 1.0) < 0.01  # Allow small floating point errors


class TestMechanicsOrchestrator:
    """Test mechanics orchestrator integration."""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initializes correctly."""
        orchestrator = MechanicsOrchestrator()
        assert orchestrator.dice_engine is not None
        assert orchestrator.branching_engine is not None
        assert orchestrator.operation_count == 0
    
    @pytest.mark.asyncio
    async def test_action_resolution(self):
        """Test complete action resolution."""
        orchestrator = MechanicsOrchestrator()
        
        request = MechanicsRequest(
            operation_type="resolve_action",
            resolution_type=ResolutionType.SKILL_CHECK,
            character_id="test_character",
            difficulty=DifficultyLevel.MODERATE
        )
        
        result = await orchestrator.resolve_action(request)
        
        assert result.success is True
        assert result.resolution_result is not None
        assert result.resolution_result.character_id == "test_character"
        assert result.resolution_result.resolution_type == ResolutionType.SKILL_CHECK
        assert len(result.narrative_branches) > 0
    
    @pytest.mark.asyncio
    async def test_action_simulation(self):
        """Test action simulation functionality."""
        orchestrator = MechanicsOrchestrator()
        
        request = MechanicsRequest(
            operation_type="simulate",
            resolution_type=ResolutionType.SKILL_CHECK,
            character_id="test_character"
        )
        
        stats = await orchestrator.simulate_action(request, iterations=10)
        
        assert "iterations" in stats
        assert "success_rate" in stats
        assert "average_roll" in stats
        assert stats["iterations"] == 10
    
    def test_character_performance_tracking(self):
        """Test character performance tracking."""
        orchestrator = MechanicsOrchestrator()
        
        # Simulate some actions to build performance data
        mock_result = Mock()
        mock_result.outcome = OutcomeType.SUCCESS
        mock_result.resolution_type = ResolutionType.SKILL_CHECK
        mock_result.dice_roll = Mock()
        mock_result.dice_roll.total = 15
        
        # Update performance
        orchestrator._update_character_performance("test_char", mock_result)
        
        performance = orchestrator.character_performance["test_char"]
        assert performance.total_actions == 1
        assert performance.successes == 1
        assert performance.calculate_success_rate() == 1.0
    
    def test_orchestrator_stats(self):
        """Test orchestrator statistics."""
        orchestrator = MechanicsOrchestrator()
        orchestrator.operation_count = 5
        orchestrator.success_count = 4
        
        stats = orchestrator.get_orchestrator_stats()
        
        assert stats["total_operations"] == 5
        assert stats["success_count"] == 4
        assert stats["success_rate"] == 0.8


class TestMechanicsModels:
    """Test mechanics data models."""
    
    def test_resolution_result_serialization(self):
        """Test resolution result to/from dict."""
        from core.narrative_systems.mechanics.mechanics_models import (
            ResolutionResult, DiceRoll
        )
        
        dice_roll = DiceRoll(
            dice_type=DiceType.D20,
            rolls=[15],
            modifier=3,
            total=18
        )
        
        result = ResolutionResult(
            resolution_type=ResolutionType.SKILL_CHECK,
            outcome=OutcomeType.SUCCESS,
            dice_roll=dice_roll,
            difficulty_check=15,
            success_margin=3,
            character_id="test_char"
        )
        
        # Test serialization
        data = result.to_dict()
        assert data["resolution_type"] == "skill_check"
        assert data["outcome"] == "success"
        assert data["character_id"] == "test_char"
        
        # Test deserialization
        result2 = ResolutionResult.from_dict(data)
        assert result2.resolution_type == result.resolution_type
        assert result2.outcome == result.outcome
        assert result2.character_id == result.character_id


# Integration test
@pytest.mark.asyncio
async def test_complete_mechanics_workflow():
    """Test complete mechanics system workflow."""
    orchestrator = MechanicsOrchestrator()
    
    # Create a skill check request
    request = MechanicsRequest(
        operation_type="resolve_action",
        resolution_type=ResolutionType.SOCIAL_INTERACTION,
        character_id="protagonist",
        difficulty=DifficultyLevel.HARD,
        modifiers={"charisma_bonus": 3, "situation_penalty": -1}
    )
    
    # Resolve the action
    result = await orchestrator.resolve_action(request)
    
    # Validate complete workflow
    assert result.success is True
    assert result.resolution_result is not None
    assert result.resolution_result.resolution_type == ResolutionType.SOCIAL_INTERACTION
    assert len(result.narrative_branches) > 0
    assert result.narrative_prompt != ""
    
    # Check character performance was updated
    performance = orchestrator.character_performance.get("protagonist")
    assert performance is not None
    assert performance.total_actions == 1
    
    # Verify branches have valid data
    for branch in result.narrative_branches:
        assert branch.branch_id != ""
        assert branch.description != ""
        assert 0 <= branch.probability <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
