"""
Character Statistics Component

Specialized component for managing character RPG-style statistics, behavior influences,
and stat-based progression. Extracted from character_stat_engine.py.
"""

import logging
from datetime import datetime
from datetime import timedelta
from typing import Any

from ..core.character_base import CharacterBehaviorProvider
from ..core.character_base import CharacterEngineBase
from ..core.character_base import CharacterValidationProvider
from ..core.character_data import CharacterBehaviorInfluence
from ..core.character_data import CharacterBehaviorType
from ..core.character_data import CharacterStatCategory
from ..core.character_data import CharacterStats
from ..core.character_data import CharacterStatType


logger = logging.getLogger(__name__)


class StatsBehaviorEngine(
    CharacterEngineBase, CharacterBehaviorProvider, CharacterValidationProvider
):
    """
    Manages character statistics, trait-based behavior, and stat progression.

    Provides RPG-style character traits that influence behavior, dialogue,
    decision-making, and character development over time.
    """

    def __init__(self, config: dict | None = None):
        """Initialize the stats behavior engine."""
        super().__init__(config)

        # Configuration parameters
        self.stat_range = self.config.get("stat_range", (1, 10))
        self.default_stat_value = self.config.get("default_stat_value", 5)
        self.progression_enabled = self.config.get("progression_enabled", True)
        self.temporary_modifier_max_duration = self.config.get(
            "temp_modifier_max_hours", 24
        )

        # Behavior templates and interactions
        self.behavior_templates: dict[str, dict] = self._initialize_behavior_templates()
        self.stat_interactions: dict[
            str, list[tuple[CharacterStatType, CharacterStatType]]
        ] = self._initialize_stat_interactions()

        # Stat influence thresholds
        self.thresholds = {
            "very_low": (1, 2),
            "low": (3, 4),
            "average": (5, 6),
            "high": (7, 8),
            "very_high": (9, 10),
        }

        self.logger.info("Stats behavior engine initialized")

    def initialize_character(self, character_id: str, **kwargs) -> CharacterStats:
        """Initialize character statistics."""
        if character_id in self.character_data:
            stats = self.character_data[character_id]

            # Update stats if provided in kwargs
            for stat_name, value in kwargs.items():
                if isinstance(value, (int, float)):
                    try:
                        stat_type = CharacterStatType(stat_name)
                        stats.update_stat(
                            stat_type, int(value), "Character initialization"
                        )
                    except ValueError:
                        self.logger.warning(f"Unknown stat type: {stat_name}")

            return stats

        # Create new character stats
        stats = CharacterStats(character_id=character_id)

        # Apply initial stats from kwargs
        for stat_name, value in kwargs.items():
            if isinstance(value, (int, float)):
                try:
                    stat_type = CharacterStatType(stat_name)
                    stats.stats[stat_type] = max(1, min(10, int(value)))
                except ValueError:
                    self.logger.warning(f"Unknown stat type: {stat_name}")

        self.character_data[character_id] = stats
        return stats

    def get_character_data(self, character_id: str) -> CharacterStats | None:
        """Get character statistics."""
        return self.character_data.get(character_id)

    def update_character_stat(
        self,
        character_id: str,
        stat_type: CharacterStatType,
        new_value: int,
        reason: str,
        scene_context: str = "",
    ) -> bool:
        """Update a character statistic with progression tracking."""
        stats = self.get_character_data(character_id)
        if not stats:
            return False

        stats.update_stat(stat_type, new_value, reason, scene_context)
        return True

    def add_temporary_stat_modifier(
        self,
        character_id: str,
        stat_type: CharacterStatType,
        modifier: int,
        duration_hours: int = 24,
    ) -> bool:
        """Add temporary modifier to character stat."""
        stats = self.get_character_data(character_id)
        if not stats:
            return False

        # Calculate expiry time
        expiry = datetime.now() + timedelta(hours=duration_hours)
        stats.temporary_modifiers[stat_type] = (modifier, expiry)

        self.logger.info(
            f"Added temporary modifier {modifier} to {stat_type.value} for {character_id}"
        )
        return True

    def get_effective_stat(
        self, character_id: str, stat_type: CharacterStatType
    ) -> int | None:
        """Get effective stat value including temporary modifiers."""
        stats = self.get_character_data(character_id)
        return stats.get_effective_stat(stat_type) if stats else None

    # =============================================================================
    # Behavior Provider Interface
    # =============================================================================

    def get_behavior_context(
        self, character_id: str, situation_type: str = "general"
    ) -> dict[str, Any]:
        """Generate behavior context based on character statistics."""
        stats = self.get_character_data(character_id)
        if not stats:
            return {}

        context = {
            "stat_influences": [],
            "dominant_traits": self._get_dominant_traits(stats),
            "character_limitations": self._get_character_limitations(stats),
            "category_averages": {},
            "behavioral_tendencies": {},
        }

        # Get category averages
        for category in CharacterStatCategory:
            context["category_averages"][
                category.value
            ] = stats.get_stat_category_average(category)

        # Get stat influences for situation
        for stat_type in CharacterStatType:
            stat_value = stats.get_effective_stat(stat_type)
            influences = self._get_stat_influences(
                stat_type, stat_value, situation_type
            )
            context["stat_influences"].extend([inf.to_dict() for inf in influences])

        # Generate behavioral tendencies
        context["behavioral_tendencies"] = self._generate_behavioral_tendencies(
            stats, situation_type
        )

        return context

    def generate_response_modifiers(
        self, character_id: str, content_type: str = "dialogue"
    ) -> dict[str, Any]:
        """Generate response modifiers based on character stats."""
        stats = self.get_character_data(character_id)
        if not stats:
            return {}

        modifiers = {
            "stat_modifiers": {},
            "speech_patterns": [],
            "emotional_tendencies": [],
            "decision_making_style": "",
            "risk_tolerance": 0.5,
        }

        # Get stat-based modifiers
        for stat_type in CharacterStatType:
            value = stats.get_effective_stat(stat_type)
            modifiers["stat_modifiers"][stat_type.value] = {
                "value": value,
                "level": self._get_stat_level_description(value),
                "modifier": (value - 5) / 5.0,  # Normalized modifier
            }

        # Generate content-specific modifiers
        if content_type == "dialogue":
            modifiers.update(self._get_dialogue_modifiers(stats))
        elif content_type == "action":
            modifiers.update(self._get_action_modifiers(stats))
        elif content_type == "internal":
            modifiers.update(self._get_internal_modifiers(stats))

        return modifiers

    # =============================================================================
    # Validation Provider Interface
    # =============================================================================

    def validate_character_action(
        self, character_id: str, action: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate if action is consistent with character stats."""
        stats = self.get_character_data(character_id)
        if not stats:
            return True, None  # No stats to validate against

        action_type = action.get("type", "")

        if action_type == "stat_update":
            return self._validate_stat_update(stats, action)
        if action_type == "decision":
            return self._validate_decision(stats, action)
        if action_type == "behavior":
            return self._validate_behavior(stats, action)

        return True, None  # Unknown action types pass by default

    def get_consistency_score(self, character_id: str) -> float:
        """Get character consistency score based on stat progression."""
        stats = self.get_character_data(character_id)
        if not stats:
            return 1.0

        # Base score on progression history consistency
        if not stats.progression_history:
            return 1.0

        # Check for contradictory progressions
        consistency_score = 1.0
        recent_progressions = stats.progression_history[-10:]  # Last 10 progressions

        for progression in recent_progressions:
            # Check if progression makes sense given current stats
            stat_value = stats.get_effective_stat(progression.stat_type)
            change = progression.new_value - progression.old_value

            # Large negative changes without good reason reduce consistency
            if change < -2 and "external" not in progression.reason.lower():
                consistency_score -= 0.1

            # Extreme values without progression path reduce consistency
            if (
                stat_value >= 9
                and len(
                    [
                        p
                        for p in stats.progression_history
                        if p.stat_type == progression.stat_type
                    ]
                )
                < 3
            ):
                consistency_score -= 0.05

        return max(0.0, min(1.0, consistency_score))

    # =============================================================================
    # Data Management
    # =============================================================================

    def export_character_data(self, character_id: str) -> dict[str, Any]:
        """Export character statistics data."""
        stats = self.get_character_data(character_id)
        if not stats:
            return {}

        return {
            "character_id": character_id,
            "stats_data": stats.to_dict(),
            "component": "stats",
            "version": "1.0",
        }

    def import_character_data(self, character_data: dict[str, Any]) -> None:
        """Import character statistics data."""
        character_id = character_data.get("character_id")
        stats_data = character_data.get("stats_data")

        if character_id and stats_data:
            try:
                stats = CharacterStats.from_dict(stats_data)
                self.character_data[character_id] = stats
                self.logger.info(f"Imported stats data for character {character_id}")
            except (KeyError, AttributeError) as e:
                self.logger.exception(
                    "Character stats data structure error for"
                )
            except (ValueError, TypeError) as e:
                self.logger.exception(
                    "Character stats data validation error for"
                )
            except Exception as e:
                self.logger.exception(
                    "Failed to import stats data for"
                )

    # =============================================================================
    # Private Helper Methods
    # =============================================================================

    def _initialize_behavior_templates(self) -> dict[str, dict]:
        """Initialize behavior templates for different situations."""
        return {
            "general": {
                "high_intelligence": "Demonstrates analytical thinking and complex reasoning",
                "low_intelligence": "Prefers simple, direct approaches to problems",
                "high_charisma": "Naturally draws attention and influences others",
                "low_charisma": "Struggles with social interactions and persuasion",
            },
            "combat": {
                "high_courage": "Acts boldly in dangerous situations",
                "low_courage": "Hesitates and seeks safer alternatives",
                "high_temper": "Quick to anger and aggressive responses",
                "low_temper": "Remains calm and controlled under pressure",
            },
            "social": {
                "high_empathy": "Easily understands and relates to others' emotions",
                "low_empathy": "Focuses on logic rather than emotional considerations",
                "high_humor": "Uses wit and jokes to lighten situations",
                "low_humor": "Maintains serious demeanor in interactions",
            },
        }

    def _initialize_stat_interactions(
        self,
    ) -> dict[str, list[tuple[CharacterStatType, CharacterStatType]]]:
        """Initialize stat interaction patterns."""
        return {
            "synergistic": [
                (CharacterStatType.INTELLIGENCE, CharacterStatType.WISDOM),
                (CharacterStatType.CHARISMA, CharacterStatType.HUMOR),
                (CharacterStatType.COURAGE, CharacterStatType.WILLPOWER),
                (CharacterStatType.EMPATHY, CharacterStatType.WISDOM),
            ],
            "conflicting": [
                (CharacterStatType.TEMPER, CharacterStatType.WISDOM),
                (CharacterStatType.GREED, CharacterStatType.LOYALTY),
                (CharacterStatType.COURAGE, CharacterStatType.PERCEPTION),
            ],
        }

    def _get_stat_influences(
        self, stat_type: CharacterStatType, value: int, situation: str
    ) -> list[CharacterBehaviorInfluence]:
        """Get behavior influences for a specific stat value in given situation."""
        influences = []
        level = self._get_stat_level_description(value)

        # Map stat types to behavior types
        behavior_mapping = {
            CharacterStatType.INTELLIGENCE: CharacterBehaviorType.LEARNING_ABILITY,
            CharacterStatType.CHARISMA: CharacterBehaviorType.SOCIAL_INTERACTION,
            CharacterStatType.COURAGE: CharacterBehaviorType.RISK_TOLERANCE,
            CharacterStatType.TEMPER: CharacterBehaviorType.EMOTIONAL_RESPONSE,
            CharacterStatType.WISDOM: CharacterBehaviorType.DECISION_MAKING,
            CharacterStatType.HUMOR: CharacterBehaviorType.SPEECH_PATTERN,
        }

        behavior_type = behavior_mapping.get(
            stat_type, CharacterBehaviorType.SPEECH_PATTERN
        )

        influence = CharacterBehaviorInfluence(
            stat_type=stat_type,
            stat_value=value,
            behavior_type=behavior_type,
            influence_strength=abs(value - 5) / 5.0,  # 0.0 to 1.0
            description=f"{stat_type.value.title()} ({level}) influences {behavior_type.value}",
            examples=self._get_behavior_examples(stat_type, value, situation),
        )

        influences.append(influence)
        return influences

    def _get_behavior_examples(
        self, stat_type: CharacterStatType, value: int, situation: str
    ) -> list[str]:
        """Get behavior examples for a stat type and value."""
        examples = []
        level = self._get_stat_level_description(value)

        base_examples = {
            CharacterStatType.INTELLIGENCE: {
                "very_low": "Makes simple observations, struggles with complex ideas",
                "low": "Prefers concrete thinking, avoids abstract concepts",
                "average": "Demonstrates normal reasoning and problem-solving",
                "high": "Shows analytical thinking and strategic planning",
                "very_high": "Displays brilliant insights and complex reasoning",
            },
            CharacterStatType.CHARISMA: {
                "very_low": "Awkward in social situations, poor communication",
                "low": "Struggles to connect with others, limited persuasion",
                "average": "Normal social skills, decent communication",
                "high": "Naturally likeable, persuasive and engaging",
                "very_high": "Magnetic personality, exceptional social influence",
            },
        }

        if stat_type in base_examples and level in base_examples[stat_type]:
            examples.append(base_examples[stat_type][level])

        return examples

    def _get_stat_level_description(self, value: int) -> str:
        """Get descriptive level for stat value."""
        for level, (min_val, max_val) in self.thresholds.items():
            if min_val <= value <= max_val:
                return level
        return "average"

    def _get_dominant_traits(self, stats: CharacterStats) -> list[str]:
        """Get character's dominant personality traits."""
        traits = []

        for stat_type in CharacterStatType:
            value = stats.get_effective_stat(stat_type)
            if value >= 8:  # High values
                traits.append(f"High {stat_type.value}")
            elif value <= 2:  # Low values
                traits.append(f"Low {stat_type.value}")

        return traits

    def _get_character_limitations(self, stats: CharacterStats) -> list[str]:
        """Get character limitations based on low stats."""
        limitations = []

        for stat_type in CharacterStatType:
            value = stats.get_effective_stat(stat_type)
            if value <= 3:
                limitations.append(f"Struggles with {stat_type.value}-based activities")

        return limitations

    def _generate_behavioral_tendencies(
        self, stats: CharacterStats, situation_type: str
    ) -> dict[str, str]:
        """Generate behavioral tendencies for the character."""
        tendencies = {}

        # Decision making style
        wisdom = stats.get_effective_stat(CharacterStatType.WISDOM)
        intelligence = stats.get_effective_stat(CharacterStatType.INTELLIGENCE)

        if wisdom >= 7 and intelligence >= 7:
            tendencies["decision_making"] = "Thoughtful and analytical"
        elif wisdom >= 7:
            tendencies["decision_making"] = "Intuitive and experiential"
        elif intelligence >= 7:
            tendencies["decision_making"] = "Logical but potentially impractical"
        else:
            tendencies["decision_making"] = "Impulsive or simplistic"

        # Communication style
        charisma = stats.get_effective_stat(CharacterStatType.CHARISMA)
        humor = stats.get_effective_stat(CharacterStatType.HUMOR)

        if charisma >= 7 and humor >= 7:
            tendencies["communication"] = "Charming and entertaining"
        elif charisma >= 7:
            tendencies["communication"] = "Persuasive and engaging"
        elif humor >= 7:
            tendencies["communication"] = "Witty but potentially awkward"
        else:
            tendencies["communication"] = "Direct and unpolished"

        return tendencies

    def _get_dialogue_modifiers(self, stats: CharacterStats) -> dict[str, Any]:
        """Get dialogue-specific modifiers."""
        modifiers = {}

        charisma = stats.get_effective_stat(CharacterStatType.CHARISMA)
        humor = stats.get_effective_stat(CharacterStatType.HUMOR)
        intelligence = stats.get_effective_stat(CharacterStatType.INTELLIGENCE)

        # Speech complexity
        if intelligence >= 8:
            modifiers["vocabulary_level"] = "advanced"
        elif intelligence <= 3:
            modifiers["vocabulary_level"] = "simple"
        else:
            modifiers["vocabulary_level"] = "moderate"

        # Social ease
        modifiers["social_comfort"] = min(1.0, charisma / 10.0)
        modifiers["humor_frequency"] = min(1.0, humor / 10.0)

        return modifiers

    def _get_action_modifiers(self, stats: CharacterStats) -> dict[str, Any]:
        """Get action-specific modifiers."""
        modifiers = {}

        courage = stats.get_effective_stat(CharacterStatType.COURAGE)
        perception = stats.get_effective_stat(CharacterStatType.PERCEPTION)

        modifiers["risk_tolerance"] = min(1.0, courage / 10.0)
        modifiers["situational_awareness"] = min(1.0, perception / 10.0)

        return modifiers

    def _get_internal_modifiers(self, stats: CharacterStats) -> dict[str, Any]:
        """Get internal thought modifiers."""
        modifiers = {}

        wisdom = stats.get_effective_stat(CharacterStatType.WISDOM)
        empathy = stats.get_effective_stat(CharacterStatType.EMPATHY)

        modifiers["introspection_depth"] = min(1.0, wisdom / 10.0)
        modifiers["emotional_awareness"] = min(1.0, empathy / 10.0)

        return modifiers

    def _validate_stat_update(
        self, stats: CharacterStats, action: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate stat update action."""
        new_value = action.get("new_value", 5)
        reason = action.get("reason", "")

        # Check if value is in valid range
        if not (1 <= new_value <= 10):
            return False, f"Stat value {new_value} outside valid range (1-10)"

        # Check if large changes have good reasons
        stat_type = CharacterStatType(action.get("stat_type", "intelligence"))
        current_value = stats.get_effective_stat(stat_type)
        change = abs(new_value - current_value)

        if change > 3 and not reason:
            return False, f"Large stat change ({change}) requires justification"

        return True, None

    def _validate_decision(
        self, stats: CharacterStats, action: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate decision action against character stats."""
        decision_type = action.get("decision_type", "")
        required_stats = action.get("required_stats", {})

        for stat_name, min_value in required_stats.items():
            try:
                stat_type = CharacterStatType(stat_name)
                current_value = stats.get_effective_stat(stat_type)
                if current_value < min_value:
                    return (
                        False,
                        f"Decision requires {stat_name} >= {min_value}, character has {current_value}",
                    )
            except ValueError:
                continue

        return True, None

    def _validate_behavior(
        self, stats: CharacterStats, action: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """Validate behavior action against character stats."""
        behavior_type = action.get("behavior_type", "")

        # Check if behavior conflicts with character limitations
        limitations = self._get_character_limitations(stats)

        for limitation in limitations:
            if behavior_type in limitation:
                return (
                    False,
                    f"Behavior conflicts with character limitation: {limitation}",
                )

        return True, None
