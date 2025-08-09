"""
Image Storage Manager for OpenChronicle

Handles image file storage, metadata persistence, and directory management.
Extracted from image_generation_engine.py
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..shared.image_models import (
    ImageMetadata, ImageType, ImageGenerationResult, NamingConfig
)
from ..shared.validation_utils import ImageValidator, ImageValidationError

logger = logging.getLogger(__name__)


class ImageStorageManager:
    """Manages image file storage and metadata"""
    
    def __init__(self, story_path: str, naming_config: Optional[NamingConfig] = None):
        self.story_path = Path(story_path)
        self.images_path = self.story_path / "images"
        self.metadata_file = self.images_path / "images.json"
        
        # Set up naming configuration
        self.naming_config = naming_config or {
            "character_prefix": "char",
            "scene_prefix": "scene", 
            "location_prefix": "loc",
            "item_prefix": "item",
            "custom_prefix": "img"
        }
        
        # Create images directory
        self.images_path.mkdir(exist_ok=True)
        
        # Initialize subdirectories
        self._create_subdirectories()
        
        # Load existing metadata
        self.metadata: Dict[str, ImageMetadata] = self._load_metadata()
    
    def _create_subdirectories(self):
        """Create organized subdirectories for different image types"""
        subdirs = ['characters', 'scenes', 'locations', 'items', 'custom']
        
        for subdir in subdirs:
            subdir_path = self.images_path / subdir
            subdir_path.mkdir(exist_ok=True)
    
    def _load_metadata(self) -> Dict[str, ImageMetadata]:
        """Load image metadata from JSON file"""
        if not self.metadata_file.exists():
            logger.info("No existing image metadata found, starting fresh")
            return {}
            
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            metadata = {}
            for image_id, meta_dict in data.items():
                try:
                    metadata[image_id] = ImageMetadata.from_dict(meta_dict)
                except Exception as e:
                    logger.warning(f"Failed to load metadata for image {image_id}: {e}")
                    continue
                
            logger.info(f"Loaded metadata for {len(metadata)} images")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to load image metadata: {e}")
            return {}
    
    def _save_metadata(self):
        """Save image metadata to JSON file"""
        try:
            # Convert metadata to dictionary format
            data = {}
            for image_id, metadata in self.metadata.items():
                data[image_id] = metadata.to_dict()
            
            # Write to file with backup
            temp_file = self.metadata_file.with_suffix('.json.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic replace
            temp_file.replace(self.metadata_file)
            logger.debug(f"Saved metadata for {len(data)} images")
            
        except Exception as e:
            logger.error(f"Failed to save image metadata: {e}")
            raise ImageValidationError(f"Could not save metadata: {e}")
    
    def generate_image_id(self, image_type: ImageType, context: Optional[Dict[str, Any]] = None) -> str:
        """Generate a unique image ID based on type and context"""
        # Get prefix based on type
        prefix_map = {
            ImageType.CHARACTER: self.naming_config["character_prefix"],
            ImageType.SCENE: self.naming_config["scene_prefix"],
            ImageType.LOCATION: self.naming_config["location_prefix"],
            ImageType.ITEM: self.naming_config["item_prefix"],
            ImageType.CUSTOM: self.naming_config["custom_prefix"]
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
            ImageType.CHARACTER: "characters",
            ImageType.SCENE: "scenes",
            ImageType.LOCATION: "locations",
            ImageType.ITEM: "items",
            ImageType.CUSTOM: "custom"
        }
        
        subdir = subdir_map.get(image_type, "custom")
        
        # Sanitize filename
        safe_filename = ImageValidator.sanitize_filename(f"{image_id}{extension}")
        
        return str(self.images_path / subdir / safe_filename)
    
    def store_image(self, result: ImageGenerationResult, image_id: str, 
                   image_type: ImageType, prompt: str, 
                   context: Optional[Dict[str, Any]] = None) -> ImageMetadata:
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
            if result.image_data.startswith(b'\xff\xd8'):
                extension = ".jpg"
            elif result.image_data.startswith(b'RIFF') and b'WEBP' in result.image_data[:20]:
                extension = ".webp"
        
        # Get file path
        file_path = self.get_file_path(image_id, image_type, extension)
        
        # Validate file path
        valid, error = ImageValidator.validate_file_path(file_path, create_dirs=True)
        if not valid:
            raise ImageValidationError(f"Invalid file path: {error}")
        
        try:
            # Store the image file
            if result.image_data:
                with open(file_path, 'wb') as f:
                    f.write(result.image_data)
            elif result.image_path:
                shutil.copy2(result.image_path, file_path)
            else:
                raise ImageValidationError("No image data or path in result")
            
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
                quality=context.get("quality", "standard") if context else "standard"
            )
            
            # Validate metadata
            validation_issues = ImageValidator.validate_metadata(metadata)
            if validation_issues:
                logger.warning(f"Metadata validation issues: {'; '.join(validation_issues)}")
            
            # Store metadata
            self.metadata[image_id] = metadata
            self._save_metadata()
            
            logger.info(f"Stored image {image_id} at {file_path}")
            return metadata
            
        except Exception as e:
            # Cleanup on failure
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
            
            logger.error(f"Failed to store image {image_id}: {e}")
            raise ImageValidationError(f"Storage failed: {e}")
    
    def get_image_metadata(self, image_id: str) -> Optional[ImageMetadata]:
        """Get metadata for an image"""
        return self.metadata.get(image_id)
    
    def list_images(self, image_type: Optional[ImageType] = None, 
                   limit: Optional[int] = None) -> List[ImageMetadata]:
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
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete image {image_id}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
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
            "storage_path": str(self.images_path)
        }
    
    def cleanup_orphaned_files(self) -> int:
        """Remove image files that don't have metadata entries"""
        orphaned_count = 0
        
        for subdir in ['characters', 'scenes', 'locations', 'items', 'custom']:
            subdir_path = self.images_path / subdir
            if not subdir_path.exists():
                continue
            
            for file_path in subdir_path.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']:
                    # Check if any metadata references this file
                    referenced = any(
                        Path(metadata.file_path).name == file_path.name 
                        for metadata in self.metadata.values()
                    )
                    
                    if not referenced:
                        try:
                            file_path.unlink()
                            orphaned_count += 1
                            logger.info(f"Removed orphaned file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove orphaned file {file_path}: {e}")
        
        return orphaned_count
