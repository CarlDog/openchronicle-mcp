"""
Character Data Classes

Unified dataclasses and enums for the character management system.
Consolidates data structures from the previous separate character engines.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Any

from .character_base import CharacterDataMixin


# =============================================================================
# Unified Character Enums (consolidated from all engines)
# =============================================================================


class CharacterStatType(Enum):
    """Unified character statistics/traits."""

    # Mental traits
    INTELLIGENCE = "intelligence"
    WISDOM = "wisdom"
    CREATIVITY = "creativity"
    PERCEPTION = "perception"

    # Social traits
    CHARISMA = "charisma"
    HUMOR = "humor"
    EMPATHY = "empathy"

    # Emotional traits
    WILLPOWER = "willpower"
    COURAGE = "courage"
    TEMPER = "temper"

    # Moral traits
    LOYALTY = "loyalty"
    GREED = "greed"


class CharacterStatCategory(Enum):
    """Categories of character traits."""

    MENTAL = "mental"
    SOCIAL = "social"
    EMOTIONAL = "emotional"
    MORAL = "moral"


class CharacterBehaviorType(Enum):
    """Types of behavior modifications based on character traits."""

    SPEECH_PATTERN = "speech_pattern"
    DECISION_MAKING = "decision_making"
    RISK_TOLERANCE = "risk_tolerance"
    SOCIAL_INTERACTION = "social_interaction"
    EMOTIONAL_RESPONSE = "emotional_response"
    LEARNING_ABILITY = "learning_ability"


class CharacterRelationType(Enum):
    """Types of relationships between characters."""

    ROMANTIC = "romantic"
    FRIENDSHIP = "friendship"
    FAMILY = "family"
    PROFESSIONAL = "professional"
    RIVALRY = "rivalry"
    MENTORSHIP = "mentorship"
    ALLIANCE = "alliance"
    ENMITY = "enmity"
    NEUTRAL = "neutral"


class CharacterInteractionType(Enum):
    """Types of character interactions."""

    DIALOGUE = "dialogue"
    CONFLICT = "conflict"
    COOPERATION = "cooperation"
    EMOTIONAL_EXCHANGE = "emotional_exchange"
    PHYSICAL_INTERACTION = "physical_interaction"
    STRATEGIC_DISCUSSION = "strategic_discussion"


class CharacterConsistencyLevel(Enum):
    """Levels of character consistency enforcement."""

    STRICT = "strict"  # No deviations allowed
    MODERATE = "moderate"  # Minor deviations allowed
    FLEXIBLE = "flexible"  # Major deviations allowed with justification
    ADAPTIVE = "adaptive"  # Character can evolve significantly


class CharacterViolationType(Enum):
    """Types of character consistency violations."""

    TRAIT_CONTRADICTION = "trait_contradiction"
    MOTIVATION_CONFLICT = "motivation_conflict"
    BEHAVIOR_INCONSISTENCY = "behavior_inconsistency"
    EMOTIONAL_DISCONNECT = "emotional_disconnect"
    RELATIONSHIP_VIOLATION = "relationship_violation"


# =============================================================================
# Character Statistics Data Structures
# =============================================================================


@dataclass
class CharacterStatProgression(CharacterDataMixin):
    """Tracks progression/changes in a character's stats over time."""

    stat_type: CharacterStatType
    old_value: int
    new_value: int
    reason: str
    timestamp: datetime
    scene_context: str = ""
    permanent: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CharacterStatProgression":
        """Create from dictionary."""
        return cls(
            stat_type=CharacterStatType(data["stat_type"]),
            old_value=data["old_value"],
            new_value=data["new_value"],
            reason=data["reason"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            scene_context=data.get("scene_context", ""),
            permanent=data.get("permanent", True),
        )


@dataclass
class CharacterBehaviorInfluence(CharacterDataMixin):
    """Represents how a stat influences character behavior."""

    stat_type: CharacterStatType
    stat_value: int
    behavior_type: CharacterBehaviorType
    influence_strength: float  # 0.0 to 1.0
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass
class CharacterStats(CharacterDataMixin):
    """Complete character statistics profile."""

    character_id: str
    stats: dict[CharacterStatType, int] = field(default_factory=dict)
    progression_history: list[CharacterStatProgression] = field(default_factory=list)
    temporary_modifiers: dict[CharacterStatType, tuple[int, datetime]] = field(
        default_factory=dict
    )
    last_updated: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize with default stats if not provided."""
        if not self.stats:
            self.stats = self._get_default_stats()

    def _get_default_stats(self) -> dict[CharacterStatType, int]:
        """Get default stat values (5 = average)."""
        return dict.fromkeys(CharacterStatType, 5)

    def get_effective_stat(self, stat_type: CharacterStatType) -> int:
        """Get stat value including temporary modifiers."""
        base_value = self.stats.get(stat_type, 5)

        # Apply temporary modifier if exists and not expired
        if stat_type in self.temporary_modifiers:
            modifier, expiry = self.temporary_modifiers[stat_type]
            if datetime.now() < expiry:
                return max(1, min(10, base_value + modifier))
            # Remove expired modifier
            del self.temporary_modifiers[stat_type]

        return base_value

    def update_stat(
        self,
        stat_type: CharacterStatType,
        new_value: int,
        reason: str,
        scene_context: str = "",
        permanent: bool = True,
    ) -> None:
        """Update a character stat with progression tracking."""
        old_value = self.stats.get(stat_type, 5)
        new_value = max(1, min(10, new_value))  # Clamp to valid range

        # Record progression
        progression = CharacterStatProgression(
            stat_type=stat_type,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            timestamp=datetime.now(),
            scene_context=scene_context,
            permanent=permanent,
        )

        self.progression_history.append(progression)
        self.stats[stat_type] = new_value
        self.last_updated = datetime.now()


# =============================================================================
# Character Interaction Data Structures
# =============================================================================


@dataclass
class CharacterRelationship(CharacterDataMixin):
    """Represents a relationship between two characters."""

    character_a: str
    character_b: str
    relationship_type: CharacterRelationType
    strength: float  # -1.0 (hostile) to 1.0 (devoted)
    history: list[dict[str, Any]] = field(default_factory=list)
    last_interaction: datetime | None = None
    trust_level: float = 0.0  # 0.0 to 1.0
    emotional_bond: float = 0.0  # 0.0 to 1.0

    def get_relationship_key(self) -> str:
        """Get standardized relationship key."""
        chars = sorted([self.character_a, self.character_b])
        return f"{chars[0]}:{chars[1]}"


@dataclass
class CharacterInteraction(CharacterDataMixin):
    """Represents a single interaction between characters."""

    interaction_id: str
    participants: list[str]
    interaction_type: CharacterInteractionType
    content: str
    timestamp: datetime
    scene_context: str = ""
    emotional_impact: dict[str, float] = field(
        default_factory=dict
    )  # character_id -> impact
    relationship_changes: dict[str, float] = field(
        default_factory=dict
    )  # relationship_key -> change


@dataclass
class CharacterState(CharacterDataMixin):
    """Character state within a scene or interaction."""

    character_id: str
    current_emotion: str = "neutral"
    emotional_intensity: float = 0.5  # 0.0 to 1.0
    motivation: str = ""
    scene_position: str = ""
    active_relationships: set[str] = field(default_factory=set)
    temporary_traits: dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneState(CharacterDataMixin):
    """State of a multi-character scene."""

    scene_id: str
    active_characters: list[str]
    character_states: dict[str, CharacterState] = field(default_factory=dict)
    turn_order: list[str] = field(default_factory=list)
    current_speaker: str | None = None
    scene_tension: float = 0.0  # 0.0 to 1.0
    scene_focus: str = ""
    environment_context: str = ""
    interaction_history: list[CharacterInteraction] = field(default_factory=list)


# =============================================================================
# Character Consistency Data Structures
# =============================================================================


@dataclass
class CharacterMotivationAnchor(CharacterDataMixin):
    """Represents a core motivation that anchors character behavior."""

    anchor_id: str
    character_id: str
    motivation_type: str  # e.g., "survival", "love", "power", "knowledge"
    description: str
    strength: float  # 0.0 to 1.0 - how strongly this drives behavior
    locked: bool = False  # Whether this can change
    created_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CharacterConsistencyViolation(CharacterDataMixin):
    """Represents a violation of character consistency."""

    violation_id: str
    character_id: str
    violation_type: CharacterViolationType
    description: str
    severity: float  # 0.0 to 1.0
    scene_context: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False


@dataclass
class CharacterConsistencyProfile(CharacterDataMixin):
    """Complete character consistency profile."""

    character_id: str
    motivation_anchors: list[CharacterMotivationAnchor] = field(default_factory=list)
    locked_traits: set[str] = field(default_factory=set)
    violation_history: list[CharacterConsistencyViolation] = field(default_factory=list)
    consistency_level: CharacterConsistencyLevel = CharacterConsistencyLevel.MODERATE
    consistency_score: float = 1.0  # Current consistency rating
    behavioral_patterns: list[dict[str, Any]] = field(default_factory=list)


# =============================================================================
# Character Presentation Data Structures
# =============================================================================


@dataclass
class CharacterStyleProfile(CharacterDataMixin):
    """Character presentation and style information."""

    character_id: str
    preferred_models: dict[str, str] = field(
        default_factory=dict
    )  # content_type -> model_name
    speech_patterns: dict[str, Any] = field(default_factory=dict)
    personality_traits: dict[str, Any] = field(default_factory=dict)
    emotional_range: dict[str, float] = field(default_factory=dict)
    consistency_score: float = 1.0
    model_performance: dict[str, dict[str, float]] = field(
        default_factory=dict
    )  # model -> metrics


# =============================================================================
# Unified Character Data Container
# =============================================================================


@dataclass
class CharacterData(CharacterDataMixin):
    """
    Unified character data container that holds all character information
    across all management components.
    """

    character_id: str

    # Core character information
    name: str = ""
    description: str = ""

    # Component data
    stats: CharacterStats | None = None
    relationships: dict[str, CharacterRelationship] = field(default_factory=dict)
    consistency_profile: CharacterConsistencyProfile | None = None
    style_profile: CharacterStyleProfile | None = None

    # State information
    current_state: CharacterState | None = None
    scene_states: dict[str, CharacterState] = field(
        default_factory=dict
    )  # scene_id -> state

    # Metadata
    created_timestamp: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    version: str = "1.0"

    def __post_init__(self):
        """Initialize with default component data if not provided."""
        if self.stats is None:
            self.stats = CharacterStats(character_id=self.character_id)
        if self.consistency_profile is None:
            self.consistency_profile = CharacterConsistencyProfile(
                character_id=self.character_id
            )
        if self.style_profile is None:
            self.style_profile = CharacterStyleProfile(character_id=self.character_id)

    def update_timestamp(self) -> None:
        """Update the last_updated timestamp."""
        self.last_updated = datetime.now()

    def get_component_data(self, component_name: str) -> Any | None:
        """Get data for a specific component."""
        component_map = {
            "stats": self.stats,
            "interactions": {"relationships": self.relationships},
            "consistency": self.consistency_profile,
            "style": self.style_profile,
            "presentation": self.style_profile,  # Alias for style
            "current_state": self.current_state,
        }
        return component_map.get(component_name)

    def set_component_data(self, component_name: str, data: Any) -> None:
        """Set data for a specific component."""
        if component_name == "stats":
            self.stats = data
        elif component_name == "interactions":
            # Handle interactions data which may contain relationships
            if isinstance(data, dict) and "relationships" in data:
                self.relationships = data["relationships"]
            else:
                self.relationships = data
        elif component_name == "consistency":
            self.consistency_profile = data
        elif component_name in ["style", "presentation"]:
            self.style_profile = data
        elif component_name == "current_state":
            self.current_state = data

        self.update_timestamp()
