"""
Image System Validation Utilities for OpenChronicle

Provides validation functions for image requests, results, and system state.
Consolidates validation logic from image generation and adapter components.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .image_models import (
    ImageGenerationRequest, ImageGenerationResult, ImageMetadata, 
    ImageProvider, ImageSize, ImageType
)

class ImageValidationError(Exception):
    """Custom exception for image validation errors"""
    pass


class ImageValidator:
    """Validates image system components and requests"""
    
    @staticmethod
    def validate_request(request: ImageGenerationRequest) -> List[str]:
        """Validate an image generation request"""
        issues = []
        
        # Validate prompt
        if not request.prompt or not request.prompt.strip():
            issues.append("Prompt cannot be empty")
        elif len(request.prompt) > 4000:
            issues.append("Prompt too long (max 4000 characters)")
        elif len(request.prompt) < 3:
            issues.append("Prompt too short (min 3 characters)")
        
        # Check for potentially problematic content
        if any(word in request.prompt.lower() for word in ['nsfw', 'explicit', 'graphic']):
            issues.append("Prompt may contain inappropriate content")
        
        # Validate provider compatibility
        if request.provider == ImageProvider.OPENAI_DALLE:
            if request.size not in [ImageSize.SQUARE_1024, ImageSize.PORTRAIT_512, ImageSize.LANDSCAPE_768]:
                issues.append(f"OpenAI DALL-E does not support size {request.size.value}")
        
        # Validate style parameter
        if request.style and len(request.style) > 200:
            issues.append("Style parameter too long (max 200 characters)")
        
        # Validate negative prompt
        if request.negative_prompt and len(request.negative_prompt) > 1000:
            issues.append("Negative prompt too long (max 1000 characters)")
        
        return issues
    
    @staticmethod
    def validate_result(result: ImageGenerationResult) -> List[str]:
        """Validate an image generation result"""
        issues = []
        
        if result.success:
            # Check that successful results have required data
            if not result.image_path and not result.image_data:
                issues.append("Successful result must have image_path or image_data")
            
            if result.image_path and not os.path.exists(result.image_path):
                issues.append(f"Image file does not exist: {result.image_path}")
            
            if result.generation_time < 0:
                issues.append("Generation time cannot be negative")
            
            if result.cost < 0:
                issues.append("Cost cannot be negative")
        else:
            # Check that failed results have error message
            if not result.error_message:
                issues.append("Failed result must have error_message")
        
        return issues
    
    @staticmethod
    def validate_metadata(metadata: ImageMetadata) -> List[str]:
        """Validate image metadata"""
        issues = []
        
        # Validate required fields
        if not metadata.image_id:
            issues.append("Image ID is required")
        elif not re.match(r'^[a-zA-Z0-9_-]+$', metadata.image_id):
            issues.append("Image ID must contain only alphanumeric characters, underscores, and hyphens")
        
        if not metadata.prompt:
            issues.append("Prompt is required in metadata")
        
        if not metadata.provider:
            issues.append("Provider is required in metadata")
        
        if not metadata.file_path:
            issues.append("File path is required in metadata")
        elif not os.path.exists(metadata.file_path):
            issues.append(f"Metadata references non-existent file: {metadata.file_path}")
        
        # Validate timestamp format
        try:
            from datetime import datetime
            datetime.fromisoformat(metadata.created_at)
        except ValueError:
            issues.append("Invalid created_at timestamp format")
        
        # Validate numeric fields
        if metadata.cost < 0:
            issues.append("Cost cannot be negative")
        
        if metadata.generation_time < 0:
            issues.append("Generation time cannot be negative")
        
        return issues
    
    @staticmethod
    def validate_file_path(file_path: str, create_dirs: bool = False) -> Tuple[bool, Optional[str]]:
        """Validate a file path for image storage"""
        try:
            path = Path(file_path)
            
            # Check if parent directory exists
            if not path.parent.exists():
                if create_dirs:
                    path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    return False, f"Parent directory does not exist: {path.parent}"
            
            # Check if path is writable
            if path.exists() and not os.access(path, os.W_OK):
                return False, f"File is not writable: {file_path}"
            
            if not path.exists() and not os.access(path.parent, os.W_OK):
                return False, f"Parent directory is not writable: {path.parent}"
            
            # Check file extension
            valid_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.gif'}
            if path.suffix.lower() not in valid_extensions:
                return False, f"Invalid file extension: {path.suffix}. Must be one of {valid_extensions}"
            
            return True, None
            
        except Exception as e:
            return False, f"Invalid file path: {e}"
    
    @staticmethod
    def validate_image_size(size: ImageSize, provider: ImageProvider) -> bool:
        """Validate if a provider supports a specific image size"""
        provider_sizes = {
            ImageProvider.OPENAI_DALLE: {
                ImageSize.SQUARE_1024, ImageSize.PORTRAIT_512, ImageSize.LANDSCAPE_768
            },
            ImageProvider.STABILITY_AI: {
                ImageSize.SQUARE_512, ImageSize.SQUARE_1024, ImageSize.LANDSCAPE_768
            },
            ImageProvider.LOCAL_SD: {
                ImageSize.SQUARE_512, ImageSize.SQUARE_1024, ImageSize.PORTRAIT_512
            },
            ImageProvider.MOCK: set(ImageSize)  # Mock supports all sizes
        }
        
        return size in provider_sizes.get(provider, set())
    
    @staticmethod
    def validate_prompt_safety(prompt: str) -> Tuple[bool, List[str]]:
        """Check prompt for potentially unsafe content"""
        warnings = []
        
        # Keywords that might cause issues
        unsafe_keywords = [
            'nude', 'naked', 'nsfw', 'explicit', 'sexual', 'erotic',
            'violence', 'gore', 'blood', 'death', 'kill', 'murder',
            'copyright', 'trademark', 'brand name', 'celebrity'
        ]
        
        prompt_lower = prompt.lower()
        for keyword in unsafe_keywords:
            if keyword in prompt_lower:
                warnings.append(f"Prompt contains potentially unsafe keyword: '{keyword}'")
        
        # Check for very long prompts that might be problematic
        if len(prompt) > 1000:
            warnings.append("Very long prompt may cause generation issues")
        
        # Check for excessive special characters
        special_chars = sum(1 for c in prompt if not c.isalnum() and not c.isspace())
        if special_chars > len(prompt) * 0.3:
            warnings.append("Prompt contains many special characters")
        
        is_safe = len(warnings) == 0
        return is_safe, warnings
    
    @staticmethod
    def validate_storage_space(directory: str, required_mb: float = 50.0) -> Tuple[bool, Optional[str]]:
        """Check if there's enough storage space for image generation"""
        try:
            import shutil
            
            free_bytes = shutil.disk_usage(directory).free
            free_mb = free_bytes / (1024 * 1024)
            
            if free_mb < required_mb:
                return False, f"Insufficient storage space: {free_mb:.1f}MB available, {required_mb}MB required"
            
            return True, None
            
        except Exception as e:
            return False, f"Could not check storage space: {e}"
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize a filename for safe file system usage"""
        # Remove or replace problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Limit length
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:96] + ext
        
        # Ensure it's not empty
        if not filename:
            filename = "image"
        
        return filename
