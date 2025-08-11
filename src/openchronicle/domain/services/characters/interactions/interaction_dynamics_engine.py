"""
Character Interactions Component

Specialized component for managing character relationships, multi-character scenes,
and interaction dynamics. Extracted from character_interaction_engine.py.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any

from ..character_base import CharacterEngineBase, CharacterStateProvider
from ..character_data import (
    CharacterData,
    CharacterRelationship,
    CharacterInteraction,
    CharacterState,
    SceneState,
    CharacterRelationType,
    CharacterInteractionType,
)

logger = logging.getLogger(__name__)


class InteractionDynamicsEngine(CharacterEngineBase, CharacterStateProvider):
    """
    Manages character interactions, relationships, and multi-character scenes.

    Tracks relationship dynamics, orchestrates character conversations,
    and maintains individual character states within complex multi-character scenes.
    """

    def __init__(self, config: Optional[Dict] = None):
        """Initialize the interaction dynamics engine."""
        super().__init__(config)

        # Configuration parameters
        self.max_scene_history = self.config.get("max_scene_history", 100)
        self.relationship_decay_rate = self.config.get("relationship_decay_rate", 0.01)
        self.interaction_window_hours = self.config.get("interaction_window_hours", 24)
        self.auto_turn_management = self.config.get("auto_turn_management", True)
        self.emotional_contagion_enabled = self.config.get(
            "emotional_contagion_enabled", True
        )

        # Data storage
        self.relationships: Dict[str, CharacterRelationship] = (
            {}
        )  # Key: "char_a:char_b"
        self.interaction_history: List[CharacterInteraction] = []
        self.scene_states: Dict[str, SceneState] = {}
        self.character_contexts: Dict[str, Dict[str, Any]] = {}

        # Turn management patterns
        self.speaking_patterns = {
            "balanced": [1, 1, 1],  # Everyone speaks equally
            "leader_focused": [3, 1, 1],  # One character dominates
            "dialogue_heavy": [2, 2, 1],  # Two characters focus
            "round_robin": [1, 1, 1],  # Strict rotation
        }

        self.logger.info("Interaction dynamics engine initialized")

    def initialize_character(self, character_id: str, **kwargs) -> CharacterState:
        """Initialize character interaction state."""
        if character_id in self.character_data:
            return self.character_data[character_id]

        # Create new character state
        character_state = CharacterState(
            character_id=character_id,
            current_emotion="neutral",
            emotional_intensity=0.5,
            motivation="participate in scene",
        )

        self.character_data[character_id] = character_state
        self.character_contexts[character_id] = {}

        return character_state

    def get_character_data(self, character_id: str) -> Optional[CharacterState]:
        """Get character interaction state."""
        return self.character_data.get(character_id)

    # =============================================================================
    # Relationship Management
    # =============================================================================

    def create_relationship(
        self,
        character_a: str,
        character_b: str,
        relationship_type: CharacterRelationType,
        initial_strength: float = 0.0,
    ) -> CharacterRelationship:
        """Create or update relationship between two characters."""
        relationship_key = self._get_relationship_key(character_a, character_b)

        if relationship_key in self.relationships:
            # Update existing relationship
            relationship = self.relationships[relationship_key]
            relationship.relationship_type = relationship_type
            relationship.strength = initial_strength
        else:
            # Create new relationship
            relationship = CharacterRelationship(
                character_a=character_a,
                character_b=character_b,
                relationship_type=relationship_type,
                strength=initial_strength,
                last_interaction=datetime.now(),
            )
            self.relationships[relationship_key] = relationship

        self.logger.info(
            f"Created/updated relationship: {character_a} - {character_b} ({relationship_type.value})"
        )
        return relationship

    def get_relationship(
        self, character_a: str, character_b: str
    ) -> Optional[CharacterRelationship]:
        """Get relationship between two characters."""
        relationship_key = self._get_relationship_key(character_a, character_b)
        return self.relationships.get(relationship_key)

    def update_relationship_strength(
        self,
        character_a: str,
        character_b: str,
        strength_change: float,
        reason: str = "",
    ) -> bool:
        """Update relationship strength between characters."""
        relationship = self.get_relationship(character_a, character_b)
        if not relationship:
            # Create neutral relationship if none exists
            relationship = self.create_relationship(
                character_a, character_b, CharacterRelationType.NEUTRAL
            )

        # Update strength (clamped to -1.0 to 1.0)
        relationship.strength = max(
            -1.0, min(1.0, relationship.strength + strength_change)
        )
        relationship.last_interaction = datetime.now()

        # Add to history
        relationship.history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "change": strength_change,
                "new_strength": relationship.strength,
                "reason": reason,
            }
        )

        return True

    def get_character_relationships(
        self, character_id: str
    ) -> List[CharacterRelationship]:
        """Get all relationships for a character."""
        relationships = []

        for relationship in self.relationships.values():
            if (
                relationship.character_a == character_id
                or relationship.character_b == character_id
            ):
                relationships.append(relationship)

        return relationships

    # =============================================================================
    # Scene Management
    # =============================================================================

    def create_scene(
        self,
        scene_id: str,
        characters: List[str],
        scene_focus: str,
        environment_context: str = "",
    ) -> SceneState:
        """Create a new multi-character scene."""
        character_states = {}

        for char_id in characters:
            # Get or create character state
            char_state = self.get_character_data(char_id)
            if not char_state:
                char_state = self.initialize_character(char_id)

            # Create scene-specific state
            scene_char_state = CharacterState(
                character_id=char_id,
                current_emotion=char_state.current_emotion,
                emotional_intensity=char_state.emotional_intensity,
                motivation=char_state.motivation,
                scene_position=environment_context,
            )
            character_states[char_id] = scene_char_state

        scene_state = SceneState(
            scene_id=scene_id,
            active_characters=characters,
            character_states=character_states,
            turn_order=characters.copy(),
            current_speaker=characters[0] if characters else None,
            scene_tension=0.3,
            scene_focus=scene_focus,
            environment_context=environment_context,
        )

        self.scene_states[scene_id] = scene_state

        self.logger.info(
            f"Created scene '{scene_id}' with {len(characters)} characters"
        )
        return scene_state

    def get_scene(self, scene_id: str) -> Optional[SceneState]:
        """Get scene state."""
        return self.scene_states.get(scene_id)

    def add_character_to_scene(self, scene_id: str, character_id: str) -> bool:
        """Add character to existing scene."""
        scene = self.get_scene(scene_id)
        if not scene or character_id in scene.active_characters:
            return False

        # Get or create character state
        char_state = self.get_character_data(character_id)
        if not char_state:
            char_state = self.initialize_character(character_id)

        # Add to scene
        scene.active_characters.append(character_id)
        scene.character_states[character_id] = CharacterState(
            character_id=character_id,
            current_emotion=char_state.current_emotion,
            emotional_intensity=char_state.emotional_intensity,
            motivation=char_state.motivation,
            scene_position=scene.environment_context,
        )

        # Update turn order
        scene.turn_order.append(character_id)

        return True

    def remove_character_from_scene(self, scene_id: str, character_id: str) -> bool:
        """Remove character from scene."""
        scene = self.get_scene(scene_id)
        if not scene or character_id not in scene.active_characters:
            return False

        scene.active_characters.remove(character_id)
        if character_id in scene.character_states:
            del scene.character_states[character_id]

        # Update turn order
        if character_id in scene.turn_order:
            scene.turn_order.remove(character_id)

        # Update current speaker if needed
        if scene.current_speaker == character_id:
            scene.current_speaker = scene.turn_order[0] if scene.turn_order else None

        return True

    # =============================================================================
    # Interaction Processing
    # =============================================================================

    def process_interaction(
        self,
        scene_id: str,
        speaker_id: str,
        content: str,
        interaction_type: CharacterInteractionType = CharacterInteractionType.DIALOGUE,
    ) -> CharacterInteraction:
        """Process character interaction within a scene."""
        scene = self.get_scene(scene_id)
        if not scene or speaker_id not in scene.active_characters:
            raise ValueError(f"Invalid scene or character for interaction")

        # Create interaction record
        interaction = CharacterInteraction(
            interaction_id=str(uuid.uuid4()),
            participants=[speaker_id],
            interaction_type=interaction_type,
            content=content,
            timestamp=datetime.now(),
            scene_context=scene.scene_focus,
        )

        # Process interaction effects
        self._process_interaction_effects(scene, interaction)

        # Add to histories
        self.interaction_history.append(interaction)
        scene.interaction_history.append(interaction)

        # Limit scene history
        if len(scene.interaction_history) > self.max_scene_history:
            scene.interaction_history = scene.interaction_history[
                -self.max_scene_history :
            ]

        # Update turn order if auto-management enabled
        if self.auto_turn_management:
            self._advance_turn_order(scene)

        self.logger.debug(f"Processed interaction in scene {scene_id}: {speaker_id}")
        return interaction

    def get_scene_interactions(
        self, scene_id: str, limit: int = 50
    ) -> List[CharacterInteraction]:
        """Get recent interactions from a scene."""
        scene = self.get_scene(scene_id)
        if not scene:
            return []

        return scene.interaction_history[-limit:]

    def get_character_interaction_history(
        self, character_id: str, hours_back: int = 24
    ) -> List[CharacterInteraction]:
        """Get character's recent interaction history."""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        return [
            interaction
            for interaction in self.interaction_history
            if character_id in interaction.participants
            and interaction.timestamp > cutoff_time
        ]

    # =============================================================================
    # State Provider Interface
    # =============================================================================

    def get_character_state(self, character_id: str) -> Dict[str, Any]:
        """Get comprehensive character interaction state."""
        character_state = self.get_character_data(character_id)
        relationships = self.get_character_relationships(character_id)

        state = {
            "character_id": character_id,
            "current_emotion": (
                character_state.current_emotion if character_state else "neutral"
            ),
            "emotional_intensity": (
                character_state.emotional_intensity if character_state else 0.5
            ),
            "motivation": character_state.motivation if character_state else "",
            "active_relationships": len(relationships),
            "relationship_summary": self._summarize_relationships(relationships),
            "recent_interactions": len(
                self.get_character_interaction_history(character_id, 24)
            ),
        }

        return state

    def update_character_state(
        self, character_id: str, state_updates: Dict[str, Any]
    ) -> bool:
        """Update character interaction state."""
        character_state = self.get_character_data(character_id)
        if not character_state:
            character_state = self.initialize_character(character_id)

        # Update state fields
        if "current_emotion" in state_updates:
            character_state.current_emotion = state_updates["current_emotion"]
        if "emotional_intensity" in state_updates:
            character_state.emotional_intensity = state_updates["emotional_intensity"]
        if "motivation" in state_updates:
            character_state.motivation = state_updates["motivation"]
        if "scene_position" in state_updates:
            character_state.scene_position = state_updates["scene_position"]

        return True

    # =============================================================================
    # Data Management
    # =============================================================================

    def export_character_data(self, character_id: str) -> Dict[str, Any]:
        """Export character interaction data."""
        character_state = self.get_character_data(character_id)
        relationships = self.get_character_relationships(character_id)
        interactions = self.get_character_interaction_history(
            character_id, 24 * 7
        )  # Week of history

        return {
            "character_id": character_id,
            "character_state": character_state.to_dict() if character_state else None,
            "relationships": [rel.to_dict() for rel in relationships],
            "recent_interactions": [int.to_dict() for int in interactions],
            "component": "interactions",
            "version": "1.0",
        }

    def import_character_data(self, character_data: Dict[str, Any]) -> None:
        """Import character interaction data."""
        character_id = character_data.get("character_id")
        if not character_id:
            return

        try:
            # Import character state
            if character_data.get("character_state"):
                state_data = character_data["character_state"]
                character_state = CharacterState.from_dict(state_data)
                self.character_data[character_id] = character_state

            # Import relationships
            for rel_data in character_data.get("relationships", []):
                relationship = CharacterRelationship.from_dict(rel_data)
                relationship_key = relationship.get_relationship_key()
                self.relationships[relationship_key] = relationship

            # Import interactions
            for int_data in character_data.get("recent_interactions", []):
                interaction = CharacterInteraction.from_dict(int_data)
                self.interaction_history.append(interaction)

            self.logger.info(f"Imported interaction data for character {character_id}")

        except Exception as e:
            self.logger.error(
                f"Failed to import interaction data for {character_id}: {e}"
            )

    # =============================================================================
    # Private Helper Methods
    # =============================================================================

    def _get_relationship_key(self, character_a: str, character_b: str) -> str:
        """Get standardized relationship key."""
        chars = sorted([character_a, character_b])
        return f"{chars[0]}:{chars[1]}"

    def _process_interaction_effects(
        self, scene: SceneState, interaction: CharacterInteraction
    ) -> None:
        """Process effects of interaction on relationships and emotions."""
        speaker_id = interaction.participants[0]

        # Update emotional contagion if enabled
        if self.emotional_contagion_enabled:
            self._apply_emotional_contagion(scene, speaker_id, interaction)

        # Update relationship strengths based on interaction
        for other_character in scene.active_characters:
            if other_character != speaker_id:
                self._update_relationship_from_interaction(
                    speaker_id, other_character, interaction
                )

    def _apply_emotional_contagion(
        self, scene: SceneState, speaker_id: str, interaction: CharacterInteraction
    ) -> None:
        """Apply emotional contagion effects to other characters."""
        speaker_state = scene.character_states.get(speaker_id)
        if not speaker_state:
            return

        speaker_intensity = speaker_state.emotional_intensity

        # Apply mild contagion to other characters
        for char_id, char_state in scene.character_states.items():
            if char_id != speaker_id:
                # Slightly adjust emotional intensity based on speaker
                contagion_effect = (
                    speaker_intensity - char_state.emotional_intensity
                ) * 0.1
                char_state.emotional_intensity = max(
                    0.0, min(1.0, char_state.emotional_intensity + contagion_effect)
                )

    def _update_relationship_from_interaction(
        self, speaker_id: str, listener_id: str, interaction: CharacterInteraction
    ) -> None:
        """Update relationship based on interaction content."""
        # Simple heuristic - positive words increase relationship, negative decrease
        content_lower = interaction.content.lower()

        positive_words = ["thank", "please", "help", "love", "appreciate", "respect"]
        negative_words = ["hate", "angry", "stupid", "betray", "lie", "fool"]

        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)

        if positive_count > negative_count:
            self.update_relationship_strength(
                speaker_id, listener_id, 0.05, "Positive interaction"
            )
        elif negative_count > positive_count:
            self.update_relationship_strength(
                speaker_id, listener_id, -0.05, "Negative interaction"
            )

    def _advance_turn_order(self, scene: SceneState) -> None:
        """Advance turn order to next speaker."""
        if not scene.turn_order or not scene.current_speaker:
            return

        current_index = scene.turn_order.index(scene.current_speaker)
        next_index = (current_index + 1) % len(scene.turn_order)
        scene.current_speaker = scene.turn_order[next_index]

    def _summarize_relationships(
        self, relationships: List[CharacterRelationship]
    ) -> Dict[str, int]:
        """Summarize relationship types for a character."""
        summary = {}

        for relationship in relationships:
            rel_type = relationship.relationship_type.value
            summary[rel_type] = summary.get(rel_type, 0) + 1

        return summary
