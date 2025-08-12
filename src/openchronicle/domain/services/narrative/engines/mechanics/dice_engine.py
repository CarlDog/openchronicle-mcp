"""
OpenChronicle Core - Dice Engine Component

Handles all dice rolling mechanics and calculations.
Extracted from NarrativeDiceEngine for modular architecture.

Author: OpenChronicle Development Team
"""

import random
from typing import Any

from openchronicle.shared.logging_system import (
    get_logger,
    log_error_with_context,
    log_system_event,
)

from ...shared.narrative_exceptions import NarrativeSystemError
from .mechanics_models import DiceRoll
from .mechanics_models import DiceType
from .mechanics_models import DifficultyLevel
from .mechanics_models import OutcomeType
from .mechanics_models import ResolutionConfig


class DiceEngine:
    """Handles dice rolling mechanics and calculations."""

    def __init__(self, config: ResolutionConfig | None = None):
        """
        Initialize dice engine.

        Args:
            config: Optional resolution configuration
        """
        self.config = config or ResolutionConfig()
        self.logger = get_logger("openchronicle.mechanics.dice")

        # Dice configurations
        self.dice_configs = {
            DiceType.D4: {"sides": 4, "min": 1},
            DiceType.D6: {"sides": 6, "min": 1},
            DiceType.D8: {"sides": 8, "min": 1},
            DiceType.D10: {"sides": 10, "min": 0},  # D10 traditionally 0-9
            DiceType.D12: {"sides": 12, "min": 1},
            DiceType.D20: {"sides": 20, "min": 1},
            DiceType.D100: {"sides": 100, "min": 1},
            DiceType.FUDGE: {"sides": 3, "min": -1},  # -1, 0, +1
            DiceType.COIN: {"sides": 2, "min": 0},  # 0 (tails), 1 (heads)
        }

        # Difficulty mappings
        self.difficulty_mappings = {
            DifficultyLevel.TRIVIAL: 5,
            DifficultyLevel.EASY: 10,
            DifficultyLevel.MODERATE: 15,
            DifficultyLevel.HARD: 20,
            DifficultyLevel.VERY_HARD: 25,
            DifficultyLevel.LEGENDARY: 30,
        }

        log_system_event(
            "dice_engine_initialized",
            f"Dice engine ready with {self.config.dice_type.value} dice",
        )

    def roll_dice(
        self,
        dice_type: DiceType = None,
        count: int = 1,
        modifier: int = 0,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> DiceRoll:
        """
        Roll dice with specified parameters.

        Args:
            dice_type: Type of dice to roll
            count: Number of dice to roll
            modifier: Modifier to add to total
            advantage: Roll twice, take higher
            disadvantage: Roll twice, take lower

        Returns:
            DiceRoll with results
        """
        if dice_type is None:
            dice_type = self.config.dice_type

        try:
            # Handle advantage/disadvantage for single die rolls
            if (advantage or disadvantage) and count == 1:
                roll1 = self._roll_single_die(dice_type)
                roll2 = self._roll_single_die(dice_type)

                if advantage:
                    rolls = [max(roll1, roll2)]
                else:  # disadvantage
                    rolls = [min(roll1, roll2)]
            else:
                # Normal dice rolling
                rolls = []
                for _ in range(count):
                    roll = self._roll_single_die(dice_type)
                    rolls.append(roll)

            # Create dice roll object
            dice_roll = DiceRoll(
                dice_type=dice_type,
                rolls=rolls,
                modifier=modifier,
                advantage=advantage,
                disadvantage=disadvantage,
                total=sum(rolls) + modifier,
            )

            log_system_event(
                "dice_rolled",
                f"Rolled {count}x{dice_type.value}: {rolls} + {modifier} = {dice_roll.total}",
            )

            return dice_roll

        except Exception as e:
            log_error_with_context(
                e,
                {
                    "operation": "roll_dice",
                    "dice_type": getattr(dice_type, "value", str(dice_type)),
                    "count": count,
                    "modifier": modifier,
                    "advantage": advantage,
                    "disadvantage": disadvantage,
                },
            )
            raise NarrativeSystemError(f"Dice rolling failed: {e}")

    def _roll_single_die(self, dice_type: DiceType) -> int:
        """Roll a single die of specified type."""
        config = self.dice_configs.get(dice_type)
        if not config:
            raise ValueError(f"Unknown dice type: {dice_type}")

        if dice_type == DiceType.FUDGE:
            # Fudge dice: -1, 0, +1
            return random.randint(-1, 1)
        if dice_type == DiceType.COIN:
            # Coin flip: 0 (tails), 1 (heads)
            return random.randint(0, 1)
        if dice_type == DiceType.D10:
            # D10 traditionally 0-9
            return random.randint(0, 9)
        # Standard dice
        return random.randint(config["min"], config["sides"])

    def roll_d20(
        self, modifier: int = 0, advantage: bool = False, disadvantage: bool = False
    ) -> DiceRoll:
        """Convenience method for d20 rolls."""
        return self.roll_dice(DiceType.D20, 1, modifier, advantage, disadvantage)

    def roll_d100(self, modifier: int = 0) -> DiceRoll:
        """Convenience method for percentile rolls."""
        return self.roll_dice(DiceType.D100, 1, modifier)

    def roll_multiple(self, dice_string: str) -> DiceRoll:
        """
        Roll dice from string notation (e.g., "3d6+2", "1d20", "2d10-1").

        Args:
            dice_string: Dice notation string

        Returns:
            DiceRoll result
        """
        try:
            # Parse dice string
            count, dice_type, modifier = self._parse_dice_string(dice_string)
            return self.roll_dice(dice_type, count, modifier)

        except Exception as e:
            log_error_with_context(
                e,
                {
                    "operation": "roll_multiple",
                    "dice_string": dice_string,
                },
            )
            raise NarrativeSystemError(f"Invalid dice notation: {dice_string}")

    def _parse_dice_string(self, dice_string: str) -> tuple[int, DiceType, int]:
        """Parse dice notation string into components."""
        dice_string = dice_string.lower().replace(" ", "")

        # Handle modifier
        modifier = 0
        if "+" in dice_string:
            parts = dice_string.split("+")
            dice_part = parts[0]
            modifier = int(parts[1])
        elif "-" in dice_string and not dice_string.startswith("-"):
            parts = dice_string.split("-")
            dice_part = parts[0]
            modifier = -int(parts[1])
        else:
            dice_part = dice_string

        # Parse count and dice type
        if "d" in dice_part:
            count_str, dice_str = dice_part.split("d", 1)
            count = int(count_str) if count_str else 1

            # Map dice string to DiceType
            dice_map = {
                "4": DiceType.D4,
                "6": DiceType.D6,
                "8": DiceType.D8,
                "10": DiceType.D10,
                "12": DiceType.D12,
                "20": DiceType.D20,
                "100": DiceType.D100,
                "f": DiceType.FUDGE,
                "fudge": DiceType.FUDGE,
            }

            dice_type = dice_map.get(dice_str, DiceType.D20)
        else:
            # Just a number, assume d20
            count = 1
            dice_type = DiceType.D20

        return count, dice_type, modifier

    def calculate_difficulty_check(
        self,
        dice_roll: DiceRoll,
        difficulty: int,
        character_skill: int = 0,
        situation_modifiers: dict[str, int] = None,
    ) -> tuple[bool, int, OutcomeType]:
        """
        Calculate if a dice roll succeeds against difficulty.

        Args:
            dice_roll: The dice roll result
            difficulty: Target difficulty number
            character_skill: Character's skill bonus
            situation_modifiers: Additional modifiers

        Returns:
            Tuple of (success, margin, outcome_type)
        """
        if situation_modifiers is None:
            situation_modifiers = {}

        # Calculate total
        total_modifier = character_skill + sum(situation_modifiers.values())
        final_total = dice_roll.total + total_modifier

        # Calculate success margin
        margin = final_total - difficulty
        success = margin >= 0

        # Determine outcome type
        if dice_roll.dice_type == DiceType.D20:
            # Check for critical results on d20
            natural_roll = dice_roll.rolls[0] if dice_roll.rolls else 0

            if natural_roll >= self.config.critical_success_threshold:
                outcome = OutcomeType.CRITICAL_SUCCESS
            elif natural_roll <= self.config.critical_failure_threshold:
                outcome = OutcomeType.CRITICAL_FAILURE
            elif success:
                if margin >= 10 or margin >= 5:
                    outcome = OutcomeType.SUCCESS
                else:
                    outcome = OutcomeType.PARTIAL_SUCCESS
            elif margin <= -10:
                outcome = OutcomeType.CRITICAL_FAILURE
            else:
                outcome = OutcomeType.FAILURE
        # Non-d20 outcomes
        elif success:
            if margin >= difficulty // 2:
                outcome = OutcomeType.CRITICAL_SUCCESS
            elif margin >= 0:
                outcome = OutcomeType.SUCCESS
            else:
                outcome = OutcomeType.PARTIAL_SUCCESS
        elif margin <= -difficulty // 2:
            outcome = OutcomeType.CRITICAL_FAILURE
        else:
            outcome = OutcomeType.FAILURE

        return success, margin, outcome

    def get_difficulty_dc(self, difficulty: DifficultyLevel) -> int:
        """Get DC for difficulty level."""
        return self.difficulty_mappings.get(difficulty, 15)

    def simulate_rolls(
        self,
        dice_type: DiceType,
        count: int = 1,
        iterations: int = 1000,
        modifier: int = 0,
    ) -> dict[str, Any]:
        """
        Simulate multiple dice rolls for statistical analysis.

        Args:
            dice_type: Type of dice to simulate
            count: Number of dice per roll
            iterations: Number of simulations
            modifier: Modifier to apply

        Returns:
            Statistics dictionary
        """
        results = []

        for _ in range(iterations):
            roll = self.roll_dice(dice_type, count, modifier)
            results.append(roll.total)

        # Calculate statistics
        avg = sum(results) / len(results)
        minimum = min(results)
        maximum = max(results)

        # Count frequency
        frequency = {}
        for result in results:
            frequency[result] = frequency.get(result, 0) + 1

        return {
            "iterations": iterations,
            "average": avg,
            "minimum": minimum,
            "maximum": maximum,
            "frequency": frequency,
            "results": results[:100],  # First 100 for sampling
        }

    def validate_roll_parameters(
        self, dice_type: DiceType, count: int, modifier: int
    ) -> bool:
        """Validate dice roll parameters."""
        if count <= 0 or count > 100:  # Reasonable limits
            return False

        if abs(modifier) > 1000:  # Reasonable modifier limits
            return False

        if dice_type not in self.dice_configs:
            return False

        return True

    def get_dice_statistics(self, dice_type: DiceType) -> dict[str, Any]:
        """Get statistical information for dice type."""
        config = self.dice_configs.get(dice_type, {})

        if dice_type == DiceType.FUDGE:
            return {"min": -1, "max": 1, "average": 0.0, "sides": 3, "type": "fudge"}
        if dice_type == DiceType.COIN:
            return {"min": 0, "max": 1, "average": 0.5, "sides": 2, "type": "coin"}
        sides = config.get("sides", 1)
        min_val = config.get("min", 1)
        max_val = sides if dice_type != DiceType.D10 else 9

        return {
            "min": min_val,
            "max": max_val,
            "average": (min_val + max_val) / 2,
            "sides": sides,
            "type": "standard",
        }
