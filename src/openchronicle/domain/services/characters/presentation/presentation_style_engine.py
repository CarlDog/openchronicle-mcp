"""
Character Presentation Component

Specialized component for managing character presentation, style profiles,
and model selection. Extracted from character_style_manager.py.
"""

import logging
from typing import Any

from ..character_base import CharacterEngineBase
from ..character_data import CharacterStyleProfile


logger = logging.getLogger(__name__)


class PresentationStyleEngine(CharacterEngineBase):
    """
    Manages character presentation, style profiles, and model selection.

    Handles character-specific model preferences, speech patterns,
    and presentation consistency across different content types.
    """

    def __init__(self, config: dict | None = None):
        """Initialize the presentation style engine."""
        super().__init__(config)

        # Model manager reference (if available)
        self.model_manager = None

        # Configuration
        self.default_models = self.config.get(
            "default_models",
            {
                "dialogue": "gpt-3.5-turbo",
                "narrative": "gpt-4",
                "action": "gpt-3.5-turbo",
            },
        )
        self.style_templates = self.config.get("style_templates", {})

        self.logger.info("Presentation style engine initialized")

    def set_model_manager(self, model_manager) -> None:
        """Set reference to model manager for model operations."""
        self.model_manager = model_manager

    def initialize_character(
        self, character_id: str, **kwargs
    ) -> CharacterStyleProfile:
        """Initialize character style profile."""
        if character_id in self.character_data:
            return self.character_data[character_id]

        # Create new style profile
        profile = CharacterStyleProfile(character_id=character_id)

        # Set default models
        profile.preferred_models = self.default_models.copy()

        # Process any provided style data
        style_data = kwargs.get("style_data", {})
        if style_data:
            self._process_style_data(profile, style_data)

        self.character_data[character_id] = profile
        return profile

    def get_character_data(self, character_id: str) -> CharacterStyleProfile | None:
        """Get character style profile."""
        return self.character_data.get(character_id)

    def load_character_styles(self, story_path: str) -> dict[str, dict[str, Any]]:
        """Load character styles from story directory."""
        import json
        import os

        styles = {}
        characters_dir = os.path.join(story_path, "characters")

        if not os.path.exists(characters_dir):
            return styles

        for char_file in os.listdir(characters_dir):
            if char_file.endswith(".json"):
                char_name = char_file[:-5]  # Remove .json
                char_path = os.path.join(characters_dir, char_file)

                try:
                    with open(char_path, encoding="utf-8") as f:
                        char_data = json.load(f)

                    # Initialize or update style profile
                    profile = self.get_character_data(char_name)
                    if not profile:
                        profile = self.initialize_character(
                            char_name, style_data=char_data
                        )
                    else:
                        self._process_style_data(profile, char_data)

                    styles[char_name] = char_data
                    self.logger.info(f"Loaded style data for {char_name}")

                except Exception as e:
                    self.logger.error(
                        f"Failed to load character style data for {char_name}: {e}"
                    )

        return styles

    # =============================================================================
    # Style Management
    # =============================================================================

    def get_character_style(self, character_name: str) -> dict[str, Any]:
        """Get character style data."""
        profile = self.get_character_data(character_name)
        if not profile:
            return {}

        return {
            "speech_patterns": profile.speech_patterns,
            "personality_traits": profile.personality_traits,
            "emotional_range": profile.emotional_range,
            "preferred_models": profile.preferred_models,
        }

    def update_character_style(
        self, character_name: str, style_updates: dict[str, Any]
    ) -> bool:
        """Update character style data."""
        profile = self.get_character_data(character_name)
        if not profile:
            profile = self.initialize_character(character_name)

        # Update style fields
        if "speech_patterns" in style_updates:
            profile.speech_patterns.update(style_updates["speech_patterns"])
        if "personality_traits" in style_updates:
            profile.personality_traits.update(style_updates["personality_traits"])
        if "emotional_range" in style_updates:
            profile.emotional_range.update(style_updates["emotional_range"])
        if "preferred_models" in style_updates:
            profile.preferred_models.update(style_updates["preferred_models"])

        return True

    # =============================================================================
    # Model Selection
    # =============================================================================

    def select_character_model(
        self, character_name: str, content_type: str = "dialogue"
    ) -> str:
        """Select appropriate model for character and content type."""
        profile = self.get_character_data(character_name)

        # Get preferred model for content type
        if profile and content_type in profile.preferred_models:
            preferred_model = profile.preferred_models[content_type]

            # Validate model is available through model manager
            if self.model_manager and hasattr(self.model_manager, "is_model_available"):
                if self.model_manager.is_model_available(preferred_model):
                    return preferred_model

        # Fall back to default model for content type
        default_model = self.default_models.get(content_type, "gpt-3.5-turbo")

        # Final fallback through model manager
        if self.model_manager and hasattr(self.model_manager, "get_available_model"):
            return self.model_manager.get_available_model(default_model)

        return default_model

    def get_current_character_model(
        self, character_name: str, content_type: str = "dialogue"
    ) -> str:
        """Get currently configured model for character."""
        profile = self.get_character_data(character_name)
        if profile and content_type in profile.preferred_models:
            return profile.preferred_models[content_type]

        return self.default_models.get(content_type, "gpt-3.5-turbo")

    def set_character_model(
        self, character_name: str, content_type: str, model_name: str
    ) -> bool:
        """Set preferred model for character and content type."""
        profile = self.get_character_data(character_name)
        if not profile:
            profile = self.initialize_character(character_name)

        profile.preferred_models[content_type] = model_name
        self.logger.info(f"Set {content_type} model for {character_name}: {model_name}")
        return True

    # =============================================================================
    # Prompt Generation
    # =============================================================================

    def get_character_style_prompt(self, character_name: str, model_name: str) -> str:
        """Generate style prompt for character based on model type."""
        profile = self.get_character_data(character_name)
        if not profile:
            return ""

        style_data = {
            "speech_patterns": profile.speech_patterns,
            "personality_traits": profile.personality_traits,
            "emotional_range": profile.emotional_range,
        }

        # Format based on model type
        if "gpt" in model_name.lower() or "openai" in model_name.lower():
            return self._format_openai_style(style_data)
        if "claude" in model_name.lower() or "anthropic" in model_name.lower():
            return self._format_anthropic_style(style_data)
        if "ollama" in model_name.lower():
            return self._format_ollama_style(style_data)
        return self._format_generic_style(style_data)

    def build_character_context(
        self,
        character_name: str,
        model_name: str,
        scene_context: str = "",
        emotional_state: str = "",
    ) -> dict[str, Any]:
        """Build comprehensive character context for content generation."""
        profile = self.get_character_data(character_name)
        if not profile:
            return {}

        context = {
            "character_name": character_name,
            "model_name": model_name,
            "style_prompt": self.get_character_style_prompt(character_name, model_name),
            "speech_patterns": profile.speech_patterns,
            "personality_traits": profile.personality_traits,
            "emotional_range": profile.emotional_range,
            "scene_context": scene_context,
            "emotional_state": emotional_state,
        }

        return context

    # =============================================================================
    # Consistency Tracking
    # =============================================================================

    def calculate_consistency_score(self, character_name: str) -> float:
        """Calculate style consistency score for character."""
        profile = self.get_character_data(character_name)
        if not profile:
            return 1.0

        return profile.consistency_score

    def update_consistency_score(self, character_name: str, score: float) -> bool:
        """Update character style consistency score."""
        profile = self.get_character_data(character_name)
        if not profile:
            return False

        profile.consistency_score = max(0.0, min(1.0, score))
        return True

    def track_model_performance(
        self, character_name: str, model_name: str, metrics: dict[str, float]
    ) -> None:
        """Track model performance for character."""
        profile = self.get_character_data(character_name)
        if not profile:
            return

        if model_name not in profile.model_performance:
            profile.model_performance[model_name] = {}

        profile.model_performance[model_name].update(metrics)

    def get_model_performance(
        self, character_name: str, model_name: str
    ) -> dict[str, float]:
        """Get model performance metrics for character."""
        profile = self.get_character_data(character_name)
        if not profile:
            return {}

        return profile.model_performance.get(model_name, {})

    # =============================================================================
    # Data Management
    # =============================================================================

    def export_character_data(self, character_id: str) -> dict[str, Any]:
        """Export character presentation data."""
        profile = self.get_character_data(character_id)
        if not profile:
            return {}

        return {
            "character_id": character_id,
            "style_profile": profile.to_dict(),
            "component": "presentation",
            "version": "1.0",
        }

    def import_character_data(self, character_data: dict[str, Any]) -> None:
        """Import character presentation data."""
        character_id = character_data.get("character_id")
        if not character_id:
            return

        try:
            # Import style profile
            if character_data.get("style_profile"):
                profile_data = character_data["style_profile"]
                profile = CharacterStyleProfile.from_dict(profile_data)
                self.character_data[character_id] = profile

            self.logger.info(f"Imported presentation data for character {character_id}")

        except Exception as e:
            self.logger.error(
                f"Failed to import presentation data for {character_id}: {e}"
            )

    # =============================================================================
    # Private Helper Methods
    # =============================================================================

    def _process_style_data(
        self, profile: CharacterStyleProfile, style_data: dict[str, Any]
    ) -> None:
        """Process style data into profile."""
        # Extract speech patterns
        if "speech_style" in style_data:
            profile.speech_patterns.update(style_data["speech_style"])

        # Extract personality traits
        if "personality" in style_data:
            profile.personality_traits.update(style_data["personality"])

        # Extract emotional range
        if "emotional_profile" in style_data:
            emotional_profile = style_data["emotional_profile"]
            if isinstance(emotional_profile, dict):
                profile.emotional_range.update(emotional_profile)

        # Extract model preferences
        if "preferred_models" in style_data:
            profile.preferred_models.update(style_data["preferred_models"])

    def _format_openai_style(self, style: dict[str, Any]) -> str:
        """Format style data for OpenAI models."""
        prompt_parts = []

        # Speech patterns
        if style.get("speech_patterns"):
            patterns = style["speech_patterns"]
            prompt_parts.append(
                f"Speech style: {', '.join(f'{k}: {v}' for k, v in patterns.items())}"
            )

        # Personality traits
        if style.get("personality_traits"):
            traits = style["personality_traits"]
            prompt_parts.append(
                f"Personality: {', '.join(f'{k}: {v}' for k, v in traits.items())}"
            )

        # Emotional range
        if style.get("emotional_range"):
            emotions = style["emotional_range"]
            prompt_parts.append(
                f"Emotional tendencies: {', '.join(f'{k}: {v}' for k, v in emotions.items())}"
            )

        return " | ".join(prompt_parts)

    def _format_anthropic_style(self, style: dict[str, Any]) -> str:
        """Format style data for Anthropic models."""
        prompt_parts = []

        prompt_parts.append("Character style guidelines:")

        if style.get("speech_patterns"):
            prompt_parts.append(f"- Speech: {style['speech_patterns']}")

        if style.get("personality_traits"):
            prompt_parts.append(f"- Personality: {style['personality_traits']}")

        if style.get("emotional_range"):
            prompt_parts.append(f"- Emotions: {style['emotional_range']}")

        return "\n".join(prompt_parts)

    def _format_ollama_style(self, style: dict[str, Any]) -> str:
        """Format style data for Ollama models."""
        # Simpler format for local models
        style_elements = []

        for category, data in style.items():
            if data:
                if isinstance(data, dict):
                    style_elements.extend(data.values())
                else:
                    style_elements.append(str(data))

        return "Character style: " + ", ".join(
            str(elem) for elem in style_elements[:5]
        )  # Limit length

    def _format_generic_style(self, style: dict[str, Any]) -> str:
        """Format style data for generic models."""
        return f"Character style: {style}"
