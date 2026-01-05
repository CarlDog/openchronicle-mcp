"""
Prompt Processor - Intelligent prompt engineering and optimization

Handles:
- Subject description to prompt conversion
- Frame description to prompt conversion
- Prompt optimization and enhancement
- Context-aware prompt building
"""

import logging
from typing import Any

from ..shared.image_models import ImageType


logger = logging.getLogger(__name__)


class PromptProcessor:
    """Processes and optimizes prompts for image generation"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.style_defaults = config.get("style_defaults", {})

    def build_character_prompt(self, character_name: str, character_data: dict[str, Any]) -> str:
        """Build optimized prompt for subject portrait generation"""

        prompt_parts = []

        # Basic description
        if "description" in character_data:
            prompt_parts.append(character_data["description"])

        # Physical traits
        if "appearance" in character_data:
            appearance = character_data["appearance"]
            if isinstance(appearance, dict):
                for key, value in appearance.items():
                    if value:
                        prompt_parts.append(f"{key}: {value}")
            else:
                prompt_parts.append(str(appearance))

        # Personality influences on appearance
        if "personality" in character_data:
            personality = character_data.get("personality", {})
            if "demeanor" in personality:
                prompt_parts.append(f"demeanor: {personality['demeanor']}")

        # Use fallback if no description available
        prompt = ", ".join(prompt_parts) if prompt_parts else f"Portrait of {character_name}"
        return self._optimize_prompt(prompt, ImageType.ENTITY)

    def build_scene_prompt(
        self,
        scene_id: str,
        scene_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Build optimized prompt for frame image generation"""
        prompt_parts = []

        # Segment description
        if "description" in scene_data:
            prompt_parts.append(scene_data["description"])

        # Location/setting
        if "location" in scene_data:
            prompt_parts.append(f"Setting: {scene_data['location']}")

        # Time of day/mood
        if "atmosphere" in scene_data:
            prompt_parts.append(scene_data["atmosphere"])

        # Add context from memory or previous frames
        if context and "recent_events" in context:
            prompt_parts.append(f"Context: {context['recent_events']}")

        # Use fallback if no description available
        prompt = ", ".join(prompt_parts) if prompt_parts else f"Frame {scene_id}"
        return self._optimize_prompt(prompt, ImageType.FRAME)

    def build_location_prompt(self, location_name: str, location_data: dict[str, Any]) -> str:
        """Build optimized prompt for location image generation"""

        prompt_parts = []

        # Location description
        if "description" in location_data:
            prompt_parts.append(location_data["description"])

        # Environment type
        if "type" in location_data:
            prompt_parts.append(f"Type: {location_data['type']}")

        # Atmosphere/mood
        if "atmosphere" in location_data:
            prompt_parts.append(location_data["atmosphere"])

        # Architecture/features
        if "features" in location_data:
            features = location_data["features"]
            if isinstance(features, list):
                prompt_parts.extend(features)
            else:
                prompt_parts.append(str(features))

        prompt = ", ".join(prompt_parts) if prompt_parts else f"Location: {location_name}"

        return self._optimize_prompt(prompt, ImageType.LOCATION)

    def build_item_prompt(self, item_name: str, item_data: dict[str, Any]) -> str:
        """Build optimized prompt for item image generation"""

        prompt_parts = []

        # Item description
        if "description" in item_data:
            prompt_parts.append(item_data["description"])

        # Item type/category
        if "type" in item_data:
            prompt_parts.append(f"Type: {item_data['type']}")

        # Material/construction
        if "material" in item_data:
            prompt_parts.append(f"Material: {item_data['material']}")

        # Special properties
        if "properties" in item_data:
            properties = item_data["properties"]
            if isinstance(properties, list):
                prompt_parts.extend(properties)
            else:
                prompt_parts.append(str(properties))

        prompt = ", ".join(prompt_parts) if prompt_parts else f"Item: {item_name}"

        return self._optimize_prompt(prompt, ImageType.ITEM)

    def _optimize_prompt(self, base_prompt: str, image_type: ImageType) -> str:
        """Optimize prompt for better generation results"""

        # Get type-specific optimization rules
        optimization_rules = self.config.get("prompt_optimization", {})
        type_rules = optimization_rules.get(image_type.value, {})

        # Apply quality modifiers
        quality_modifiers = type_rules.get("quality_modifiers", [])
        if quality_modifiers:
            base_prompt += ", " + ", ".join(quality_modifiers)

        # Apply style guidance
        style_guidance = type_rules.get("style_guidance", [])
        if style_guidance:
            base_prompt += ", " + ", ".join(style_guidance)

        # Apply negative prompts (for compatible providers)
        negative_prompts = type_rules.get("negative_prompts", [])
        if negative_prompts:
            # Note: This would need provider-specific handling
            # For now, we'll store it for potential future use
            pass

        return base_prompt

    def enhance_prompt_with_style(self, base_prompt: str, style_modifiers: list[str]) -> str:
        """Enhance prompt with additional style modifiers"""

        if not style_modifiers:
            return base_prompt

        # Filter out empty or None modifiers
        valid_modifiers = [mod for mod in style_modifiers if mod and mod.strip()]

        if valid_modifiers:
            return base_prompt + ", " + ", ".join(valid_modifiers)
        return base_prompt

    def get_default_style_modifiers(self, image_type: ImageType) -> list[str]:
        """Get default style modifiers for image type"""

        type_defaults = {
            ImageType.ENTITY: [
                "subject portrait",
                "detailed face",
                "high quality",
                "fantasy art",
            ],
            ImageType.FRAME: [
                "detailed environment",
                "atmospheric",
                "cinematic composition",
                "fantasy setting",
            ],
            ImageType.LOCATION: [
                "detailed architecture",
                "environmental shot",
                "atmospheric lighting",
                "fantasy location",
            ],
            ImageType.ITEM: [
                "detailed object",
                "product shot",
                "high detail",
                "fantasy item",
            ],
        }

        # Get defaults from config or use built-in defaults
        config_defaults = self.style_defaults.get(image_type.value, [])
        return config_defaults if config_defaults else type_defaults.get(image_type, [])

    def validate_prompt(self, prompt: str) -> dict[str, Any]:
        """Validate prompt for potential issues"""

        validation_result = {"valid": True, "warnings": [], "suggestions": []}

        # Check prompt length
        if len(prompt) < 10:
            validation_result["warnings"].append("Prompt is very short, may produce poor results")
            validation_result["suggestions"].append("Add more descriptive details")

        if len(prompt) > 500:
            validation_result["warnings"].append("Prompt is very long, may be truncated by provider")
            validation_result["suggestions"].append("Consider shortening to key details")

        # Check for potentially problematic content
        problematic_terms = self.config.get("problematic_terms", [])
        for term in problematic_terms:
            if term.lower() in prompt.lower():
                validation_result["warnings"].append(f"Prompt contains potentially problematic term: {term}")
                validation_result["suggestions"].append("Consider rephrasing to avoid content policy issues")

        # Check for missing key elements
        if ("entity") in prompt.lower() and "face" not in prompt.lower():
            validation_result["suggestions"].append("Consider adding facial description for subject images")

        return validation_result

    def get_prompt_suggestions(self, image_type: ImageType, base_data: dict[str, Any]) -> list[str]:
        """Get suggestions for improving prompts"""

        suggestions: list[str] = []

        if image_type == ImageType.ENTITY:
            if "appearance" not in base_data:
                suggestions.append("Add appearance details (hair, eyes, clothing)")
            if "personality" not in base_data:
                suggestions.append("Add traits that affect appearance")

        elif image_type == ImageType.FRAME:
            if "location" not in base_data:
                suggestions.append("Add location/setting details")
            if "atmosphere" not in base_data:
                suggestions.append("Add mood/atmosphere description")

        elif image_type == ImageType.LOCATION:
            if "type" not in base_data:
                suggestions.append("Specify location type (indoor/outdoor, building type)")
            if "features" not in base_data:
                suggestions.append("Add distinctive architectural features")

        elif image_type == ImageType.ITEM:
            if "type" not in base_data:
                suggestions.append("Specify item category/type")
            if "material" not in base_data:
                suggestions.append("Add material/construction details")

        return suggestions
