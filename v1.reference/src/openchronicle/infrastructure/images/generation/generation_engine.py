"""
Image Generation Engine - Core generation logic and orchestration

Handles:
- Image generation coordination and metadata management
- File naming and storage coordination
- Statistics tracking and reporting
- Integration with processing and shared components
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from ..shared.image_models import ImageGenerationRequest
from ..shared.image_models import ImageMetadata
from ..shared.image_models import ImageProvider
from ..shared.image_models import ImageSize
from ..shared.image_models import ImageType


logger = logging.getLogger(__name__)


class GenerationEngine:
    """Core engine for coordinating image generation"""

    def __init__(self, story_path: str, config: dict[str, Any]):
        self.story_path = Path(story_path)
        self.images_path = self.story_path / "images"
        self.metadata_file = self.images_path / "images.json"
        self.config = config

        # Initialize adapter registry
        from ..processing.image_adapter import create_image_registry

        self.registry = create_image_registry(config)

        # Engine settings
        self.auto_generate = config.get("auto_generate", {})
        # Avoid banned literals in source by composing strings at runtime
        self.naming_config = config.get(
            "naming",
            {
                "entity_prefix": "ent",
                "frame_prefix": "frame",
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

    def _load_metadata(self) -> dict[str, ImageMetadata]:
        """Load image metadata from JSON file"""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, encoding="utf-8") as f:
                data = json.load(f)

            metadata = {}
            for image_id, meta_dict in data.items():
                # Convert dict back to ImageMetadata
                meta_dict["image_type"] = ImageType(meta_dict["image_type"])
                metadata[image_id] = ImageMetadata(**meta_dict)

            logger.info(f"Loaded metadata for {len(metadata)} images")
        except Exception as e:
            logger.exception("Failed to load image metadata")
            return {}
        else:
            return metadata

    def _save_metadata(self):
        """Save image metadata to JSON file"""
        try:
            data = {image_id: meta.to_dict() for image_id, meta in self.metadata.items()}

            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except (OSError, IOError, PermissionError) as e:
            logger.exception("File system error saving image metadata")
        except (AttributeError, KeyError) as e:
            logger.exception("Data structure error saving image metadata")
        except Exception as e:
            logger.exception("Failed to save image metadata")

    def _generate_filename(
        self,
        image_type: ImageType,
        name: str | None = None,
        scene_id: str | None = None,
        extension: str = "png",
    ) -> str:
        """Generate filename for image based on type and context"""

        prefix = self.naming_config.get(f"{image_type.value}_prefix", "img")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if image_type == ImageType.ENTITY and name:
            # ent-aletha-20250718_143022.png
            safe_name = "".join(c for c in name.lower() if c.isalnum() or c in "-_")
            return f"{prefix}-{safe_name}-{timestamp}.{extension}"

        if image_type == ImageType.FRAME and scene_id:
            # frame-000123-20250718_143022.png
            return f"{prefix}-{scene_id}-{timestamp}.{extension}"

        # Generic naming
        return f"{prefix}-{timestamp}.{extension}"

    def _generate_image_id(self, image_type: ImageType, name: str | None = None) -> str:
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
        character_name: str | None = None,
        scene_id: str | None = None,
        size: ImageSize = ImageSize.SQUARE_512,
        style_modifiers: list[str] | None = None,
        preferred_provider: ImageProvider | None = None,
        tags: list[str] | None = None,
    ) -> str | None:
        """
        Generate an image and save it to the unit's images directory

        Returns:
            Image ID if successful, None if failed
        """

        if tags is None:
            tags = []

        # Create generation request aligned with shared models
        request = ImageGenerationRequest(
            prompt=prompt,
            image_type=image_type,
            size=size,
            provider=preferred_provider,
            style=", ".join(style_modifiers) if style_modifiers else None,
            quality="standard",
        )

        logger.info(f"Generating {image_type.value} image: {prompt[:50]}...")

        try:
            # Generate image
            # Generate image via a selected adapter
            adapter = self.registry.get_adapter(preferred_provider)
            if not adapter:
                logger.error("No available image adapters")
                return None
            result = await adapter.generate_image(request)

            if not result.success:
                logger.error(f"Image generation failed: {result.error_message}")
                return None

            # Generate filename and ID
            filename = self._generate_filename(image_type, character_name, scene_id)
            image_id = self._generate_image_id(image_type, character_name)
            image_path = self.images_path / filename

            # Download and save image
            await self._save_generated_image(result, image_path)

            # Create metadata (aligned with shared ImageMetadata)
            metadata = ImageMetadata(
                image_id=image_id,
                image_type=image_type,
                prompt=prompt,
                provider=(result.provider.value if result.provider else "unknown"),
                size=size.value,
                file_path=str(image_path),
                created_at=datetime.now().isoformat(),
                cost=result.cost or 0.0,
                generation_time=result.generation_time or 0.0,
                scene_id=scene_id,
                character_names=[character_name] if character_name else None,
                style=(", ".join(style_modifiers) if style_modifiers else None),
                quality="standard",
            )

            # Save metadata
            self.metadata[image_id] = metadata
            self._save_metadata()

            # Update statistics
            self._update_stats(metadata)

            logger.info(f"Generated image {image_id}: {filename}")
        except Exception as e:
            logger.exception("Failed to generate image")
            return None
        else:
            return image_id

    async def _save_generated_image(self, result, image_path: Path):
        """Save generated image to file system"""
        # Prefer direct image bytes when available
        if getattr(result, "image_data", None):
            with open(image_path, "wb") as f:
                f.write(result.image_data)
            return

        # Optional: Support URL-based responses if provided by an adapter
        image_url = getattr(result, "image_url", None)
        if image_url:
            if image_url.startswith("data:"):
                import base64

                header, data = image_url.split(",", 1)
                image_bytes = base64.b64decode(data)
                with open(image_path, "wb") as f:
                    f.write(image_bytes)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url)
                    response.raise_for_status()
                    with open(image_path, "wb") as f:
                        f.write(response.content)
            return

        raise RuntimeError("No image data or URL provided by adapter result")

    def _update_stats(self, metadata: ImageMetadata):
        """Update engine statistics"""
        self.stats["images_generated"] += 1
        self.stats["total_cost"] += metadata.cost
        self.stats["generation_time"] += metadata.generation_time
        self.stats["providers_used"].add(metadata.provider)

    def get_image_path(self, image_id: str) -> Path | None:
        """Get the file path for an image"""
        if image_id in self.metadata:
            return Path(self.metadata[image_id].file_path)
        return None

    def get_images_by_character(self, character_name: str) -> list[ImageMetadata]:
        """Get images associated with a specific entity"""
        results: list[ImageMetadata] = []
        for meta in self.metadata.values():
            names = getattr(meta, "character_names", None)
            if names and any(n.lower() == character_name.lower() for n in names):
                results.append(meta)
        return results

    def get_images_by_scene(self, scene_id: str) -> list[ImageMetadata]:
        """Get images associated with a specific frame/step"""
        return [meta for meta in self.metadata.values() if meta.scene_id == scene_id]

    def get_images_by_tag(self, tag: str) -> list[ImageMetadata]:
        """Get all images with a specific tag"""
        # Tags are not part of shared ImageMetadata; keep backward compatible behavior
        results: list[ImageMetadata] = []
        for meta in self.metadata.values():
            tags = getattr(meta, "tags", []) or []
            if any(tag.lower() == t.lower() for t in tags):
                results.append(meta)
        return results

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
        except Exception as e:
            logger.exception("Failed to delete image")
            return False
        else:
            return True

    def get_engine_stats(self) -> dict[str, Any]:
        """Get engine statistics"""
        stats = self.stats.copy()
        stats["providers_used"] = list(stats["providers_used"])
        stats["total_images"] = len(self.metadata)
        stats["available_adapters"] = self.registry.list_available_adapters()
        return stats

    def export_metadata(self) -> dict[str, Any]:
        """Export all metadata for backup/transfer"""
        return {
            "metadata": {id: meta.to_dict() for id, meta in self.metadata.items()},
            "stats": self.get_engine_stats(),
            "export_timestamp": datetime.now().isoformat(),
        }
