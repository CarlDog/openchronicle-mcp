"""
Image Processing Components for OpenChronicle

This package contains components for image processing, storage, and format conversion.
Extracted and modularized from core/image_adapter.py and related functionality.
"""

from .format_converter import ImageFormat
from .format_converter import ImageFormatConverter
from .format_converter import ImageQuality
from .image_adapter import ImageAdapter
from .image_adapter import ImageAdapterRegistry
from .image_adapter import MockImageAdapter
from .image_adapter import OpenAIImageAdapter
from .image_adapter import StabilityImageAdapter
from .image_adapter import create_image_registry
from .storage_manager import ImageStorageManager


__all__ = [
    # Adapters
    "ImageAdapter",
    "OpenAIImageAdapter",
    "StabilityImageAdapter",
    "MockImageAdapter",
    "ImageAdapterRegistry",
    "create_image_registry",
    # Storage
    "ImageStorageManager",
    # Format conversion
    "ImageFormatConverter",
    "ImageFormat",
    "ImageQuality",
]
