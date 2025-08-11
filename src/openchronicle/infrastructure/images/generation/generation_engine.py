"""
Image Generation Engine - Core generation logic and orchestration

Handles:
- Image generation coordination and metadata management
- File naming and storage coordination
- Statistics tracking and reporting
- Integration with processing and shared components
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

import httpx

from ..shared.image_models import (
    ImageGenerationRequest,
    ImageMetadata,
    ImageType,
    ImageSize,
    ImageProvider,
)


logger = logging.getLogger(__name__)


class GenerationEngine:
    """Core engine for coordinating image generation"""

    def __init__(self, story_path: str, config: Dict[str, Any]):
        self.story_path = Path(story_path)
        self.images_path = self.story_path / "images"
        self.metadata_file = self.images_path / "images.json"
        self.config = config

        # Initialize adapter registry
        from ..processing.image_adapter import create_image_registry

        self.registry = create_image_registry(config)

        # Engine settings
        self.auto_generate = config.get("auto_generate", {})
        self.naming_config = config.get(
            "naming",
            {
                "character_prefix": "char",
                "scene_prefix": "scene",
                "location_prefix": "loc",
                "item_prefix": "item",
                "custom_prefix": "img",
            },
        )

        # Create images directory
        self.images_path.mkdir(exist_ok=True)

        # Load existing metadata
        self.metadata = self._load_metadata()

        # Statistics
        self.stats = {
            "images_generated": 0,
            "total_cost": 0.0,
            "generation_time": 0.0,
            "providers_used": set(),
        }

    def _load_metadata(self) -> Dict[str, ImageMetadata]:
        """Load image metadata from JSON file"""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            metadata = {}
            for image_id, meta_dict in data.items():
                # Convert dict back to ImageMetadata
                meta_dict["image_type"] = ImageType(meta_dict["image_type"])
                metadata[image_id] = ImageMetadata(**meta_dict)

            logger.info(f"Loaded metadata for {len(metadata)} images")
            return metadata

        except Exception as e:
            logger.error(f"Failed to load image metadata: {e}")
            return {}

    def _save_metadata(self):
        """Save image metadata to JSON file"""
        try:
            data = {
                image_id: meta.to_dict() for image_id, meta in self.metadata.items()
            }

            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"Failed to save image metadata: {e}")

    def _generate_filename(
        self,
        image_type: ImageType,
        name: Optional[str] = None,
        scene_id: Optional[str] = None,
        extension: str = "png",
    ) -> str:
        """Generate filename for image based on type and context"""

        prefix = self.naming_config.get(f"{image_type.value}_prefix", "img")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if image_type == ImageType.CHARACTER and name:
            # char-aletha-20250718_143022.png
            safe_name = "".join(c for c in name.lower() if c.isalnum() or c in "-_")
            return f"{prefix}-{safe_name}-{timestamp}.{extension}"

        elif image_type == ImageType.SCENE and scene_id:
            # scene-000123-20250718_143022.png
            return f"{prefix}-{scene_id}-{timestamp}.{extension}"

        else:
            # Generic naming
            return f"{prefix}-{timestamp}.{extension}"

    def _generate_image_id(
        self, image_type: ImageType, name: Optional[str] = None
    ) -> str:
        """Generate unique image ID"""
        base = f"{image_type.value}"
        if name:
            base += f"_{name}"
        timestamp = int(time.time() * 1000)
        return f"{base}_{timestamp}"

    async def generate_image(
        self,
        prompt: str,
        image_type: ImageType,
        character_name: Optional[str] = None,
        scene_id: Optional[str] = None,
        size: ImageSize = ImageSize.SQUARE_512,
        style_modifiers: Optional[List[str]] = None,
        preferred_provider: Optional[ImageProvider] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Generate an image and save it to the story's images directory

        Returns:
            Image ID if successful, None if failed
        """

        if tags is None:
            tags = []

        # Create generation request
        request = ImageGenerationRequest(
            prompt=prompt,
            image_type=image_type,
            size=size,
            character_name=character_name,
            scene_id=scene_id,
            style_modifiers=style_modifiers,
        )

        logger.info(f"Generating {image_type.value} image: {prompt[:50]}...")

        try:
            # Generate image
            result = await self.registry.generate_image(request, preferred_provider)

            if not result.success:
                logger.error(f"Image generation failed: {result.error_message}")
                return None

            # Generate filename and ID
            filename = self._generate_filename(image_type, character_name, scene_id)
            image_id = self._generate_image_id(image_type, character_name)
            image_path = self.images_path / filename

            # Download and save image
            await self._save_generated_image(result, image_path)

            # Create metadata
            metadata = ImageMetadata(
                image_id=image_id,
                filename=filename,
                image_type=image_type,
                prompt=prompt,
                character_name=character_name,
                scene_id=scene_id,
                provider=(
                    result.metadata.get("model", "unknown")
                    if result.metadata
                    else "unknown"
                ),
                model=(
                    result.metadata.get("model", "unknown")
                    if result.metadata
                    else "unknown"
                ),
                size=size.value,
                generation_time=result.generation_time or 0.0,
                cost=result.cost or 0.0,
                timestamp=datetime.now().isoformat(),
                tags=tags,
            )

            # Save metadata
            self.metadata[image_id] = metadata
            self._save_metadata()

            # Update statistics
            self._update_stats(metadata)

            logger.info(f"Generated image {image_id}: {filename}")
            return image_id

        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            return None

    async def _save_generated_image(self, result, image_path: Path):
        """Save generated image to file system"""
        if result.image_url:
            if result.image_url.startswith("data:"):
                # Handle base64 data URLs (from mock adapter)
                import base64

                header, data = result.image_url.split(",", 1)
                image_data = base64.b64decode(data)

                with open(image_path, "wb") as f:
                    f.write(image_data)

            else:
                # Download from URL
                async with httpx.AsyncClient() as client:
                    response = await client.get(result.image_url)
                    response.raise_for_status()

                    with open(image_path, "wb") as f:
                        f.write(response.content)

    def _update_stats(self, metadata: ImageMetadata):
        """Update engine statistics"""
        self.stats["images_generated"] += 1
        self.stats["total_cost"] += metadata.cost
        self.stats["generation_time"] += metadata.generation_time
        self.stats["providers_used"].add(metadata.provider)

    def get_image_path(self, image_id: str) -> Optional[Path]:
        """Get the file path for an image"""
        if image_id in self.metadata:
            return self.images_path / self.metadata[image_id].filename
        return None

    def get_images_by_character(self, character_name: str) -> List[ImageMetadata]:
        """Get all images for a specific character"""
        return [
            meta
            for meta in self.metadata.values()
            if meta.character_name
            and meta.character_name.lower() == character_name.lower()
        ]

    def get_images_by_scene(self, scene_id: str) -> List[ImageMetadata]:
        """Get all images for a specific scene"""
        return [meta for meta in self.metadata.values() if meta.scene_id == scene_id]

    def get_images_by_tag(self, tag: str) -> List[ImageMetadata]:
        """Get all images with a specific tag"""
        return [
            meta
            for meta in self.metadata.values()
            if tag.lower() in [t.lower() for t in meta.tags]
        ]

    def delete_image(self, image_id: str) -> bool:
        """Delete an image and its metadata"""
        if image_id not in self.metadata:
            return False

        try:
            # Delete file
            image_path = self.get_image_path(image_id)
            if image_path and image_path.exists():
                image_path.unlink()

            # Remove metadata
            del self.metadata[image_id]
            self._save_metadata()

            logger.info(f"Deleted image {image_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete image {image_id}: {e}")
            return False

    def get_engine_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        stats = self.stats.copy()
        stats["providers_used"] = list(stats["providers_used"])
        stats["total_images"] = len(self.metadata)
        stats["available_adapters"] = self.registry.list_available_adapters()
        return stats

    def export_metadata(self) -> Dict[str, Any]:
        """Export all metadata for backup/transfer"""
        return {
            "metadata": {id: meta.to_dict() for id, meta in self.metadata.items()},
            "stats": self.get_engine_stats(),
            "export_timestamp": datetime.now().isoformat(),
        }
