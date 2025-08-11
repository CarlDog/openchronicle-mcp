"""
Scene Context Manager

Specialized component for managing scene-specific context and narrative flow.
Handles scene transitions, context continuity, and narrative consistency.
"""

from dataclasses import dataclass
from typing import Any

from ..shared.memory_models import MemorySnapshot
from .context_builder import ContextBuilder
from .context_builder import ContextConfiguration
from .world_state_manager import WorldStateManager


@dataclass
class SceneContext:
    """Represents context for a specific scene."""

    scene_id: str
    location: str
    time_context: str
    active_characters: list[str]
    scene_mood: str
    world_state_snapshot: dict[str, Any]
    narrative_focus: str
    context_prompt: str


@dataclass
class SceneTransition:
    """Represents a transition between scenes."""

    from_scene: str
    to_scene: str
    transition_type: (
        str  # "immediate", "time_jump", "location_change", "perspective_shift"
    )
    time_elapsed: str | None = None
    continuity_notes: list[str] = None


@dataclass
class ContextContinuity:
    """Analysis of context continuity between scenes."""

    character_consistency: float  # 0.0 to 1.0
    world_state_consistency: float
    narrative_flow_score: float
    potential_issues: list[str]
    recommendations: list[str]


class SceneContextManager:
    """Advanced scene context and narrative continuity management."""

    def __init__(self):
        """Initialize scene context manager."""
        self.context_builder = ContextBuilder()
        self.world_manager = WorldStateManager()

        self.scene_types = {
            "dialogue": "Character interaction and conversation",
            "action": "Physical action and conflict",
            "exposition": "Information delivery and world-building",
            "reflection": "Character introspection and development",
            "transition": "Movement between locations or time periods",
        }

        self.narrative_focuses = [
            "character_development",
            "plot_advancement",
            "world_building",
            "conflict_resolution",
            "relationship_dynamics",
            "mystery_revelation",
        ]

    def create_scene_context(
        self,
        memory: MemorySnapshot,
        scene_id: str,
        location: str,
        active_characters: list[str],
        scene_type: str = "dialogue",
        narrative_focus: str = "character_development",
    ) -> SceneContext:
        """
        Create comprehensive context for a specific scene.

        Args:
            memory: Current memory snapshot
            scene_id: Unique identifier for the scene
            location: Scene location
            active_characters: Characters present in the scene
            scene_type: Type of scene being created
            narrative_focus: Primary narrative focus

        Returns:
            SceneContext with all relevant information
        """
        try:
            # Generate time context
            time_context = self._generate_time_context(memory)

            # Determine scene mood
            scene_mood = self._determine_scene_mood(memory, active_characters)

            # Create world state snapshot
            world_snapshot = dict(memory.world_state)

            # Generate context prompt
            context_config = self._create_scene_context_config(
                scene_type, active_characters
            )
            context_prompt = self.context_builder.build_memory_context(
                memory, active_characters, context_config
            )

            return SceneContext(
                scene_id=scene_id,
                location=location,
                time_context=time_context,
                active_characters=active_characters,
                scene_mood=scene_mood,
                world_state_snapshot=world_snapshot,
                narrative_focus=narrative_focus,
                context_prompt=context_prompt,
            )

        except Exception:
            # Return minimal scene context on error
            return SceneContext(
                scene_id=scene_id,
                location=location or "Unknown",
                time_context="Present",
                active_characters=active_characters or [],
                scene_mood="neutral",
                world_state_snapshot={},
                narrative_focus=narrative_focus,
                context_prompt="[Error generating context]",
            )

    def analyze_scene_transition(
        self, from_context: SceneContext, to_context: SceneContext
    ) -> SceneTransition:
        """Analyze the transition between two scenes."""
        try:
            # Determine transition type
            transition_type = self._determine_transition_type(from_context, to_context)

            # Calculate time elapsed
            time_elapsed = self._calculate_time_elapsed(from_context, to_context)

            # Generate continuity notes
            continuity_notes = self._generate_continuity_notes(from_context, to_context)

            return SceneTransition(
                from_scene=from_context.scene_id,
                to_scene=to_context.scene_id,
                transition_type=transition_type,
                time_elapsed=time_elapsed,
                continuity_notes=continuity_notes,
            )

        except Exception:
            return SceneTransition(
                from_scene=from_context.scene_id,
                to_scene=to_context.scene_id,
                transition_type="immediate",
            )

    def check_context_continuity(
        self,
        previous_context: SceneContext,
        current_context: SceneContext,
        memory: MemorySnapshot,
    ) -> ContextContinuity:
        """Check continuity between scene contexts."""
        try:
            # Character consistency
            char_consistency = self._check_character_consistency(
                previous_context, current_context, memory
            )

            # World state consistency
            world_consistency = self._check_world_state_consistency(
                previous_context, current_context
            )

            # Narrative flow
            narrative_flow = self._check_narrative_flow(
                previous_context, current_context
            )

            # Identify issues and recommendations
            issues, recommendations = self._analyze_continuity_issues(
                char_consistency,
                world_consistency,
                narrative_flow,
                previous_context,
                current_context,
            )

            return ContextContinuity(
                character_consistency=char_consistency,
                world_state_consistency=world_consistency,
                narrative_flow_score=narrative_flow,
                potential_issues=issues,
                recommendations=recommendations,
            )

        except Exception:
            return ContextContinuity(
                character_consistency=0.5,
                world_state_consistency=0.5,
                narrative_flow_score=0.5,
                potential_issues=["Error analyzing continuity"],
                recommendations=["Manual review recommended"],
            )

    def generate_scene_prompt(
        self,
        scene_context: SceneContext,
        memory: MemorySnapshot,
        additional_instructions: str = "",
    ) -> str:
        """Generate a comprehensive scene prompt for AI generation."""
        try:
            prompt_parts = []

            # Scene setup
            prompt_parts.append("=== SCENE SETUP ===")
            prompt_parts.append(f"Scene ID: {scene_context.scene_id}")
            prompt_parts.append(f"Location: {scene_context.location}")
            prompt_parts.append(f"Time Context: {scene_context.time_context}")
            prompt_parts.append(f"Scene Mood: {scene_context.scene_mood}")
            prompt_parts.append(f"Narrative Focus: {scene_context.narrative_focus}")

            # Active characters
            if scene_context.active_characters:
                prompt_parts.append("\n=== ACTIVE CHARACTERS ===")
                for char_name in scene_context.active_characters:
                    if char_name in memory.characters:
                        char_data = memory.characters[char_name]
                        mood = char_data.current_mood or "neutral"
                        prompt_parts.append(f"- {char_name}: {mood} mood")

            # World context
            if scene_context.world_state_snapshot:
                prompt_parts.append("\n=== CURRENT WORLD STATE ===")
                for key, value in scene_context.world_state_snapshot.items():
                    prompt_parts.append(f"- {key}: {value}")

            # Memory context
            prompt_parts.append(f"\n{scene_context.context_prompt}")

            # Additional instructions
            if additional_instructions:
                prompt_parts.append("\n=== ADDITIONAL INSTRUCTIONS ===")
                prompt_parts.append(additional_instructions)

            return "\n".join(prompt_parts)

        except Exception:
            return f"Scene: {scene_context.scene_id} at {scene_context.location}\n[Error generating scene prompt]"

    def update_scene_with_outcomes(
        self,
        scene_context: SceneContext,
        memory: MemorySnapshot,
        scene_outcomes: dict[str, Any],
    ) -> dict[str, Any]:
        """Update memory based on scene outcomes."""
        try:
            updates = {}

            # Character mood changes
            if "character_moods" in scene_outcomes:
                for char_name, new_mood in scene_outcomes["character_moods"].items():
                    if char_name in memory.characters:
                        memory.characters[char_name].current_mood = new_mood
                        updates[f"character_{char_name}_mood"] = new_mood

            # World state changes
            if "world_state_changes" in scene_outcomes:
                world_changes = scene_outcomes["world_state_changes"]
                self.world_manager.update_world_state(
                    memory,
                    world_changes,
                    source="scene",
                    description=f"Changes from scene {scene_context.scene_id}",
                )
                updates["world_state"] = world_changes

            # New events
            if "events" in scene_outcomes:
                for event in scene_outcomes["events"]:
                    self.world_manager.add_world_event(
                        memory,
                        event.get("description", "Scene event"),
                        event_type=event.get("type", "scene"),
                        characters_involved=scene_context.active_characters,
                        location=scene_context.location,
                    )
                updates["events_added"] = len(scene_outcomes["events"])

            # New flags
            if "flags" in scene_outcomes:
                for flag in scene_outcomes["flags"]:
                    self.world_manager.add_memory_flag(
                        memory,
                        flag.get("name", "Scene flag"),
                        flag_data=flag.get("data", {}),
                        flag_type=flag.get("type", "scene"),
                    )
                updates["flags_added"] = len(scene_outcomes["flags"])

            return updates

        except Exception:
            return {}

    def _generate_time_context(self, memory: MemorySnapshot) -> str:
        """Generate time context description."""
        world_state = memory.world_state

        time_parts = []

        # Time of day
        if "time_of_day" in world_state:
            time_parts.append(world_state["time_of_day"])

        # Season
        if "season" in world_state:
            time_parts.append(f"({world_state['season']})")

        # Weather
        if "weather" in world_state:
            time_parts.append(f"Weather: {world_state['weather']}")

        return " ".join(time_parts) if time_parts else "Present"

    def _determine_scene_mood(
        self, memory: MemorySnapshot, active_characters: list[str]
    ) -> str:
        """Determine overall mood for the scene."""
        try:
            character_moods = []

            for char_name in active_characters:
                if char_name in memory.characters:
                    char_mood = memory.characters[char_name].current_mood
                    if char_mood:
                        character_moods.append(char_mood)

            if not character_moods:
                return "neutral"

            # Simple mood aggregation (could be more sophisticated)
            if any(
                mood in ["angry", "hostile", "frustrated"] for mood in character_moods
            ):
                return "tense"
            if any(
                mood in ["happy", "excited", "cheerful"] for mood in character_moods
            ):
                return "upbeat"
            if any(
                mood in ["sad", "melancholy", "depressed"] for mood in character_moods
            ):
                return "somber"
            return "neutral"

        except Exception:
            return "neutral"

    def _create_scene_context_config(
        self, scene_type: str, active_characters: list[str]
    ) -> ContextConfiguration:
        """Create context configuration optimized for scene type."""
        if scene_type == "dialogue":
            return ContextConfiguration(
                include_character_details=True,
                include_world_state=False,
                include_recent_events=True,
                include_active_flags=True,
                max_recent_events=3,
                character_detail_level="full",
                prioritize_primary_characters=True,
            )
        if scene_type == "action":
            return ContextConfiguration(
                include_character_details=True,
                include_world_state=True,
                include_recent_events=True,
                include_active_flags=True,
                max_recent_events=5,
                character_detail_level="summary",
                prioritize_primary_characters=True,
            )
        # exposition, reflection, transition
        return ContextConfiguration(
            include_character_details=True,
            include_world_state=True,
            include_recent_events=True,
            include_active_flags=True,
            max_recent_events=7,
            character_detail_level="full",
            prioritize_primary_characters=False,
        )

    def _determine_transition_type(
        self, from_context: SceneContext, to_context: SceneContext
    ) -> str:
        """Determine the type of transition between scenes."""
        # Location change
        if from_context.location != to_context.location:
            return "location_change"

        # Character change
        from_chars = set(from_context.active_characters)
        to_chars = set(to_context.active_characters)
        if from_chars != to_chars:
            return "perspective_shift"

        # Time context change
        if from_context.time_context != to_context.time_context:
            return "time_jump"

        return "immediate"

    def _calculate_time_elapsed(
        self, from_context: SceneContext, to_context: SceneContext
    ) -> str | None:
        """Calculate time elapsed between scenes."""
        # Simple time detection (could be enhanced)
        from_time = from_context.time_context.lower()
        to_time = to_context.time_context.lower()

        if from_time != to_time:
            return "Time has passed"

        return None

    def _generate_continuity_notes(
        self, from_context: SceneContext, to_context: SceneContext
    ) -> list[str]:
        """Generate continuity notes for the transition."""
        notes = []

        # Location change note
        if from_context.location != to_context.location:
            notes.append(
                f"Location changed from {from_context.location} to {to_context.location}"
            )

        # Character changes
        from_chars = set(from_context.active_characters)
        to_chars = set(to_context.active_characters)

        new_chars = to_chars - from_chars
        departed_chars = from_chars - to_chars

        if new_chars:
            notes.append(f"New characters: {', '.join(new_chars)}")
        if departed_chars:
            notes.append(f"Characters departed: {', '.join(departed_chars)}")

        # Mood change
        if from_context.scene_mood != to_context.scene_mood:
            notes.append(
                f"Mood shifted from {from_context.scene_mood} to {to_context.scene_mood}"
            )

        return notes

    def _check_character_consistency(
        self,
        prev_context: SceneContext,
        curr_context: SceneContext,
        memory: MemorySnapshot,
    ) -> float:
        """Check character consistency between scenes."""
        try:
            # Characters that appear in both scenes
            common_chars = set(prev_context.active_characters) & set(
                curr_context.active_characters
            )

            if not common_chars:
                return 1.0  # No overlap, no inconsistency

            consistency_score = 1.0

            # Check mood consistency (gradual changes are expected)
            for char_name in common_chars:
                if char_name in memory.characters:
                    # In a full implementation, would compare previous vs current character state
                    # For now, assume consistency
                    pass

            return consistency_score

        except Exception:
            return 0.5

    def _check_world_state_consistency(
        self, prev_context: SceneContext, curr_context: SceneContext
    ) -> float:
        """Check world state consistency between scenes."""
        try:
            prev_state = prev_context.world_state_snapshot
            curr_state = curr_context.world_state_snapshot

            if not prev_state or not curr_state:
                return 1.0

            # Check for inconsistent changes
            inconsistencies = 0
            total_checks = 0

            for key in prev_state:
                if key in curr_state:
                    total_checks += 1
                    # Some changes are expected, but dramatic inconsistencies are problematic
                    # This is a simplified check
                    if prev_state[key] != curr_state[key]:
                        # Check if change makes sense (simplified)
                        if not self._is_reasonable_state_change(
                            key, prev_state[key], curr_state[key]
                        ):
                            inconsistencies += 1

            if total_checks == 0:
                return 1.0

            return max(0.0, 1.0 - (inconsistencies / total_checks))

        except Exception:
            return 0.5

    def _check_narrative_flow(
        self, prev_context: SceneContext, curr_context: SceneContext
    ) -> float:
        """Check narrative flow between scenes."""
        try:
            # Simple flow checking (could be enhanced with NLP)
            flow_score = 1.0

            # Narrative focus changes
            if prev_context.narrative_focus != curr_context.narrative_focus:
                flow_score -= 0.1  # Small penalty for focus changes

            # Mood consistency
            if prev_context.scene_mood != curr_context.scene_mood:
                flow_score -= 0.1  # Small penalty for mood changes

            return max(0.0, flow_score)

        except Exception:
            return 0.5

    def _analyze_continuity_issues(
        self,
        char_consistency: float,
        world_consistency: float,
        narrative_flow: float,
        prev_context: SceneContext,
        curr_context: SceneContext,
    ) -> tuple[list[str], list[str]]:
        """Analyze continuity issues and generate recommendations."""
        issues = []
        recommendations = []

        # Character consistency issues
        if char_consistency < 0.7:
            issues.append("Character behavior may be inconsistent")
            recommendations.append("Review character motivations and mood progression")

        # World state consistency issues
        if world_consistency < 0.7:
            issues.append("World state changes may be inconsistent")
            recommendations.append("Verify world state transitions make logical sense")

        # Narrative flow issues
        if narrative_flow < 0.7:
            issues.append("Narrative flow may be disrupted")
            recommendations.append("Consider adding transition elements or context")

        # Location changes without context
        if prev_context.location != curr_context.location:
            if not any(
                "location" in note.lower() for note in []
            ):  # Would check transition notes
                recommendations.append("Consider explaining the location change")

        return issues, recommendations

    def _is_reasonable_state_change(
        self, key: str, old_value: Any, new_value: Any
    ) -> bool:
        """Check if a world state change is reasonable."""
        # Simple reasonableness checks (could be expanded)
        try:
            old_str = str(old_value).lower()
            new_str = str(new_value).lower()

            # Time progression
            if key == "time_of_day":
                reasonable_progressions = [
                    ("morning", "afternoon"),
                    ("afternoon", "evening"),
                    ("evening", "night"),
                    ("night", "morning"),
                ]
                return (old_str, new_str) in reasonable_progressions

            # Weather changes
            if key == "weather":
                # Most weather changes are reasonable
                return True

            # Threat level changes
            if key == "threat_level":
                # Threat can escalate or de-escalate
                return True

            # Default: assume reasonable
            return True

        except Exception:
            return True  # Assume reasonable if we can't determine
