"""
OpenChronicle Core - Character Behavior Engine

Handles character behavior, response generation, and contextual adaptations.
Extracted from character_orchestrator.py for better separation of concerns.

Author: OpenChronicle Development Team
"""

import logging
from datetime import datetime
from typing import Any

from ..core.character_base import CharacterBehaviorProvider


logger = logging.getLogger(__name__)


class CharacterBehaviorEngine:
    """Handles character behavior generation and contextual responses."""

    def __init__(self, config: dict | None = None):
        """Initialize character behavior engine."""
        self.config = config or {}
        self.behavior_providers: list[CharacterBehaviorProvider] = []

        # Configuration
        self.adaptive_behavior = self.config.get("adaptive_behavior", True)
        self.context_memory_size = self.config.get("context_memory_size", 10)

        logger.info("Character behavior engine initialized")

    def register_behavior_provider(self, provider: CharacterBehaviorProvider) -> None:
        """Register a behavior provider."""
        if provider not in self.behavior_providers:
            self.behavior_providers.append(provider)
            logger.info(f"Registered behavior provider: {provider.__class__.__name__}")

    def unregister_behavior_provider(self, provider: CharacterBehaviorProvider) -> None:
        """Unregister a behavior provider."""
        if provider in self.behavior_providers:
            self.behavior_providers.remove(provider)
            logger.info(f"Unregistered behavior provider: {provider.__class__.__name__}")

    def generate_behavior_context(
        self, character_id: str, situation_type: str = "general"
    ) -> dict[str, Any]:
        """Generate comprehensive behavior context for character."""
        context = {
            "character_id": character_id,
            "situation_type": situation_type,
            "timestamp": datetime.now().isoformat(),
            "adaptive_behavior_enabled": self.adaptive_behavior,
        }

        # Gather context from all behavior providers
        for provider in self.behavior_providers:
            try:
                provider_context = provider.get_behavior_context(
                    character_id, situation_type
                )
                context.update(provider_context)
                logger.debug(f"Added context from {provider.__class__.__name__}")
            except (AttributeError, KeyError) as e:
                logger.exception(
                    f"Provider data structure error in {provider.__class__.__name__}"
                )
            except (ValueError, TypeError) as e:
                logger.exception(
                    f"Provider parameter error in {provider.__class__.__name__}"
                )
            except Exception as e:
                logger.exception(
                    f"Error getting behavior context from {provider.__class__.__name__}"
                )

        return context

    def generate_response_modifiers(
        self, character_id: str, content_type: str = "dialogue"
    ) -> dict[str, Any]:
        """Generate response modifiers for character content generation."""
        modifiers = {
            "character_id": character_id,
            "content_type": content_type,
            "timestamp": datetime.now().isoformat(),
        }

        # Gather modifiers from all behavior providers
        for provider in self.behavior_providers:
            try:
                provider_modifiers = provider.generate_response_modifiers(
                    character_id, content_type
                )
                modifiers.update(provider_modifiers)
                logger.debug(f"Added modifiers from {provider.__class__.__name__}")
            except (AttributeError, KeyError) as e:
                logger.exception(
                    f"Provider data structure error in {provider.__class__.__name__}"
                )
            except (ValueError, TypeError) as e:
                logger.exception(
                    f"Provider parameter error in {provider.__class__.__name__}"
                )
            except Exception as e:
                logger.exception(
                    f"Error getting response modifiers from {provider.__class__.__name__}"
                )

        return modifiers

    def adapt_character_style(
        self, character_id: str, adaptation_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Adapt character style based on story context and interactions.

        Args:
            character_id: Unique character identifier
            adaptation_data: Data for style adaptation

        Returns:
            Dictionary containing adaptation results
        """
        try:
            adaptation_type = adaptation_data.get("type", "general")
            context = adaptation_data.get("context", {})
            scene_data = adaptation_data.get("scene_data", {})

            result = {
                "character_id": character_id,
                "adaptation_type": adaptation_type,
                "success": True,
                "adaptations": [],
                "timestamp": datetime.now().isoformat(),
            }

            # Apply basic style adaptations based on context
            if adaptation_type == "dialogue_style":
                result["adaptations"].extend(self._adapt_dialogue_style(character_id, context))
            elif adaptation_type == "emotional_tone":
                result["adaptations"].extend(self._adapt_emotional_tone(character_id, context))
            elif adaptation_type == "interaction_style":
                result["adaptations"].extend(self._adapt_interaction_style(character_id, context))
            else:
                result["adaptations"].append("General style adaptation applied")

            # Apply scene-specific adaptations
            if scene_data:
                scene_adaptations = self._adapt_to_scene(character_id, scene_data)
                result["adaptations"].extend(scene_adaptations)

            logger.info(f"Adapted character {character_id} style: {adaptation_type}")
        except Exception as e:
            logger.exception(f"Error adapting character {character_id} style")
            return {
                "character_id": character_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return result

    def _adapt_dialogue_style(self, character_id: str, context: dict[str, Any]) -> list[str]:
        """Adapt dialogue style based on context."""
        adaptations = []

        mood = context.get("mood", "neutral")
        formality = context.get("formality_level", "moderate")

        if mood == "angry":
            adaptations.append("Applied aggressive dialogue patterns")
        elif mood == "sad":
            adaptations.append("Applied melancholic dialogue patterns")
        elif mood == "happy":
            adaptations.append("Applied upbeat dialogue patterns")

        if formality == "formal":
            adaptations.append("Increased dialogue formality")
        elif formality == "casual":
            adaptations.append("Decreased dialogue formality")

        return adaptations

    def _adapt_emotional_tone(self, character_id: str, context: dict[str, Any]) -> list[str]:
        """Adapt emotional tone based on context."""
        adaptations = []

        emotional_state = context.get("emotional_state", {})
        intensity = emotional_state.get("intensity", 0.5)

        if intensity > 0.7:
            adaptations.append("Increased emotional intensity")
        elif intensity < 0.3:
            adaptations.append("Decreased emotional intensity")

        dominant_emotion = emotional_state.get("dominant_emotion", "neutral")
        adaptations.append(f"Adapted to {dominant_emotion} emotional tone")

        return adaptations

    def _adapt_interaction_style(self, character_id: str, context: dict[str, Any]) -> list[str]:
        """Adapt interaction style based on context."""
        adaptations = []

        relationship_type = context.get("relationship_type", "neutral")
        social_context = context.get("social_context", "normal")

        if relationship_type == "romantic":
            adaptations.append("Applied romantic interaction patterns")
        elif relationship_type == "adversarial":
            adaptations.append("Applied defensive interaction patterns")
        elif relationship_type == "friendly":
            adaptations.append("Applied warm interaction patterns")

        if social_context == "public":
            adaptations.append("Adapted for public interaction")
        elif social_context == "private":
            adaptations.append("Adapted for private interaction")

        return adaptations

    def _adapt_to_scene(self, character_id: str, scene_data: dict[str, Any]) -> list[str]:
        """Adapt character to specific scene context."""
        adaptations = []

        scene_type = scene_data.get("type", "general")
        atmosphere = scene_data.get("atmosphere", "neutral")

        if scene_type == "combat":
            adaptations.append("Adapted for combat scenario")
        elif scene_type == "social":
            adaptations.append("Adapted for social scenario")
        elif scene_type == "exploration":
            adaptations.append("Adapted for exploration scenario")

        if atmosphere == "tense":
            adaptations.append("Adjusted for tense atmosphere")
        elif atmosphere == "relaxed":
            adaptations.append("Adjusted for relaxed atmosphere")

        return adaptations

    def get_behavioral_analysis(self, character_id: str, analysis_type: str = "general") -> dict[str, Any]:
        """
        Get behavioral analysis for character.

        Args:
            character_id: Unique character identifier
            analysis_type: Type of analysis to perform

        Returns:
            Dictionary containing behavioral analysis
        """
        try:
            analysis = {
                "character_id": character_id,
                "analysis_type": analysis_type,
                "timestamp": datetime.now().isoformat(),
                "behavior_patterns": [],
                "recommendations": [],
            }

            # Perform analysis based on type
            if analysis_type == "personality":
                analysis.update(self._analyze_personality_patterns(character_id))
            elif analysis_type == "interaction":
                analysis.update(self._analyze_interaction_patterns(character_id))
            elif analysis_type == "emotional":
                analysis.update(self._analyze_emotional_patterns(character_id))
            else:
                analysis["behavior_patterns"] = ["General behavioral analysis performed"]

            logger.info(f"Generated behavioral analysis for {character_id}: {analysis_type}")
        except Exception as e:
            logger.exception("Error generating behavioral analysis for")
            return {
                "character_id": character_id,
                "analysis_type": analysis_type,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return analysis

    def _analyze_personality_patterns(self, character_id: str) -> dict[str, Any]:
        """Analyze personality patterns for character."""
        return {
            "behavior_patterns": ["Consistent personality traits maintained"],
            "recommendations": ["Continue current personality expression"],
        }

    def _analyze_interaction_patterns(self, character_id: str) -> dict[str, Any]:
        """Analyze interaction patterns for character."""
        return {
            "behavior_patterns": ["Stable interaction dynamics"],
            "recommendations": ["Maintain current interaction style"],
        }

    def _analyze_emotional_patterns(self, character_id: str) -> dict[str, Any]:
        """Analyze emotional patterns for character."""
        return {
            "behavior_patterns": ["Emotional responses within expected ranges"],
            "recommendations": ["Continue emotional consistency"],
        }

    def get_behavior_status(self) -> dict[str, Any]:
        """Get behavior engine status."""
        return {
            "engine_status": "active",
            "behavior_providers_count": len(self.behavior_providers),
            "adaptive_behavior_enabled": self.adaptive_behavior,
            "context_memory_size": self.context_memory_size,
            "provider_types": [provider.__class__.__name__ for provider in self.behavior_providers],
        }
