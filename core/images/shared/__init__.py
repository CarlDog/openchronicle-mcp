"""
Shared Image System Components for OpenChronicle

This package contains shared data models, configuration management, and utilities
used across the image generation and processing systems.
"""

from .image_models import (
    ImageProvider,
    ImageSize,
    ImageType,
    ImageGenerationRequest,
    ImageGenerationResult,
    ImageMetadata,
    ImageStats,
    ImageConfig,
    NamingConfig,
    AutoGenerateConfig
)

from .config_manager import ImageConfigManager

from .validation_utils import (
    ImageValidator,
    ImageValidationError
)

__all__ = [
    # Data models and enums
    'ImageProvider',
    'ImageSize',
    'ImageType',
    'ImageGenerationRequest',
    'ImageGenerationResult',
    'ImageMetadata',
    'ImageStats',
    'ImageConfig',
    'NamingConfig',
    'AutoGenerateConfig',
    
    # Configuration management
    'ImageConfigManager',
    
    # Validation
    'ImageValidator',
    'ImageValidationError'
]
