"""
OpenChronicle Core - Narrative Mechanics Data Models

Data classes and enums for the narrative mechanics system.
Extracted from NarrativeDiceEngine for modular architecture.

Author: OpenChronicle Development Team
"""

from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Any


class DiceType(Enum):
    """Types of dice used in narrative resolution."""

    D4 = "d4"  # 4-sided die
    D6 = "d6"  # 6-sided die
    D8 = "d8"  # 8-sided die
    D10 = "d10"  # 10-sided die
    D12 = "d12"  # 12-sided die
    D20 = "d20"  # 20-sided die
    D100 = "d100"  # 100-sided die (percentile)
    FUDGE = "fudge"  # Fudge dice (-1, 0, +1)
    COIN = "coin"  # Simple coin flip


class ResolutionType(Enum):
    """Types of narrative resolution."""

    SKILL_CHECK = "skill_check"  # Basic skill or ability check
    COMBAT_ACTION = "combat_action"  # Combat-related actions
    SOCIAL_INTERACTION = "social_interaction"  # Social and dialogue actions
    EXPLORATION = "exploration"  # Discovery and investigation
    CREATIVE_ACTION = "creative_action"  # Artistic or creative endeavors
    MENTAL_CHALLENGE = "mental_challenge"  # Puzzles and mental tasks
    PHYSICAL_CHALLENGE = "physical_challenge"  # Athletic and physical tasks
    MAGICAL_ACTION = "magical_action"  # Magic and supernatural actions
    STEALTH_ACTION = "stealth_action"  # Stealth and infiltration
    SURVIVAL_ACTION = "survival_action"  # Survival and endurance
    LUCK_CHECK = "luck_check"  # Pure chance events
    NARRATIVE_CHOICE = "narrative_choice"  # Story direction choices
    CHARACTER_DEVELOPMENT = "character_development"  # Character growth moments
    RELATIONSHIP_TEST = "relationship_test"  # Relationship dynamics
    WORLD_EVENT = "world_event"  # Major world-affecting events


class DifficultyLevel(Enum):
    """Difficulty levels for narrative challenges."""

    TRIVIAL = "trivial"  # DC 5 - Almost impossible to fail
    EASY = "easy"  # DC 10 - Simple tasks
    MODERATE = "moderate"  # DC 15 - Standard difficulty
    HARD = "hard"  # DC 20 - Challenging tasks
    VERY_HARD = "very_hard"  # DC 25 - Expert-level tasks
    LEGENDARY = "legendary"  # DC 30 - Near-impossible tasks


class OutcomeType(Enum):
    """Types of resolution outcomes."""

    CRITICAL_SUCCESS = "critical_success"  # Exceptional positive result
    SUCCESS = "success"  # Positive result
    PARTIAL_SUCCESS = "partial_success"  # Mixed result
    FAILURE = "failure"  # Negative result
    CRITICAL_FAILURE = "critical_failure"  # Catastrophic result


@dataclass
class DiceRoll:
    """Individual dice roll data."""

    dice_type: DiceType
    rolls: list[int] = field(default_factory=list)
    modifier: int = 0
    advantage: bool = False
    disadvantage: bool = False
    total: int = 0

    def __post_init__(self):
        if not self.total and self.rolls:
            self.total = sum(self.rolls) + self.modifier


@dataclass
class ResolutionResult:
    """Result of a narrative resolution."""

    resolution_type: ResolutionType
    outcome: OutcomeType
    dice_roll: DiceRoll
    difficulty_check: int
    success_margin: int  # How much over/under the target

    # Character and context
    character_id: str = ""
    character_skill: int = 0
    situation_modifiers: dict[str, int] = field(default_factory=dict)

    # Narrative impact
    narrative_impact: str = ""
    consequences: list[str] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)

    # Metadata
    timestamp: str = ""
    scene_context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "resolution_type": self.resolution_type.value,
            "outcome": self.outcome.value,
            "dice_roll": {
                "dice_type": self.dice_roll.dice_type.value,
                "rolls": self.dice_roll.rolls,
                "modifier": self.dice_roll.modifier,
                "advantage": self.dice_roll.advantage,
                "disadvantage": self.dice_roll.disadvantage,
                "total": self.dice_roll.total,
            },
            "difficulty_check": self.difficulty_check,
            "success_margin": self.success_margin,
            "character_id": self.character_id,
            "character_skill": self.character_skill,
            "situation_modifiers": self.situation_modifiers,
            "narrative_impact": self.narrative_impact,
            "consequences": self.consequences,
            "benefits": self.benefits,
            "timestamp": self.timestamp,
            "scene_context": self.scene_context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResolutionResult":
        """Create from dictionary."""
        dice_data = data.get("dice_roll", {})
        dice_roll = DiceRoll(
            dice_type=DiceType(dice_data.get("dice_type", "d20")),
            rolls=dice_data.get("rolls", []),
            modifier=dice_data.get("modifier", 0),
            advantage=dice_data.get("advantage", False),
            disadvantage=dice_data.get("disadvantage", False),
            total=dice_data.get("total", 0),
        )

        return cls(
            resolution_type=ResolutionType(data.get("resolution_type", "skill_check")),
            outcome=OutcomeType(data.get("outcome", "success")),
            dice_roll=dice_roll,
            difficulty_check=data.get("difficulty_check", 15),
            success_margin=data.get("success_margin", 0),
            character_id=data.get("character_id", ""),
            character_skill=data.get("character_skill", 0),
            situation_modifiers=data.get("situation_modifiers", {}),
            narrative_impact=data.get("narrative_impact", ""),
            consequences=data.get("consequences", []),
            benefits=data.get("benefits", []),
            timestamp=data.get("timestamp", ""),
            scene_context=data.get("scene_context", {}),
        )


@dataclass
class ResolutionConfig:
    """Configuration for resolution mechanics."""

    base_difficulty: int = 15
    dice_type: DiceType = DiceType.D20
    allow_advantage: bool = True
    allow_disadvantage: bool = True
    critical_success_threshold: int = 20
    critical_failure_threshold: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "base_difficulty": self.base_difficulty,
            "dice_type": self.dice_type.value,
            "allow_advantage": self.allow_advantage,
            "allow_disadvantage": self.allow_disadvantage,
            "critical_success_threshold": self.critical_success_threshold,
            "critical_failure_threshold": self.critical_failure_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ResolutionConfig":
        """Create from dictionary."""
        return cls(
            base_difficulty=data.get("base_difficulty", 15),
            dice_type=DiceType(data.get("dice_type", "d20")),
            allow_advantage=data.get("allow_advantage", True),
            allow_disadvantage=data.get("allow_disadvantage", True),
            critical_success_threshold=data.get("critical_success_threshold", 20),
            critical_failure_threshold=data.get("critical_failure_threshold", 1),
        )


@dataclass
class NarrativeBranch:
    """Represents a narrative branching path."""

    branch_id: str
    description: str
    probability: float = 1.0  # Likelihood of this branch occurring

    # Branch effects
    stat_changes: dict[str, int] = field(default_factory=dict)
    scene_transitions: list[str] = field(default_factory=list)
    character_consequences: list[str] = field(default_factory=list)
    world_state_changes: dict[str, Any] = field(default_factory=dict)

    # Branch conditions
    required_outcome: OutcomeType | None = None
    required_skills: dict[str, int] = field(default_factory=dict)
    required_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "branch_id": self.branch_id,
            "description": self.description,
            "probability": self.probability,
            "stat_changes": self.stat_changes,
            "scene_transitions": self.scene_transitions,
            "character_consequences": self.character_consequences,
            "world_state_changes": self.world_state_changes,
            "required_outcome": (
                self.required_outcome.value if self.required_outcome else None
            ),
            "required_skills": self.required_skills,
            "required_items": self.required_items,
        }


@dataclass
class MechanicsRequest:
    """Request for narrative mechanics operation."""

    operation_type: str  # "resolve_action", "create_branches", "simulate", etc.
    resolution_type: ResolutionType
    character_id: str = ""
    difficulty: DifficultyLevel | None = None
    modifiers: dict[str, int] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)

    # Optional parameters
    advantage: bool = False
    disadvantage: bool = False
    custom_config: ResolutionConfig | None = None


@dataclass
class MechanicsResult:
    """Result of mechanics operation."""

    request: MechanicsRequest
    resolution_result: ResolutionResult | None = None
    narrative_branches: list[NarrativeBranch] = field(default_factory=list)
    success: bool = True
    error_message: str = ""

    # Additional results
    performance_data: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    narrative_prompt: str = ""


@dataclass
class CharacterPerformance:
    """Character performance tracking."""

    character_id: str
    total_actions: int = 0
    successes: int = 0
    failures: int = 0
    critical_successes: int = 0
    critical_failures: int = 0

    # Skill tracking
    skill_usage: dict[str, int] = field(default_factory=dict)
    skill_successes: dict[str, int] = field(default_factory=dict)

    # Recent performance
    recent_rolls: list[ResolutionResult] = field(default_factory=list)
    average_roll: float = 0.0

    def calculate_success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_actions == 0:
            return 0.0
        return self.successes / self.total_actions

    def calculate_skill_success_rate(self, skill: str) -> float:
        """Calculate success rate for specific skill."""
        usage = self.skill_usage.get(skill, 0)
        if usage == 0:
            return 0.0
        successes = self.skill_successes.get(skill, 0)
        return successes / usage
