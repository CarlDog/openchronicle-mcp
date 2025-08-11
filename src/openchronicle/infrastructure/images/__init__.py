"""
Image Systems - Modular image generation and processing

Provides unified image generation, processing, and storage capabilities:
- Shared: Common data structures and utilities for image systems
- Processing: Image processing, storage, and format conversion
- Generation: Core generation logic and orchestration
- ImageOrchestrator: Unified API for all image system operations
"""

# Main orchestrator
# Generation components
from .generation.generation_engine import GenerationEngine
from .generation.prompt_processor import PromptProcessor
from .generation.style_manager import StyleManager
from .image_orchestrator import ImageOrchestrator
from .image_orchestrator import auto_generate_character_portrait
from .image_orchestrator import auto_generate_scene_image
from .image_orchestrator import create_image_engine
from .processing.format_converter import ImageFormatConverter

# Processing components
from .processing.image_adapter import ImageAdapterRegistry
from .processing.image_adapter import create_image_registry
from .processing.storage_manager import ImageStorageManager
from .shared.config_manager import ImageConfigManager
from .shared.image_models import ImageGenerationRequest
from .shared.image_models import ImageGenerationResult
from .shared.image_models import ImageMetadata

# Shared components
from .shared.image_models import ImageProvider
from .shared.image_models import ImageSize
from .shared.image_models import ImageType
from .shared.validation_utils import ImageValidator


__all__ = [
    # Main orchestrator and integration functions
    "ImageOrchestrator",
    "create_image_engine",
    "auto_generate_character_portrait",
    "auto_generate_scene_image",
    # Shared models and utilities
    "ImageProvider",
    "ImageSize",
    "ImageType",
    "ImageGenerationRequest",
    "ImageGenerationResult",
    "ImageMetadata",
    "ImageConfigManager",
    "ImageValidator",
    # Processing components
    "ImageAdapterRegistry",
    "create_image_registry",
    "ImageStorageManager",
    "ImageFormatConverter",
    # Generation components
    "GenerationEngine",
    "PromptProcessor",
    "StyleManager",
]
