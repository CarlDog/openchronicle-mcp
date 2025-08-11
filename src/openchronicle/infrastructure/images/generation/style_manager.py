"""
Style Manager - Style and parameter management for image generation

Handles:
- Style templates and presets
- Parameter optimization per provider
- Auto-generation trigger logic
- Style consistency management
"""

import logging
from typing import Dict, List, Optional, Any

from ..shared.image_models import ImageType, ImageSize, ImageProvider


logger = logging.getLogger(__name__)


class StyleManager:
    """Manages styles, presets, and generation parameters"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.auto_generate = config.get("auto_generate", {})
        self.style_presets = self._load_style_presets()
        self.provider_settings = config.get("provider_settings", {})

    def _load_style_presets(self) -> Dict[str, Dict[str, Any]]:
        """Load style presets from configuration"""

        default_presets = {
            "fantasy_portrait": {
                "style_modifiers": [
                    "fantasy art",
                    "detailed character portrait",
                    "high quality",
                    "dramatic lighting",
                ],
                "image_types": [ImageType.CHARACTER],
                "description": "Fantasy character portrait with dramatic lighting",
            },
            "cinematic_scene": {
                "style_modifiers": [
                    "cinematic composition",
                    "atmospheric lighting",
                    "detailed environment",
                    "fantasy setting",
                ],
                "image_types": [ImageType.SCENE, ImageType.LOCATION],
                "description": "Cinematic scene with atmospheric elements",
            },
            "detailed_item": {
                "style_modifiers": [
                    "detailed object",
                    "product photography",
                    "high detail",
                    "clean background",
                ],
                "image_types": [ImageType.ITEM],
                "description": "Detailed item with clean presentation",
            },
            "medieval_fantasy": {
                "style_modifiers": [
                    "medieval fantasy",
                    "detailed armor and weapons",
                    "castle architecture",
                    "period appropriate",
                ],
                "image_types": [
                    ImageType.CHARACTER,
                    ImageType.SCENE,
                    ImageType.LOCATION,
                    ImageType.ITEM,
                ],
                "description": "Medieval fantasy theme",
            },
            "modern_urban": {
                "style_modifiers": [
                    "modern urban setting",
                    "contemporary architecture",
                    "realistic lighting",
                    "city environment",
                ],
                "image_types": [ImageType.SCENE, ImageType.LOCATION],
                "description": "Modern urban environment",
            },
        }

        # Override with config presets if available
        config_presets = self.config.get("style_presets", {})
        default_presets.update(config_presets)

        return default_presets

    def get_style_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific style preset"""
        return self.style_presets.get(preset_name)

    def get_default_style_modifiers(self, image_type: ImageType) -> List[str]:
        """Get default style modifiers for an image type"""
        defaults = {
            ImageType.CHARACTER: ["high quality", "detailed", "portrait"],
            ImageType.SCENE: ["high quality", "detailed", "landscape", "atmospheric"],
            ImageType.LOCATION: [
                "high quality",
                "detailed",
                "environment",
                "architectural",
            ],
            ImageType.ITEM: ["high quality", "detailed", "object", "studio lighting"],
        }
        return defaults.get(image_type, ["high quality", "detailed"])

    def get_presets_for_type(self, image_type: ImageType) -> List[str]:
        """Get available presets for image type"""
        compatible_presets = []

        for preset_name, preset_data in self.style_presets.items():
            if image_type in preset_data.get("image_types", []):
                compatible_presets.append(preset_name)

        return compatible_presets

    def apply_style_preset(
        self, preset_name: str, existing_modifiers: Optional[List[str]] = None
    ) -> List[str]:
        """Apply style preset to existing modifiers"""

        preset = self.get_style_preset(preset_name)
        if not preset:
            logger.warning(f"Style preset '{preset_name}' not found")
            return existing_modifiers or []

        preset_modifiers = preset.get("style_modifiers", [])

        if existing_modifiers:
            # Combine without duplicates, preserving order
            combined = existing_modifiers.copy()
            for modifier in preset_modifiers:
                if modifier not in combined:
                    combined.append(modifier)
            return combined
        else:
            return preset_modifiers.copy()

    def optimize_parameters_for_provider(
        self, provider: ImageProvider, size: ImageSize, image_type: ImageType
    ) -> Dict[str, Any]:
        """Optimize generation parameters for specific provider"""

        provider_name = (
            provider.value if isinstance(provider, ImageProvider) else str(provider)
        )

        # Get provider-specific settings
        provider_config = self.provider_settings.get(provider_name, {})

        # Base parameters
        params = {"size": size.value, "quality": "high"}

        # Provider-specific optimizations
        if provider_name == "openai":
            params.update(
                {
                    "model": provider_config.get("default_model", "dall-e-3"),
                    "quality": provider_config.get("quality", "hd"),
                    "style": provider_config.get("style", "natural"),
                }
            )

        elif provider_name == "stability":
            params.update(
                {
                    "model": provider_config.get(
                        "default_model", "stable-diffusion-xl"
                    ),
                    "cfg_scale": provider_config.get("cfg_scale", 7),
                    "steps": provider_config.get("steps", 50),
                    "sampler": provider_config.get("sampler", "DPM++ 2M Karras"),
                }
            )

        # Image type specific optimizations
        type_params = provider_config.get("type_settings", {}).get(image_type.value, {})
        params.update(type_params)

        return params

    def should_auto_generate_character(
        self,
        character_name: str,
        character_data: Dict[str, Any],
        existing_images: List[Any],
    ) -> bool:
        """Check if character portrait should be auto-generated"""

        if not self.auto_generate.get("character_portraits", False):
            return False

        # Check if character already has a portrait
        has_portrait = any(
            img.image_type == ImageType.CHARACTER for img in existing_images
        )

        if has_portrait:
            logger.info(f"Character {character_name} already has a portrait")
            return False

        # Check character importance or other criteria
        importance = character_data.get("importance", "normal")
        min_importance = self.auto_generate.get("character_min_importance", "normal")

        importance_levels = {"low": 1, "normal": 2, "high": 3, "critical": 4}

        if importance_levels.get(importance, 2) >= importance_levels.get(
            min_importance, 2
        ):
            return True

        return False

    def should_auto_generate_scene(
        self,
        scene_id: str,
        scene_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if scene image should be auto-generated"""

        if not self.auto_generate.get("scene_images", False):
            return False

        # Check for trigger conditions
        triggers = self.auto_generate.get(
            "scene_triggers", ["major_event", "new_location"]
        )

        # Simple trigger detection (can be enhanced)
        should_generate = False

        if (
            "major_event" in triggers
            and scene_data.get("importance", "normal") == "high"
        ):
            should_generate = True

        if "new_location" in triggers and scene_data.get("new_location", False):
            should_generate = True

        if "character_introduction" in triggers and scene_data.get(
            "new_character", False
        ):
            should_generate = True

        # Context-based triggers
        if context:
            if "scene_transition" in triggers and context.get(
                "location_changed", False
            ):
                should_generate = True

            if "dramatic_moment" in triggers and context.get("tension_level", 0) > 7:
                should_generate = True

        return should_generate

    def get_recommended_size(
        self, image_type: ImageType, provider: Optional[ImageProvider] = None
    ) -> ImageSize:
        """Get recommended image size for type and provider"""

        # Type-based recommendations
        type_recommendations = {
            ImageType.CHARACTER: ImageSize.PORTRAIT_512,
            ImageType.SCENE: ImageSize.LANDSCAPE_768,
            ImageType.LOCATION: ImageSize.LANDSCAPE_768,
            ImageType.ITEM: ImageSize.SQUARE_512,
        }

        base_size = type_recommendations.get(image_type, ImageSize.SQUARE_512)

        # Provider-specific adjustments
        if provider:
            provider_name = (
                provider.value if isinstance(provider, ImageProvider) else str(provider)
            )
            provider_config = self.provider_settings.get(provider_name, {})

            # Check for provider size preferences
            size_preferences = provider_config.get("size_preferences", {})
            preferred_size = size_preferences.get(image_type.value)

            if preferred_size:
                try:
                    return ImageSize(preferred_size)
                except ValueError:
                    logger.warning(
                        f"Invalid size preference '{preferred_size}' for {provider_name}"
                    )

        return base_size

    def validate_style_consistency(
        self,
        image_type: ImageType,
        style_modifiers: List[str],
        existing_images: List[Any],
    ) -> Dict[str, Any]:
        """Validate style consistency with existing images"""

        validation = {"consistent": True, "warnings": [], "suggestions": []}

        if not existing_images:
            return validation

        # Analyze existing styles
        existing_styles = []
        for img in existing_images:
            if hasattr(img, "tags") and img.tags:
                existing_styles.extend(img.tags)

        # Check for style conflicts
        style_keywords = [mod.lower() for mod in style_modifiers]

        # Check for art style consistency
        art_styles_in_new = [s for s in style_keywords if "art" in s or "style" in s]
        art_styles_in_existing = [
            s for s in existing_styles if "art" in s or "style" in s
        ]

        if art_styles_in_existing and art_styles_in_new:
            if not any(style in art_styles_in_existing for style in art_styles_in_new):
                validation["warnings"].append(
                    "Art style may be inconsistent with existing images"
                )
                validation["suggestions"].append(
                    f"Consider using similar style: {art_styles_in_existing[0]}"
                )

        return validation

    def create_custom_preset(
        self,
        name: str,
        style_modifiers: List[str],
        image_types: List[ImageType],
        description: str = "",
    ) -> bool:
        """Create a custom style preset"""

        if name in self.style_presets:
            logger.warning(f"Style preset '{name}' already exists")
            return False

        self.style_presets[name] = {
            "style_modifiers": style_modifiers,
            "image_types": image_types,
            "description": description,
            "custom": True,
        }

        logger.info(f"Created custom style preset: {name}")
        return True

    def get_style_statistics(self) -> Dict[str, Any]:
        """Get statistics about style usage"""

        total_presets = len(self.style_presets)
        custom_presets = sum(
            1 for p in self.style_presets.values() if p.get("custom", False)
        )

        # Count presets by image type
        type_counts = {}
        for image_type in ImageType:
            type_counts[image_type.value] = len(self.get_presets_for_type(image_type))

        return {
            "total_presets": total_presets,
            "custom_presets": custom_presets,
            "built_in_presets": total_presets - custom_presets,
            "presets_by_type": type_counts,
            "auto_generation_enabled": bool(self.auto_generate),
            "available_triggers": list(self.auto_generate.get("scene_triggers", [])),
        }
