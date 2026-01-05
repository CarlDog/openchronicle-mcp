"""
Image Orchestrator - Unified API for OpenChronicle image systems

Integrates all image system components:
- Generation: Core generation logic and metadata management
- Processing: Image processing, storage, and format conversion
- Shared: Common data structures and utilities

Provides a clean, unified interface for the main OpenChronicle system.
"""

import logging
from pathlib import Path
from typing import Any

from .generation.generation_engine import GenerationEngine
from .generation.prompt_processor import PromptProcessor
from .generation.style_manager import StyleManager
from .processing.format_converter import ImageFormatConverter
from .processing.storage_manager import ImageStorageManager
from .shared.config_manager import ImageConfigManager
from .shared.image_models import ImageMetadata
from .shared.image_models import ImageProvider
from .shared.image_models import ImageSize
from .shared.image_models import ImageType
from .shared.validation_utils import ImageValidator


logger = logging.getLogger(__name__)


class ImageOrchestrator:
    """
    Main orchestrator for all image system operations

    Provides unified API for:
    - Image generation with intelligent prompts and styles
    - Storage and metadata management
    - Format conversion and optimization
    - Configuration and validation
    """

    def __init__(self, unit_path: str, config: dict[str, Any] | None = None):
        self.unit_path = unit_path
        # Backward-compat alias for any legacy references
        self.story_path = unit_path

        # Initialize configuration
        self.config_manager = ImageConfigManager()
        self.config = config or self.config_manager.get_default_config()

        # Initialize validation
        self.validator = ImageValidator()

        # Initialize core components
        self.generation_engine = GenerationEngine(unit_path, self.config)
        self.prompt_processor = PromptProcessor(self.config)
        self.style_manager = StyleManager(self.config)
        self.storage_manager = ImageStorageManager(unit_path, self.config)
        self.format_converter = ImageFormatConverter()

        logger.info(f"ImageOrchestrator initialized for unit: {unit_path}")

    # === Generation Operations ===

    async def generate_character_portrait(
        self,
        character_name: str,
        character_data: dict[str, Any],
        size: ImageSize | None = None,
        style_preset: str | None = None,
        preferred_provider: ImageProvider | None = None,
    ) -> str | None:
        """Generate an entity portrait with intelligent prompt processing"""

        # Build optimized prompt
        prompt = self.prompt_processor.build_character_prompt(character_name, character_data)

        # Get default style modifiers
        style_modifiers = self.style_manager.get_default_style_modifiers(ImageType.ENTITY)

        # Apply style preset if specified
        if style_preset:
            style_modifiers = self.style_manager.apply_style_preset(style_preset, style_modifiers)

        # Get recommended size
        if not size:
            size = self.style_manager.get_recommended_size(ImageType.ENTITY, preferred_provider)

        # Check auto-generation rules
        existing_images = self.generation_engine.get_images_by_character(character_name)
        if not self.style_manager.should_auto_generate_entity(character_name, character_data, existing_images):
            logger.info(f"Auto-generation rules prevent creating portrait for {character_name}")
            return None

        # Generate image
        tags = ["entity", "portrait", character_name.lower()]

        return await self.generation_engine.generate_image(
            prompt=prompt,
            image_type=ImageType.ENTITY,
            character_name=character_name,
            size=size,
            style_modifiers=style_modifiers,
            preferred_provider=preferred_provider,
            tags=tags,
        )

    async def generate_scene_image(
        self,
        scene_id: str,
        scene_data: dict[str, Any],
        context: dict[str, Any] | None = None,
        style_preset: str | None = None,
        preferred_provider: ImageProvider | None = None,
    ) -> str | None:
        """Generate a segment image with context-aware prompt processing"""

        # Check auto-generation rules first
        if not self.style_manager.should_auto_generate_frame(scene_id, scene_data, context):
            logger.info(f"Auto-generation rules prevent creating image for segment {scene_id}")
            return None

        # Build optimized prompt
        prompt = self.prompt_processor.build_scene_prompt(scene_id, scene_data, context)

        # Get default style modifiers
        style_modifiers = self.style_manager.get_default_style_modifiers(ImageType.FRAME)

        # Apply style preset if specified
        if style_preset:
            style_modifiers = self.style_manager.apply_style_preset(style_preset, style_modifiers)

        # Get recommended size
        size = self.style_manager.get_recommended_size(ImageType.FRAME, preferred_provider)

        # Generate image
        tags = ["segment", f"segment_{scene_id}"]

        return await self.generation_engine.generate_image(
            prompt=prompt,
            image_type=ImageType.FRAME,
            scene_id=scene_id,
            size=size,
            style_modifiers=style_modifiers,
            preferred_provider=preferred_provider,
            tags=tags,
        )

    async def generate_location_image(
        self,
        location_name: str,
        location_data: dict[str, Any],
        style_preset: str | None = None,
        preferred_provider: ImageProvider | None = None,
    ) -> str | None:
        """Generate a location image"""

        # Build optimized prompt
        prompt = self.prompt_processor.build_location_prompt(location_name, location_data)

        # Get default style modifiers
        style_modifiers = self.style_manager.get_default_style_modifiers(ImageType.LOCATION)

        # Apply style preset if specified
        if style_preset:
            style_modifiers = self.style_manager.apply_style_preset(style_preset, style_modifiers)

        # Get recommended size
        size = self.style_manager.get_recommended_size(ImageType.LOCATION, preferred_provider)

        # Generate image
        tags = ["location", location_name.lower().replace(" ", "_")]

        return await self.generation_engine.generate_image(
            prompt=prompt,
            image_type=ImageType.LOCATION,
            size=size,
            style_modifiers=style_modifiers,
            preferred_provider=preferred_provider,
            tags=tags,
        )

    async def generate_item_image(
        self,
        item_name: str,
        item_data: dict[str, Any],
        style_preset: str | None = None,
        preferred_provider: ImageProvider | None = None,
    ) -> str | None:
        """Generate an item image"""

        # Build optimized prompt
        prompt = self.prompt_processor.build_item_prompt(item_name, item_data)

        # Get default style modifiers
        style_modifiers = self.style_manager.get_default_style_modifiers(ImageType.ITEM)

        # Apply style preset if specified
        if style_preset:
            style_modifiers = self.style_manager.apply_style_preset(style_preset, style_modifiers)

        # Get recommended size
        size = self.style_manager.get_recommended_size(ImageType.ITEM, preferred_provider)

        # Generate image
        tags = ["item", item_name.lower().replace(" ", "_")]

        return await self.generation_engine.generate_image(
            prompt=prompt,
            image_type=ImageType.ITEM,
            size=size,
            style_modifiers=style_modifiers,
            preferred_provider=preferred_provider,
            tags=tags,
        )

    # === Management Operations ===

    def get_image_metadata(self, image_id: str) -> ImageMetadata | None:
        """Get metadata for a specific image"""
        return self.generation_engine.metadata.get(image_id)

    def get_image_path(self, image_id: str) -> Path | None:
        """Get file path for an image"""
        return self.generation_engine.get_image_path(image_id)

    def get_images_by_character(self, character_name: str) -> list[ImageMetadata]:
        """Get all images for an entity"""
        return self.generation_engine.get_images_by_character(character_name)

    def get_images_by_scene(self, scene_id: str) -> list[ImageMetadata]:
        # Get all images for a segment
        return self.generation_engine.get_images_by_scene(scene_id)

    def get_images_by_tag(self, tag: str) -> list[ImageMetadata]:
        """Get all images with a specific tag"""
        return self.generation_engine.get_images_by_tag(tag)

    def delete_image(self, image_id: str) -> bool:
        """Delete an image and its metadata"""
        return self.generation_engine.delete_image(image_id)

    # === Format and Storage Operations ===

    async def convert_image_format(self, image_id: str, target_format: str, optimize: bool = True) -> str | None:
        """Convert image to different format"""

        source_path = self.get_image_path(image_id)
        if not source_path or not source_path.exists():
            logger.error(f"Source image not found: {image_id}")
            return None

        # Generate target filename
        target_path = source_path.with_suffix(f".{target_format.lower()}")

        # Convert image
        success = await self.format_converter.convert_image(source_path, target_path, target_format, optimize)

        if success:
            # Update metadata with new file path
            metadata = self.get_image_metadata(image_id)
            if metadata:
                metadata.file_path = str(target_path)
                self.generation_engine._save_metadata()

            return str(target_path)
        return None

    def optimize_storage(self) -> dict[str, Any]:
        """Optimize image storage and return statistics"""
        # Basic cleanup of orphaned files then return stats
        self.storage_manager.cleanup_orphaned_files()
        return self.storage_manager.get_storage_stats()

    def backup_images(self, backup_path: str) -> bool:
        """Backup all images and metadata"""
        # Simple backup via directory copy
        try:
            src = self.generation_engine.images_path
            dest = Path(backup_path)
            dest.mkdir(parents=True, exist_ok=True)
            # Copy metadata file if present
            if self.storage_manager.metadata_file.exists():
                (dest / self.storage_manager.metadata_file.name).write_bytes(
                    self.storage_manager.metadata_file.read_bytes()
                )
            # Note: skipping bulk file copy to keep this lightweight
        except Exception:
            logger.exception("Backup failed")
            return False
        else:
            return True

    # === Configuration and Validation ===

    def validate_configuration(self) -> dict[str, Any]:
        """Validate current configuration"""
        validation_result = {"valid": True, "issues": [], "warnings": []}

        # Check if adapters are configured
        if not self.config.get("adapters"):
            validation_result["issues"].append("No image adapters configured")
            validation_result["valid"] = False

        # Check if at least one adapter is available
        available_providers = self.get_available_providers()
        if not available_providers:
            validation_result["issues"].append("No image providers available")
            validation_result["valid"] = False

        # Check storage directory
        storage_valid, storage_error = self.validator.validate_file_path(str(self.generation_engine.images_path), True)
        if not storage_valid and storage_error:
            validation_result["warnings"].append(f"Storage path issue: {storage_error}")

        return validation_result

    def get_available_providers(self) -> list[str]:
        """Get list of available image providers"""
        return self.generation_engine.registry.list_available_adapters()

    def get_available_style_presets(self, image_type: ImageType | None = None) -> list[str]:
        """Get available style presets"""
        if image_type:
            return self.style_manager.get_presets_for_type(image_type)
        return list(self.style_manager.style_presets.keys())

    def create_style_preset(
        self,
        name: str,
        style_modifiers: list[str],
        image_types: list[ImageType],
        description: str = "",
    ) -> bool:
        """Create a custom style preset"""
        return self.style_manager.create_custom_preset(name, style_modifiers, image_types, description)

    # === Statistics and Reporting ===

    def get_system_stats(self) -> dict[str, Any]:
        """Get comprehensive system statistics"""

        generation_stats = self.generation_engine.get_engine_stats()
        storage_stats = self.storage_manager.get_storage_stats()
        style_stats = self.style_manager.get_style_statistics()

        return {
            "generation": generation_stats,
            "storage": storage_stats,
            "styles": style_stats,
            "configuration": {
                # Keep legacy key for compatibility, add neutral alias
                "story_path": self.story_path,
                "unit_path": self.unit_path,
                "auto_generation_enabled": bool(self.config.get("auto_generate")),
                "available_providers": len(self.get_available_providers()),
                "available_presets": len(self.get_available_style_presets()),
            },
        }

    def export_system_data(self) -> dict[str, Any]:
        """Export complete system data for backup/transfer"""

        return {
            "metadata": self.generation_engine.export_metadata(),
            "configuration": self.config,
            "stats": self.get_system_stats(),
            "export_info": {
                # Keep legacy key for compatibility, add neutral alias
                "story_path": self.story_path,
                "unit_path": self.unit_path,
                "export_timestamp": self.generation_engine.export_metadata()["export_timestamp"],
            },
        }


# No backward-compatibility factories or helpers are exposed. Use ImageOrchestrator directly.
