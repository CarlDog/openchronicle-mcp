"""
OpenChronicle Core - Character Stats Engine

Handles character statistics, modifiers, and stat-based calculations.
Extracted from character_orchestrator.py for better separation of concerns.

Author: OpenChronicle Development Team
"""

import logging
from typing import Any

from ..core.character_data import CharacterData
from ..core.character_data import CharacterStats
from ..core.character_data import CharacterStatType


logger = logging.getLogger(__name__)


class CharacterStatsEngine:
    """Handles character statistics management and calculations."""

    def __init__(self, config: dict | None = None):
        """Initialize character stats engine."""
        self.config = config or {}

        # Configuration
        self.stat_validation_enabled = self.config.get("stat_validation_enabled", True)
        self.auto_calculate_modifiers = self.config.get("auto_calculate_modifiers", True)
        self.stat_cap_enabled = self.config.get("stat_cap_enabled", True)
        self.min_stat_value = self.config.get("min_stat_value", 1)
        self.max_stat_value = self.config.get("max_stat_value", 20)

        logger.info("Character stats engine initialized")

    def get_character_stats(self, character: CharacterData) -> CharacterStats | None:
        """
        Get character statistics.

        Args:
            character: Character data object

        Returns:
            CharacterStats or None if not available
        """
        if not character or not character.stats:
            logger.debug(f"No stats available for character {getattr(character, 'character_id', 'unknown')}")
            return None

        return character.stats

    def update_character_stat(
        self,
        character: CharacterData,
        stat_type: CharacterStatType,
        new_value: int,
        reason: str,
        scene_context: str = "",
    ) -> bool:
        """
        Update a character statistic.

        Args:
            character: Character data object
            stat_type: Type of stat to update
            new_value: New stat value
            reason: Reason for the update
            scene_context: Optional scene context

        Returns:
            True if update successful, False otherwise
        """
        try:
            if not character or not character.stats:
                logger.error("No character or stats available for update")
                return False

            # Validate new value if enabled
            if self.stat_validation_enabled:
                if not self._validate_stat_value(stat_type, new_value):
                    logger.warning(f"Stat value {new_value} invalid for {stat_type.value}")
                    return False

            # Apply stat caps if enabled
            if self.stat_cap_enabled:
                new_value = max(self.min_stat_value, min(self.max_stat_value, new_value))

            # Update stat
            character.stats.update_stat(stat_type, new_value, reason, scene_context)

            logger.info(f"Updated {stat_type.value} to {new_value} for character {character.character_id}: {reason}")

        except (ValueError, TypeError, AttributeError) as e:
            logger.exception("Invalid data or parameters updating character stat")
            return False
        except Exception as e:
            logger.exception("Unexpected error updating character stat")
            return False
        else:
            return True

    def get_effective_stat(self, character: CharacterData, stat_type: CharacterStatType) -> int | None:
        """
        Get effective character stat value including modifiers.

        Args:
            character: Character data object
            stat_type: Type of stat to get

        Returns:
            Effective stat value or None if not available
        """
        try:
            stats = self.get_character_stats(character)
            if not stats:
                result = None
            else:
                base_value = stats.get_effective_stat(stat_type)

                # Apply additional modifiers if auto-calculation is enabled
                if self.auto_calculate_modifiers:
                    modifier = self._calculate_additional_modifiers(character, stat_type)
                    result = base_value + modifier if base_value is not None else None
                else:
                    result = base_value

        except (ValueError, TypeError, AttributeError) as e:
            logger.exception(f"Invalid data calculating effective stat {stat_type.value}")
            return None
        except Exception as e:
            logger.exception(f"Unexpected error getting effective stat {stat_type.value}")
            return None
        else:
            return result

    def calculate_stat_modifier(self, stat_value: int) -> int:
        """
        Calculate D&D-style stat modifier from stat value.

        Args:
            stat_value: Base stat value

        Returns:
            Stat modifier
        """
        return (stat_value - 10) // 2

    def get_all_stat_modifiers(self, character: CharacterData) -> dict[str, int]:
        """
        Get all stat modifiers for character.

        Args:
            character: Character data object

        Returns:
            Dictionary of stat modifiers
        """
        modifiers = {}

        if not character or not character.stats:
            return modifiers

        for stat_type in CharacterStatType:
            effective_value = self.get_effective_stat(character, stat_type)
            if effective_value is not None:
                modifiers[stat_type.value] = self.calculate_stat_modifier(effective_value)

        return modifiers

    def _validate_stat_value(self, stat_type: CharacterStatType, value: int) -> bool:
        """
        Validate a stat value.

        Args:
            stat_type: Type of stat
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        # Basic range validation
        if value < self.min_stat_value or value > self.max_stat_value:
            return False

        # Stat-specific validation could be added here
        # For example, certain stats might have different valid ranges

        return True

    def _calculate_additional_modifiers(self, character: CharacterData, stat_type: CharacterStatType) -> int:
        """
        Calculate additional modifiers from equipment, effects, etc.

        Args:
            character: Character data object
            stat_type: Type of stat

        Returns:
            Additional modifier value
        """
        modifier = 0

        # Check for temporary effects (could be stored in metadata)
        temp_effects = character.metadata.get("temporary_effects", {})
        stat_effects = temp_effects.get(stat_type.value, [])

        for effect in stat_effects:
            if isinstance(effect, dict):
                modifier += effect.get("modifier", 0)
            elif isinstance(effect, (int, float)):
                modifier += int(effect)

        # Check for equipment bonuses (could be stored in metadata)
        equipment_bonuses = character.metadata.get("equipment_bonuses", {})
        stat_bonus = equipment_bonuses.get(stat_type.value, 0)
        modifier += stat_bonus

        return modifier

    def perform_stat_check(
        self,
        character: CharacterData,
        stat_type: CharacterStatType,
        difficulty_class: int = 10,
        advantage: bool = False,
        disadvantage: bool = False,
    ) -> dict[str, Any]:
        """
        Perform a stat check (d20 + modifier vs DC).

        Args:
            character: Character data object
            stat_type: Stat to use for check
            difficulty_class: Target DC
            advantage: Roll with advantage
            disadvantage: Roll with disadvantage

        Returns:
            Dictionary containing check results
        """
        try:
            import random

            # Get stat modifier
            effective_stat = self.get_effective_stat(character, stat_type)
            if effective_stat is None:
                return {
                    "success": False,
                    "error": f"No {stat_type.value} stat available",
                }

            modifier = self.calculate_stat_modifier(effective_stat)

            # Roll d20
            if advantage and not disadvantage:
                roll1, roll2 = random.randint(1, 20), random.randint(1, 20)
                roll = max(roll1, roll2)
                roll_type = "advantage"
                rolls = [roll1, roll2]
            elif disadvantage and not advantage:
                roll1, roll2 = random.randint(1, 20), random.randint(1, 20)
                roll = min(roll1, roll2)
                roll_type = "disadvantage"
                rolls = [roll1, roll2]
            else:
                roll = random.randint(1, 20)
                roll_type = "normal"
                rolls = [roll]

            # Calculate total
            total = roll + modifier
            success = total >= difficulty_class

            result = {
                "character_id": character.character_id,
                "stat_type": stat_type.value,
                "roll": roll,
                "rolls": rolls,
                "roll_type": roll_type,
                "modifier": modifier,
                "total": total,
                "difficulty_class": difficulty_class,
                "success": success,
                "margin": total - difficulty_class,
            }

            logger.info(
                f"Stat check for {character.character_id} {stat_type.value}: "
                f"{roll}+{modifier}={total} vs DC{difficulty_class} ({'SUCCESS' if success else 'FAILURE'})"
            )

        except Exception as e:
            logger.exception("Error performing stat check")
            return {"success": False, "error": str(e)}
        else:
            return result

    def get_stat_summary(self, character: CharacterData) -> dict[str, Any]:
        """
        Get comprehensive stat summary for character.

        Args:
            character: Character data object

        Returns:
            Dictionary containing stat summary
        """
        try:
            if not character or not character.stats:
                summary = {"character_id": getattr(character, "character_id", "unknown"), "has_stats": False}
            else:
                summary = {
                    "character_id": character.character_id,
                    "has_stats": True,
                    "stats": {},
                    "modifiers": {},
                    "total_stat_points": 0,
                }

                # Get all stats and modifiers
                for stat_type in CharacterStatType:
                    effective_value = self.get_effective_stat(character, stat_type)
                    if effective_value is not None:
                        modifier = self.calculate_stat_modifier(effective_value)
                        summary["stats"][stat_type.value] = effective_value
                        summary["modifiers"][stat_type.value] = modifier
                        summary["total_stat_points"] += effective_value

                # Calculate average stat
                if summary["stats"]:
                    summary["average_stat"] = summary["total_stat_points"] / len(summary["stats"])

        except Exception as e:
            logger.exception("Error getting stat summary")
            return {"character_id": getattr(character, "character_id", "unknown"), "error": str(e)}
        else:
            return summary

    def get_stats_status(self) -> dict[str, Any]:
        """Get stats engine status."""
        return {
            "engine_status": "active",
            "stat_validation_enabled": self.stat_validation_enabled,
            "auto_calculate_modifiers": self.auto_calculate_modifiers,
            "stat_cap_enabled": self.stat_cap_enabled,
            "stat_range": f"{self.min_stat_value}-{self.max_stat_value}",
        }
