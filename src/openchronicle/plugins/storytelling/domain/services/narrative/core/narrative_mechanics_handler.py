"""
OpenChronicle Core - Narrative Mechanics Handler

Handles dice rolling, branching logic, and narrative mechanics.
Extracted from narrative_orchestrator.py for better separation of concerns.

Author: OpenChronicle Development Team
"""

import random
import re
from datetime import datetime
from typing import Any

from openchronicle.shared.logging_system import log_error
from openchronicle.shared.logging_system import log_info
from openchronicle.shared.logging_system import log_warning


class NarrativeMechanicsHandler:
    """Handles narrative mechanics including dice rolling and branching."""

    def __init__(self, config: dict[str, Any] = None):
        """Initialize mechanics handler with configuration."""
        self.config = config or {}
        self.default_dice_sides = self.config.get("default_dice_sides", 20)
        self.difficulty_scaling = self.config.get("difficulty_scaling", "balanced")
        self.randomness_factor = self.config.get("randomness_factor", 0.3)

    def roll_dice(self, dice_expression: str) -> dict[str, Any]:
        """Roll dice using standard dice notation (e.g., '1d20', '3d6+2')."""
        try:
            # Parse dice expression (e.g., "1d20", "3d6+2", "d6")
            pattern = r"^(\d*)d(\d+)([+-]\d+)?$"
            match = re.match(pattern, dice_expression.lower().strip())

            if not match:
                return {
                    "success": False,
                    "error": f"Invalid dice expression: {dice_expression}",
                    "expression": dice_expression,
                }

            # Extract components
            num_dice = int(match.group(1)) if match.group(1) else 1
            die_type = int(match.group(2))
            modifier = int(match.group(3)) if match.group(3) else 0

            # Validate parameters
            if num_dice < 1 or num_dice > 100:
                return {
                    "success": False,
                    "error": "Number of dice must be between 1 and 100",
                    "expression": dice_expression,
                }

            if die_type < 2 or die_type > 1000:
                return {
                    "success": False,
                    "error": "Die type must be between 2 and 1000",
                    "expression": dice_expression,
                }

            # Roll the dice
            rolls = []
            for _ in range(num_dice):
                rolls.append(random.randint(1, die_type))

            total = sum(rolls) + modifier

            result = {
                "success": True,
                "expression": dice_expression,
                "num_dice": num_dice,
                "die_type": die_type,
                "modifier": modifier,
                "rolls": rolls,
                "total": total,
                "timestamp": datetime.now().isoformat(),
            }

            log_info(
                f"Dice roll: {dice_expression} = {total} (rolls: {rolls}, modifier: {modifier})"
            )

        except (ValueError, TypeError) as e:
            log_error(f"Invalid dice expression parameters '{dice_expression}': {e}")
            return {"success": False, "error": f"Invalid dice parameters: {str(e)}", "expression": dice_expression}
        except (AttributeError, KeyError) as e:
            log_error(f"Dice rolling data access error '{dice_expression}': {e}")
            return {"success": False, "error": f"Data access error: {str(e)}", "expression": dice_expression}
        except Exception as e:
            log_error(f"Unexpected error rolling dice '{dice_expression}': {e}")
            return {"success": False, "error": f"Unexpected error: {str(e)}", "expression": dice_expression}
        else:
            return result

    def evaluate_narrative_branch(self, scenario: dict[str, Any]) -> dict[str, Any]:
        """Evaluate narrative branching scenarios."""
        try:
            story_id = scenario.get("story_id", "unknown")
            character_id = scenario.get("character_id", "unknown")
            branch_type = scenario.get("type", "unknown")
            scene_id = scenario.get("scene_id", "unknown")
            choices = scenario.get("choices", [])
            narrative_tension = scenario.get("narrative_tension", 0.5)

            # Basic branch evaluation logic
            evaluation = {
                "success": True,
                "story_id": story_id,
                "character_id": character_id,
                "branch_type": branch_type,
                "scene_id": scene_id,
                "narrative_tension": narrative_tension,
                "recommendations": [],
            }

            # Select option if choices are provided
            if choices:
                # Apply randomness factor to selection
                if random.random() < self.randomness_factor:
                    selected_option = random.choice(choices)
                    evaluation["selection_method"] = "random"
                else:
                    # Use weighted selection based on narrative tension
                    selected_option = self._weighted_choice_selection(choices, narrative_tension)
                    evaluation["selection_method"] = "weighted"

                evaluation["selected_option"] = selected_option
                evaluation["available_choices"] = choices

            # Evaluate based on branch type
            if branch_type == "character_decision":
                evaluation["recommendations"].append(
                    "Consider character motivations and past decisions"
                )
                evaluation["difficulty"] = "moderate"

            elif branch_type == "plot_progression":
                evaluation["recommendations"].append(
                    "Ensure plot consistency with established elements"
                )
                evaluation["difficulty"] = "high"

            elif branch_type == "dialogue_choice":
                evaluation["recommendations"].append(
                    "Maintain character voice and relationship dynamics"
                )
                evaluation["difficulty"] = "low"

            elif branch_type == "conflict_resolution":
                evaluation["recommendations"].append(
                    "Balance narrative tension with character agency"
                )
                evaluation["difficulty"] = "high"

            else:
                evaluation["recommendations"].append(
                    "Generic narrative evaluation applied"
                )
                evaluation["difficulty"] = "moderate"

            # Calculate tension modifier based on evaluation
            tension_modifier = scenario.get("tension_impact", 0.0)
            if branch_type == "conflict_resolution":
                tension_modifier *= 1.5  # Conflicts have higher impact
            elif branch_type == "dialogue_choice":
                tension_modifier *= 0.5  # Dialogue has lower impact

            evaluation["tension_modifier"] = tension_modifier
            evaluation["timestamp"] = datetime.now().isoformat()

            log_info(
                f"Evaluated narrative branch for {character_id} in {story_id}: {branch_type}"
            )

        except Exception as e:
            log_error(f"Error evaluating narrative branch: {e}")
            return {"success": False, "error": str(e), "scenario": scenario}
        else:
            return evaluation

    def _weighted_choice_selection(self, choices: list[Any], narrative_tension: float) -> Any:
        """Select choice based on weighted algorithm considering narrative tension."""
        if not choices:
            return None

        # Simple weighted selection - prefer choices that affect tension appropriately
        # High tension: prefer calming choices
        # Low tension: prefer escalating choices
        if narrative_tension > 0.7:
            # High tension - prefer first half of choices (assume they're calming)
            return choices[0] if len(choices) == 1 else choices[random.randint(0, len(choices) // 2)]
        elif narrative_tension < 0.3:
            # Low tension - prefer last half of choices (assume they're escalating)
            return choices[-1] if len(choices) == 1 else choices[random.randint(len(choices) // 2, len(choices) - 1)]
        else:
            # Moderate tension - any choice is fine
            return random.choice(choices)

    def calculate_difficulty_modifier(self, base_difficulty: str, context: dict[str, Any] = None) -> float:
        """Calculate difficulty modifier based on scaling setting and context."""
        context = context or {}

        # Base difficulty values
        difficulty_values = {
            "trivial": 0.1,
            "easy": 0.3,
            "moderate": 0.5,
            "hard": 0.7,
            "extreme": 0.9
        }

        base_value = difficulty_values.get(base_difficulty, 0.5)

        # Apply scaling based on configuration
        if self.difficulty_scaling == "forgiving":
            return max(0.1, base_value - 0.2)
        elif self.difficulty_scaling == "challenging":
            return min(0.9, base_value + 0.2)
        else:  # balanced
            return base_value

    def generate_random_event(self, event_type: str = "general") -> dict[str, Any]:
        """Generate a random narrative event."""
        try:
            event_templates = {
                "general": [
                    "A sudden noise breaks the silence",
                    "An unexpected visitor arrives",
                    "The weather changes dramatically",
                    "A memory surfaces unexpectedly",
                    "Something important is discovered"
                ],
                "social": [
                    "A misunderstanding arises between characters",
                    "An old friend appears unexpectedly",
                    "A secret is accidentally revealed",
                    "Someone asks for help",
                    "A celebration is interrupted"
                ],
                "conflict": [
                    "A challenge must be faced immediately",
                    "Opposition appears to block progress",
                    "A moral dilemma presents itself",
                    "Time runs short for an important decision",
                    "Resources become scarce"
                ]
            }

            templates = event_templates.get(event_type, event_templates["general"])
            selected_event = random.choice(templates)

            # Add some randomization details
            intensity = random.choice(["mild", "moderate", "intense"])
            timing = random.choice(["immediate", "delayed", "gradual"])

            return {
                "success": True,
                "event_type": event_type,
                "description": selected_event,
                "intensity": intensity,
                "timing": timing,
                "tension_impact": random.uniform(-0.3, 0.3),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            log_error(f"Error generating random event: {e}")
            return {"success": False, "error": str(e)}

    def get_mechanics_status(self) -> dict[str, Any]:
        """Get current mechanics handler status."""
        return {
            "handler_status": "active",
            "configuration": {
                "default_dice_sides": self.default_dice_sides,
                "difficulty_scaling": self.difficulty_scaling,
                "randomness_factor": self.randomness_factor,
            },
            "supported_operations": [
                "roll_dice",
                "evaluate_narrative_branch",
                "calculate_difficulty_modifier",
                "generate_random_event"
            ]
        }
