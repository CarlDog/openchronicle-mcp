"""
Domain services for OpenChronicle.

Domain services contain business logic that doesn't naturally fit into entities
or value objects. They coordinate between entities and implement complex
business rules.
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Any

from ..entities import Character
from ..entities import Scene
from ..entities import Story
from ..entities import StoryStatus
from ..value_objects import NarrativeContext


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str] | None = None
    suggestions: list[str] | None = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.suggestions is None:
            self.suggestions = []


class StoryGenerator:
    """
    Domain service for story generation and narrative flow.

    This service contains the core business logic for generating coherent
    narratives while maintaining character consistency and story flow.
    """

    def __init__(self):
        self.min_scene_length = 50  # minimum words per scene
        self.max_context_age = timedelta(hours=24)  # context relevance window

    def validate_story_state(self, story: Story) -> list[str]:
        """Validate story state and return list of issues."""
        issues = []

        if not story.title.strip():
            issues.append("Story must have a title")

        if story.status == StoryStatus.ACTIVE and not story.world_state:
            issues.append("Active stories should have world state initialized")

        return issues

    def calculate_narrative_coherence(self, scenes: list[Scene]) -> float:
        """Calculate coherence score for a sequence of scenes."""
        if not scenes:
            return 1.0

        # Sort scenes by sequence number
        sorted_scenes = sorted(scenes, key=lambda s: s.sequence_number)

        coherence_factors = []

        # Check for consistent participants
        all_participants = set()
        for scene in sorted_scenes:
            all_participants.update(scene.participants)

        # Calculate participant consistency
        if all_participants:
            participant_appearances = dict.fromkeys(all_participants, 0)
            for scene in sorted_scenes:
                for participant in scene.participants:
                    participant_appearances[participant] += 1

            # Penalize characters that appear very rarely
            min_appearances = len(sorted_scenes) * 0.1  # Should appear in at least 10% of scenes
            consistency_score = sum(
                1.0 if count >= min_appearances else count / min_appearances
                for count in participant_appearances.values()
            ) / len(all_participants)
            coherence_factors.append(consistency_score)

        # Check temporal consistency
        time_gaps = []
        for i in range(1, len(sorted_scenes)):
            gap = sorted_scenes[i].timestamp - sorted_scenes[i - 1].timestamp
            time_gaps.append(gap.total_seconds())

        if time_gaps:
            avg_gap = sum(time_gaps) / len(time_gaps)
            # Penalize very long gaps between scenes
            max_reasonable_gap = 3600  # 1 hour
            time_consistency = min(1.0, max_reasonable_gap / max(avg_gap, 1))
            coherence_factors.append(time_consistency)

        # Return average of all coherence factors
        return sum(coherence_factors) / len(coherence_factors) if coherence_factors else 1.0

    def suggest_next_scene_type(self, recent_scenes: list[Scene]) -> str:
        """Suggest the type of scene that should come next."""
        if not recent_scenes:
            return "narrative"

        # Count recent scene types
        recent_types = [scene.scene_type for scene in recent_scenes[-5:]]
        type_counts = {}
        for scene_type in recent_types:
            type_counts[scene_type] = type_counts.get(scene_type, 0) + 1

        # Suggest variety
        if type_counts.get("dialogue", 0) >= 3:
            return "action"
        if type_counts.get("action", 0) >= 2:
            return "description"
        if type_counts.get("description", 0) >= 2:
            return "dialogue"
        return "narrative"

    def detect_story_pacing_issues(self, scenes: list[Scene]) -> list[str]:
        """Detect potential pacing issues in the story."""
        issues = []

        if not scenes:
            return issues

        # Check for very short or very long scenes
        word_counts = [scene.get_word_count() for scene in scenes]
        avg_length = sum(word_counts) / len(word_counts)

        very_short = [i for i, count in enumerate(word_counts) if count < avg_length * 0.3]
        very_long = [i for i, count in enumerate(word_counts) if count > avg_length * 3]

        if very_short:
            issues.append(f"Scenes {very_short} are unusually short")
        if very_long:
            issues.append(f"Scenes {very_long} are unusually long")

        # Check for repetitive scene types
        recent_types = [scene.scene_type for scene in scenes[-10:]]
        if len(set(recent_types)) == 1 and len(recent_types) > 3:
            issues.append(f"Too many consecutive {recent_types[0]} scenes")

        return issues

    def validate_story_concept(self, title: str, description: str, world_state: dict[str, Any]) -> "ValidationResult":
        """Validate a story concept for coherence and completeness."""
        errors = []
        warnings = []

        # Basic validation
        if not title or len(title.strip()) < 3:
            errors.append("Story title must be at least 3 characters long")

        if len(title) > 200:
            warnings.append("Very long titles may be hard to remember")

        if description and len(description) > 2000:
            warnings.append("Very long descriptions may be overwhelming")

        # World state validation
        if world_state:
            if "setting" not in world_state and "location" not in world_state:
                warnings.append("Consider adding setting or location information")

            # Check for common conflicts
            tech_level = world_state.get("tech_level", "").lower()
            magic_level = world_state.get("magic_level", "").lower()

            if tech_level == "futuristic" and magic_level == "high":
                warnings.append("Futuristic + high magic settings may need careful balance")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=self._generate_story_suggestions(title, description, world_state),
        )

    def _generate_story_suggestions(self, title: str, description: str, world_state: dict[str, Any]) -> list[str]:
        """Generate helpful suggestions for story development."""
        suggestions = []

        if not description:
            suggestions.append("Add a compelling description to set the tone")

        if not world_state or len(world_state) < 3:
            suggestions.append("Consider adding more world-building details")

        # Genre-specific suggestions based on title keywords
        title_lower = title.lower()
        if any(word in title_lower for word in ["space", "star", "galaxy", "future"]):
            suggestions.append("For sci-fi stories, consider defining technology levels")
        elif any(word in title_lower for word in ["magic", "wizard", "dragon", "fantasy"]):
            suggestions.append("For fantasy stories, consider establishing magic system rules")
        elif any(word in title_lower for word in ["mystery", "detective", "crime"]):
            suggestions.append("For mysteries, plan key clues and red herrings")

        return suggestions

    def generate_coherent_narrative(
        self, context: NarrativeContext, participant_characters: list["Character"]
    ) -> ValidationResult:
        """Generate a coherent narrative based on context and characters."""
        errors = []
        warnings = []

        # Validate context completeness
        if not context.user_input.strip():
            errors.append("User input is required for narrative generation")

        if not participant_characters:
            warnings.append("No characters participating in this scene")

        # Check character consistency for participants
        for character in participant_characters:
            if not character.personality_traits:
                warnings.append(f"Character {character.name} lacks defined personality traits")

            if not character.emotional_state:
                warnings.append(f"Character {character.name} has no defined emotional state")

        # Validate scene type compatibility
        if context.scene_type == "dialogue" and len(participant_characters) < 2:
            warnings.append("Dialogue scenes work best with multiple characters")

        # Check for narrative coherence
        if context.memory_state and context.memory_state.recent_events:
            recent_event_count = len(context.memory_state.recent_events)
            if recent_event_count > 20:
                warnings.append("Many recent events may make context too complex")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=self._generate_narrative_suggestions(context, participant_characters),
        )

    def _generate_narrative_suggestions(
        self, context: NarrativeContext, participant_characters: list["Character"]
    ) -> list[str]:
        """Generate suggestions for improving the narrative."""
        suggestions = []

        if context.scene_type == "narrative":
            suggestions.append("Consider adding sensory details to enhance immersion")

        if len(participant_characters) > 3:
            suggestions.append("With many characters, focus on 1-2 primary speakers")

        if context.location:
            suggestions.append("Use the location to influence character actions and mood")

        return suggestions


class CharacterAnalyzer:
    """
    Domain service for character analysis and consistency.

    This service ensures character behavior remains consistent and tracks
    character development throughout the narrative.
    """

    def __init__(self):
        self.consistency_threshold = 0.7  # minimum consistency score
        self.development_weight = 0.3  # how much development affects consistency

    def validate_character_concept(
        self,
        name: str,
        personality_traits: dict[str, Any],
        background: str,
        story_context: dict[str, Any],
    ) -> ValidationResult:
        """Validate a character concept for coherence and story fit."""
        errors = []
        warnings = []

        # Basic validation
        if not name or len(name.strip()) < 2:
            errors.append("Character name must be at least 2 characters long")

        if len(name) > 100:
            warnings.append("Very long character names may be hard to remember")

        # Personality validation
        if not personality_traits:
            warnings.append("Consider adding personality traits for richer characterization")
        else:
            # Check for conflicting traits
            trait_conflicts = [
                ("introverted", "extroverted"),
                ("aggressive", "peaceful"),
                ("logical", "emotional"),
            ]

            for trait1, trait2 in trait_conflicts:
                if (
                    trait1 in personality_traits
                    and trait2 in personality_traits
                    and personality_traits[trait1] > 7
                    and personality_traits[trait2] > 7
                ):
                    warnings.append(f"High {trait1} and {trait2} traits may create internal conflict")

        # Background validation
        if not background:
            warnings.append("Adding character background helps with consistency")
        elif len(background) > 1000:
            warnings.append("Very long backgrounds may be hard to track during gameplay")

        # Story context fit
        if story_context:
            setting = story_context.get("setting", "").lower()
            tech_level = story_context.get("tech_level", "").lower()

            # Check for anachronisms
            if "medieval" in setting and any(
                word in background.lower() for word in ["computer", "internet", "smartphone"]
            ):
                errors.append("Character background contains elements inconsistent with medieval setting")

            if tech_level == "stone age" and any(word in background.lower() for word in ["sword", "metal", "writing"]):
                warnings.append("Character background may be too advanced for stone age setting")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=self._generate_character_suggestions(name, personality_traits, background),
        )

    def _generate_character_suggestions(
        self, name: str, personality_traits: dict[str, Any], background: str
    ) -> list[str]:
        """Generate suggestions for character development."""
        suggestions = []

        if not personality_traits:
            suggestions.append("Add 3-5 key personality traits (e.g., courage: 8, wisdom: 6)")
        elif len(personality_traits) < 3:
            suggestions.append("Consider adding more personality traits for depth")

        if not background:
            suggestions.append("Add background to explain character motivation and history")

        # Trait-specific suggestions
        if personality_traits:
            high_traits = [
                trait for trait, value in personality_traits.items() if isinstance(value, (int, float)) and value > 8
            ]
            if high_traits:
                suggestions.append(f"Consider how extreme {', '.join(high_traits)} traits affect relationships")

        return suggestions

    def calculate_consistency_score(self, character: Character, recent_scenes: list[Scene]) -> float:
        """Calculate how consistent a character's behavior has been."""
        if not recent_scenes:
            return 1.0

        # Find scenes where this character participated
        character_scenes = [scene for scene in recent_scenes if character.id in scene.participants]

        if not character_scenes:
            return 1.0

        consistency_factors = []

        # Check emotional consistency
        if character.emotional_state:
            base_emotions = set(character.emotional_state.keys())
            scene_emotions = []

            for scene in character_scenes:
                scene_updates = scene.character_updates.get(character.id, {})
                if "emotional_state" in scene_updates:
                    scene_emotions.extend(scene_updates["emotional_state"].keys())

            if scene_emotions:
                emotion_consistency = len(base_emotions.intersection(scene_emotions)) / len(base_emotions)
                consistency_factors.append(emotion_consistency)

        # Check personality trait consistency
        if character.personality_traits:
            trait_mentions = 0
            total_opportunities = len(character_scenes)

            for scene in character_scenes:
                # This is a simplified check - in reality, we'd use NLP to detect trait expressions
                scene_text = scene.ai_response.lower()
                for trait in character.personality_traits.keys():
                    if trait.lower() in scene_text:
                        trait_mentions += 1
                        break

            trait_consistency = trait_mentions / max(total_opportunities, 1)
            consistency_factors.append(trait_consistency)

        # Account for character development (some inconsistency is expected growth)
        development_factor = len(character.character_arc) * self.development_weight
        development_bonus = min(0.2, development_factor)  # up to 20% bonus for development

        base_consistency = sum(consistency_factors) / len(consistency_factors) if consistency_factors else 1.0
        return min(1.0, base_consistency + development_bonus)

    def detect_character_conflicts(self, characters: list[Character]) -> list[str]:
        """Detect potential conflicts between character definitions."""
        conflicts = []

        # Check for duplicate names
        names = [char.name.lower() for char in characters]
        duplicates = set([name for name in names if names.count(name) > 1])
        if duplicates:
            conflicts.append(f"Duplicate character names: {duplicates}")

        # Check for conflicting relationships
        for char in characters:
            for other_id, relationship in char.relationships.items():
                # Find the other character
                other_char = next((c for c in characters if c.id == other_id), None)
                if other_char and char.id in other_char.relationships:
                    other_rel = other_char.relationships[char.id]

                    # Check if relationship types are compatible
                    if relationship["type"] == "enemy" and other_rel["type"] == "friend":
                        conflicts.append(f"Conflicting relationship between {char.name} and {other_char.name}")

        return conflicts

    def suggest_character_development(self, character: Character, story_context: NarrativeContext) -> list[str]:
        """Suggest potential character development opportunities."""
        suggestions = []

        # Check if character has been static for too long
        recent_development = [
            event for event in character.character_arc if (datetime.now() - event["timestamp"]).days < 7
        ]

        if not recent_development:
            suggestions.append("Consider adding character development or growth")

        # Check for unresolved goals
        if character.goals:
            suggestions.append("Explore progress toward character goals")

        # Check for underdeveloped relationships
        if len(character.relationships) < len(story_context.get_primary_characters()) - 1:
            suggestions.append("Develop relationships with other characters")

        # Check emotional range
        if len(character.emotional_state) < 3:
            suggestions.append("Explore broader emotional range for character")

        return suggestions

    def validate_character_update(
        self, character: Character, proposed_updates: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Validate proposed character updates for consistency."""
        issues = []

        # Check emotional state bounds
        if "emotional_state" in proposed_updates:
            for emotion, intensity in proposed_updates["emotional_state"].items():
                if not isinstance(intensity, (int, float)) or intensity < 0 or intensity > 1:
                    issues.append(f"Invalid emotional intensity for {emotion}: {intensity}")

        # Check relationship updates
        if "relationships" in proposed_updates:
            for _other_id, rel_data in proposed_updates["relationships"].items():
                if "strength" in rel_data:
                    strength = rel_data["strength"]
                    if not isinstance(strength, (int, float)) or strength < 0 or strength > 1:
                        issues.append(f"Invalid relationship strength: {strength}")

        # Check for personality conflicts
        if "personality_traits" in proposed_updates:
            existing_traits = set(character.personality_traits.keys())
            new_traits = set(proposed_updates["personality_traits"].keys())

            # Define conflicting trait pairs
            conflicts = {
                ("brave", "cowardly"),
                ("kind", "cruel"),
                ("honest", "deceptive"),
                ("calm", "aggressive"),
            }

            all_traits = existing_traits.union(new_traits)
            for trait1, trait2 in conflicts:
                if trait1 in all_traits and trait2 in all_traits:
                    issues.append(f"Conflicting personality traits: {trait1} and {trait2}")

        return len(issues) == 0, issues

    def analyze_consistency(
        self, character: Character, scene_content: str, previous_scenes: list[Scene]
    ) -> "ConsistencyAnalysisResult":
        """Analyze character consistency in a scene and suggest updates."""
        from dataclasses import dataclass

        @dataclass
        class ConsistencyAnalysisResult:
            consistency_score: float
            has_updates: bool
            suggested_updates: dict[str, Any]
            warnings: list[str]

        # Calculate consistency score
        consistency_score = self.calculate_consistency_score(character, previous_scenes)

        # Check for character mentions in scene content
        warnings = []
        suggested_updates = {}
        has_updates = False

        # Simple analysis of character behavior in scene
        scene_lower = scene_content.lower()
        char_name_lower = character.name.lower()

        # Check if character is mentioned but behavior seems inconsistent
        if char_name_lower in scene_lower:
            # Look for emotional cues
            emotional_words = {
                "angry": 0.8,
                "furious": 0.9,
                "calm": 0.2,
                "peaceful": 0.1,
                "sad": 0.7,
                "happy": 0.3,
                "excited": 0.8,
                "worried": 0.6,
            }

            detected_emotions = {}
            for emotion, intensity in emotional_words.items():
                if emotion in scene_lower:
                    detected_emotions[emotion] = intensity

            if detected_emotions:
                # Suggest emotional state update
                suggested_updates["emotional_state"] = detected_emotions
                has_updates = True

                # Check for major emotional shifts
                current_emotions = character.emotional_state or {}
                for emotion, intensity in detected_emotions.items():
                    if emotion in current_emotions:
                        current_intensity = current_emotions[emotion]
                        if abs(intensity - current_intensity) > 0.5:
                            warnings.append(f"Major emotional shift detected for {character.name}: {emotion}")

        return ConsistencyAnalysisResult(
            consistency_score=consistency_score,
            has_updates=has_updates,
            suggested_updates=suggested_updates,
            warnings=warnings,
        )


# Base service interfaces for dependency injection


class StoryService(ABC):
    """Abstract base class for story service."""

    @abstractmethod
    async def get_story(self, story_id: str) -> Story | None:
        """Get story by ID."""

    @abstractmethod
    async def save_story(self, story: Story) -> bool:
        """Save story."""


class CharacterService(ABC):
    """Abstract base class for character service."""

    @abstractmethod
    async def get_character(self, story_id: str, character_id: str) -> Character | None:
        """Get character by ID."""

    @abstractmethod
    async def save_character(self, story_id: str, character: Character) -> bool:
        """Save character."""


class SceneService(ABC):
    """Abstract base class for scene service."""

    @abstractmethod
    async def get_scene(self, story_id: str, scene_id: str) -> Scene | None:
        """Get scene by ID."""

    @abstractmethod
    async def save_scene(self, story_id: str, scene: Scene) -> bool:
        """Save scene."""


class MemoryService(ABC):
    """Abstract base class for memory service."""

    @abstractmethod
    async def get_memory_summary(self, story_id: str) -> dict[str, Any]:
        """Get memory summary."""

    @abstractmethod
    async def add_recent_event(self, story_id: str, description: str, importance: float = 1.0):
        """Add recent event."""

    @abstractmethod
    async def add_memory_flag(
        self,
        story_id: str,
        flag_name: str,
        description: str,
        flag_type: str = "general",
    ):
        """Add memory flag."""


# Export all domain services
__all__ = [
    "CharacterAnalyzer",
    "CharacterService",
    "MemoryService",
    "SceneService",
    "StoryGenerator",
    "StoryService",
]
