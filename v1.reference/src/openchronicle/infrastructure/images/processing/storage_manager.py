"""
Image Storage Manager for OpenChronicle

Handles image file storage, metadata persistence, and directory management.
Extracted from image_generation_engine.py
"""

import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..shared.image_models import ImageGenerationResult
from ..shared.image_models import ImageMetadata
from ..shared.image_models import ImageType
from ..shared.image_models import NamingConfig
from ..shared.validation_utils import ImageValidationError
from ..shared.validation_utils import ImageValidator


logger = logging.getLogger(__name__)


class ImageStorageManager:
    """Manages image file storage and metadata"""

    def __init__(self, story_path: str, naming_config: NamingConfig | None = None):
        self.story_path = Path(story_path)
        self.images_path = self.story_path / "images"
        self.metadata_file = self.images_path / "images.json"

        # Set up naming configuration
        self.naming_config = naming_config or {
            "entity_prefix": "ent",
            "frame_prefix": "frame",
            "location_prefix": "loc",
            "item_prefix": "item",
            "custom_prefix": "img",
        }

        # Create images directory (with parents)
        self.images_path.mkdir(parents=True, exist_ok=True)

        # Initialize subdirectories
        self._create_subdirectories()

        # Load existing metadata
        self.metadata = self._load_metadata()

    def _create_subdirectories(self):
        """Create organized subdirectories for different image types"""
        subdirs = ["characters", "scenes", "locations", "items", "custom"]

        for subdir in subdirs:
            subdir_path = self.images_path / subdir
            subdir_path.mkdir(parents=True, exist_ok=True)

    def _load_metadata(self) -> dict[str, ImageMetadata]:
        """Load image metadata from JSON file"""
        if not self.metadata_file.exists():
            logger.info("No existing image metadata found, starting fresh")
            return {}

        try:
            with open(self.metadata_file, encoding="utf-8") as f:
                data = json.load(f)

            metadata: dict[str, ImageMetadata] = {}
            for image_id, meta_dict in data.items():
                try:
                    metadata[image_id] = ImageMetadata.from_dict(meta_dict)
                except (ValueError, TypeError, KeyError) as e:
                    logger.warning(f"Failed to load metadata for image {image_id}: {e}")
                    continue

            logger.info(f"Loaded metadata for {len(metadata)} images")
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.exception("Failed to load image metadata")
            return {}
        else:
            return metadata

    def _save_metadata(self):
        """Save image metadata to JSON file"""
        try:
            # Convert metadata to dictionary format
            data: dict[str, Any] = {}
            for image_id, metadata in self.metadata.items():
                data[image_id] = metadata.to_dict()

            # Write to file with backup
            temp_file = self.metadata_file.with_suffix(".json.tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic replace
            temp_file.replace(self.metadata_file)
            logger.debug(f"Saved metadata for {len(data)} images")
        except (OSError, TypeError, ValueError) as e:
            logger.exception("Failed to save image metadata")
            raise ImageValidationError(f"Could not save metadata: {e}") from e

    def generate_image_id(self, image_type: ImageType, context: dict[str, Any] | None = None) -> str:
        """Generate a unique image ID based on type and context"""
        # Get prefix based on type
        prefix_map = {
            ImageType.ENTITY: self.naming_config.get("entity_prefix", "ent"),
            ImageType.FRAME: self.naming_config.get("frame_prefix", "frame"),
            ImageType.LOCATION: self.naming_config["location_prefix"],
            ImageType.ITEM: self.naming_config["item_prefix"],
            ImageType.CUSTOM: self.naming_config["custom_prefix"],
        }

        prefix = prefix_map.get(image_type, "img")

        # Add context if available
        context_part = ""
        if context:
            if context.get("character_names"):
                context_part = f"_{context['character_names'][0]}"
            elif context.get("scene_id"):
                context_part = f"_scene{context['scene_id']}"
            elif context.get("location"):
                # Sanitize location name
                location = ImageValidator.sanitize_filename(context["location"])[:20]
                context_part = f"_{location}"

        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Generate base ID
        base_id = f"{prefix}{context_part}_{timestamp}"

        # Ensure uniqueness
        counter = 1
        image_id = base_id
        while image_id in self.metadata:
            image_id = f"{base_id}_{counter}"
            counter += 1

        return image_id

    def get_file_path(self, image_id: str, image_type: ImageType, extension: str = ".png") -> str:
        """Get the file path for an image"""
        # Determine subdirectory based on type
        subdir_map = {
            ImageType.ENTITY: "entities",
            ImageType.FRAME: "frames",
            ImageType.LOCATION: "locations",
            ImageType.ITEM: "items",
            ImageType.CUSTOM: "custom",
        }

        subdir = subdir_map.get(image_type, "custom")

        # Sanitize filename
        safe_filename = ImageValidator.sanitize_filename(f"{image_id}{extension}")

        return str(self.images_path / subdir / safe_filename)

    def store_image(
        self,
        result: ImageGenerationResult,
        image_id: str,
        image_type: ImageType,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> ImageMetadata:
        """Store an image and create metadata"""

        # Validate result
        validation_issues = ImageValidator.validate_result(result)
        if validation_issues:
            raise ImageValidationError(f"Invalid result: {'; '.join(validation_issues)}")

        if not result.success:
            raise ImageValidationError("Cannot store failed image generation result")

        # Determine file extension based on image data
        extension = ".png"  # Default
        if result.image_data:
            # Try to detect format from image data
            if result.image_data.startswith(b"\xff\xd8"):
                extension = ".jpg"
            elif result.image_data.startswith(b"RIFF") and b"WEBP" in result.image_data[:20]:
                extension = ".webp"

        # Get file path
        file_path = self.get_file_path(image_id, image_type, extension)

        # Validate file path
        valid, error = ImageValidator.validate_file_path(file_path, create_dirs=True)
        if not valid:
            raise ImageValidationError(f"Invalid file path: {error}")

        # Ensure there is something to store before attempting IO
        if not result.image_data and not result.image_path:
            raise ImageValidationError("No image data or path in result")

        try:
            # Store the image file
            if result.image_data:
                with open(file_path, "wb") as f:
                    f.write(result.image_data)
            else:
                shutil.copy2(result.image_path, file_path)

            # Create metadata
            metadata = ImageMetadata(
                image_id=image_id,
                image_type=image_type,
                prompt=prompt,
                provider=result.provider.value if result.provider else "unknown",
                size=context.get("size", "unknown") if context else "unknown",
                file_path=file_path,
                created_at=datetime.now().isoformat(),
                cost=result.cost or 0.0,
                generation_time=result.generation_time or 0.0,
                story_id=context.get("story_id") if context else None,
                scene_id=context.get("scene_id") if context else None,
                character_names=context.get("character_names") if context else None,
                location=context.get("location") if context else None,
                style=context.get("style") if context else None,
                negative_prompt=context.get("negative_prompt") if context else None,
                quality=context.get("quality", "standard") if context else "standard",
            )

            # Validate metadata
            validation_issues = ImageValidator.validate_metadata(metadata)
            if validation_issues:
                logger.warning(f"Metadata validation issues: {'; '.join(validation_issues)}")

            # Store metadata
            self.metadata[image_id] = metadata
            self._save_metadata()

            logger.info(f"Stored image {image_id} at {file_path}")
        except (OSError, ImageValidationError, ValueError, TypeError) as e:
            # Cleanup on failure
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

            logger.exception("Failed to store image")
            raise ImageValidationError(f"Storage failed: {e}") from e
        else:
            return metadata

    def get_image_metadata(self, image_id: str) -> ImageMetadata | None:
        """Get metadata for an image"""
        return self.metadata.get(image_id)

    def list_images(self, image_type: ImageType | None = None, limit: int | None = None) -> list[ImageMetadata]:
        """List stored images, optionally filtered by type"""
        images = list(self.metadata.values())

        if image_type:
            images = [img for img in images if img.image_type == image_type]

        # Sort by creation date (newest first)
        images.sort(key=lambda x: x.created_at, reverse=True)

        if limit:
            images = images[:limit]

        return images

    def delete_image(self, image_id: str) -> bool:
        """Delete an image and its metadata"""
        if image_id not in self.metadata:
            logger.warning(f"Image {image_id} not found in metadata")
            return False

        metadata = self.metadata[image_id]

        try:
            # Remove file
            if os.path.exists(metadata.file_path):
                os.remove(metadata.file_path)
                logger.info(f"Deleted image file: {metadata.file_path}")

            # Remove metadata
            del self.metadata[image_id]
            self._save_metadata()

            logger.info(f"Deleted image {image_id}")
        except (OSError, KeyError) as e:
            logger.exception("Failed to delete image")
            return False
        else:
            return True

    def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics"""
        total_images = len(self.metadata)
        total_cost = sum(img.cost for img in self.metadata.values())
        total_size = 0

        # Calculate total file size
        for metadata in self.metadata.values():
            if os.path.exists(metadata.file_path):
                total_size += os.path.getsize(metadata.file_path)

        # Count by type
        type_counts = {}
        for metadata in self.metadata.values():
            type_name = metadata.image_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        # Provider usage
        provider_counts = {}
        for metadata in self.metadata.values():
            provider_counts[metadata.provider] = provider_counts.get(metadata.provider, 0) + 1

        return {
            "total_images": total_images,
            "total_cost": total_cost,
            "total_size_mb": total_size / (1024 * 1024),
            "avg_cost_per_image": total_cost / max(1, total_images),
            "images_by_type": type_counts,
            "images_by_provider": provider_counts,
            "storage_path": str(self.images_path),
        }

    def cleanup_orphaned_files(self) -> int:
        """Remove image files that don't have metadata entries"""
        orphaned_count = 0

        for subdir in ["characters", "scenes", "locations", "items", "custom"]:
            subdir_path = self.images_path / subdir
            if not subdir_path.exists():
                continue

            for file_path in subdir_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in [
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".webp",
                ]:
                    # Check if any metadata references this file
                    referenced = any(
                        Path(metadata.file_path).name == file_path.name for metadata in self.metadata.values()
                    )

                    if not referenced:
                        try:
                            file_path.unlink()
                            orphaned_count += 1
                            logger.info(f"Removed orphaned file: {file_path}")
                        except OSError as e:
                            logger.exception("Failed to remove orphaned file")

        return orphaned_count
