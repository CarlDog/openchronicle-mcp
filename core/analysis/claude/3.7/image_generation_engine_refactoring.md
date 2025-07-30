# Image Generation Engine Refactoring Recommendation

## Current Module Overview

**File**: `core/image_generation_engine.py` (608 lines)  
**Purpose**: Manages image generation for characters, scenes, and locations in OpenChronicle narratives.

**Related File**: `core/image_adapter.py` (392 lines)  
**Purpose**: Provides a plugin system for integrating different image generation providers.

**Key Components**:
1. **ImageGenerationEngine Class** - Main class handling image generation functionality
2. **ImageMetadata Class** - Data container for image metadata
3. **Configuration Loading** - Functions to load and process configuration from the model registry
4. **Auto-generation Logic** - Functions to automatically generate images for characters and scenes
5. **Adapters System** - Provider-specific adapters in image_adapter.py
6. **Registry System** - Adapter registry and fallback management in image_adapter.py

**Current Responsibilities**:
- Loading model configuration from the registry
- Managing image files and directories
- Tracking image metadata
- Generating character portraits and scene images
- Providing image search and retrieval functionality
- Tracking statistics for image generation
- Managing adapters for different providers (in image_adapter.py)

## Issues Identified

1. **Configuration Duplication**: Registry loading and configuration parsing logic duplicated
2. **Mixed Responsibilities**: The engine handles both file management and generation logic
3. **Manual Image Path Management**: Hardcoded paths and manual directory management
4. **Adapter Registration**: Adapters need to be manually registered with explicit provider mapping
5. **Metadata Management**: Metadata handling intermixed with generation logic
6. **Error Handling**: Limited error handling with minimal recovery strategies
7. **Testing Challenges**: Testing requires complex mocking of filesystem and configuration
8. **Deep Dependencies**: The engine directly depends on image_adapter implementation details

## Refactoring Recommendations

### 1. Convert to Package Structure

Transform the two files into a structured package:

```
core/
  image/
    __init__.py                 # Public API
    engine.py                   # Main engine (simplified)
    metadata.py                 # Image metadata model
    providers/                  # Image providers
      __init__.py
      base.py
      openai.py
      stability.py
      local.py
      mock.py
    config/                     # Configuration
      __init__.py
      loader.py
      registry.py
    storage/                    # Storage management
      __init__.py
      file_manager.py
      metadata_store.py
    generation/                 # Generation logic
      __init__.py
      character_generator.py
      scene_generator.py
      prompt_builder.py
    utils/                      # Utilities
      __init__.py
      image_processing.py
      statistics.py
```

### 2. Implement Data Models

Create proper data models for requests, results, and metadata:

```python
# metadata.py
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pathlib import Path


class ImageType(Enum):
    """Types of images for organization"""
    CHARACTER = "character"
    SCENE = "scene"
    LOCATION = "location"
    ITEM = "item"
    CUSTOM = "custom"


class ImageSize(Enum):
    """Standard image sizes for generation"""
    SQUARE_512 = "512x512"
    SQUARE_1024 = "1024x1024"
    PORTRAIT_512 = "512x768"
    LANDSCAPE_768 = "768x512"
    WIDE_1024 = "1024x512"


@dataclass
class ImageMetadata:
    """Metadata for generated images"""
    image_id: str
    filename: str
    image_type: ImageType
    prompt: str
    character_name: Optional[str] = None
    scene_id: Optional[str] = None
    provider: str = "unknown"
    model: str = "unknown"
    size: str = "512x512"
    generation_time: float = 0.0
    cost: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            "image_id": self.image_id,
            "filename": self.filename,
            "image_type": self.image_type.value if isinstance(self.image_type, ImageType) else self.image_type,
            "prompt": self.prompt,
            "provider": self.provider,
            "model": self.model,
            "size": self.size,
            "generation_time": self.generation_time,
            "cost": self.cost,
            "timestamp": self.timestamp,
            "tags": self.tags
        }
        
        if self.character_name:
            data["character_name"] = self.character_name
        if self.scene_id:
            data["scene_id"] = self.scene_id
            
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageMetadata':
        """Create ImageMetadata from dictionary"""
        image_type = data.get("image_type")
        if isinstance(image_type, str):
            image_type = ImageType(image_type)
            
        return cls(
            image_id=data["image_id"],
            filename=data["filename"],
            image_type=image_type,
            prompt=data["prompt"],
            character_name=data.get("character_name"),
            scene_id=data.get("scene_id"),
            provider=data.get("provider", "unknown"),
            model=data.get("model", "unknown"),
            size=data.get("size", "512x512"),
            generation_time=data.get("generation_time", 0.0),
            cost=data.get("cost", 0.0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            tags=data.get("tags", [])
        )


@dataclass
class ImageGenerationRequest:
    """Request for image generation"""
    prompt: str
    image_type: ImageType
    size: ImageSize = ImageSize.SQUARE_512
    character_name: Optional[str] = None
    scene_id: Optional[str] = None
    style_modifiers: List[str] = field(default_factory=list)
    negative_prompt: Optional[str] = None
    seed: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = {
            "prompt": self.prompt,
            "image_type": self.image_type.value,
            "size": self.size.value,
            "style_modifiers": self.style_modifiers
        }
        
        if self.character_name:
            data["character_name"] = self.character_name
        if self.scene_id:
            data["scene_id"] = self.scene_id
        if self.negative_prompt:
            data["negative_prompt"] = self.negative_prompt
        if self.seed is not None:
            data["seed"] = self.seed
            
        return data
```

### 3. Implement Provider Strategy Pattern

Create a provider strategy pattern for image generation:

```python
# providers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ...metadata import ImageGenerationRequest, ImageGenerationResult


class ImageProvider(ABC):
    """Base class for image generation providers"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize provider with configuration"""
        self.config = config
        self.enabled = config.get("enabled", True)
        self.name = "base"
    
    @abstractmethod
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate an image from the request"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured"""
        pass
    
    def get_provider_name(self) -> str:
        """Get human-readable provider name"""
        return self.name
    
    def supports_size(self, size: str) -> bool:
        """Check if provider supports the requested size"""
        # Default implementation supports all sizes
        return True


# providers/openai.py
import os
import time
import httpx
from typing import Dict, Any, Optional
from .base import ImageProvider
from ...metadata import ImageGenerationRequest, ImageGenerationResult, ImageSize


class OpenAIProvider(ImageProvider):
    """Provider for OpenAI DALL-E image generation"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "openai_dalle"
        self.api_key = config.get("api_key", os.getenv("OPENAI_API_KEY"))
        self.model = config.get("model", "dall-e-3")
        self.quality = config.get("quality", "standard")
    
    def is_available(self) -> bool:
        """Check if OpenAI API key is configured"""
        return bool(self.api_key and self.enabled)
    
    def supports_size(self, size: ImageSize) -> bool:
        """DALL-E 3 supports specific sizes"""
        if self.model == "dall-e-3":
            return size in [ImageSize.SQUARE_1024, ImageSize.PORTRAIT_512, ImageSize.LANDSCAPE_768]
        return size in [ImageSize.SQUARE_512, ImageSize.SQUARE_1024]
    
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        """Generate image using OpenAI DALL-E"""
        # Implementation...


# providers/__init__.py
from typing import Dict, Type, Optional
from .base import ImageProvider
from .openai import OpenAIProvider
from .stability import StabilityProvider
from .local import LocalProvider
from .mock import MockProvider


PROVIDER_REGISTRY: Dict[str, Type[ImageProvider]] = {
    "openai_dalle": OpenAIProvider,
    "stability_ai": StabilityProvider,
    "local_sd": LocalProvider,
    "mock": MockProvider
}


def get_provider(name: str, config: Dict[str, Any]) -> Optional[ImageProvider]:
    """Get provider instance by name"""
    provider_class = PROVIDER_REGISTRY.get(name)
    if not provider_class:
        return None
    
    return provider_class(config)


def get_provider_names() -> list[str]:
    """Get all registered provider names"""
    return list(PROVIDER_REGISTRY.keys())
```

### 4. Create Storage Manager

Implement a dedicated storage manager:

```python
# storage/file_manager.py
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from ...metadata import ImageType, ImageMetadata


class ImageFileManager:
    """Manages image files and directories"""
    
    def __init__(self, story_path: str):
        """Initialize with story path"""
        self.story_path = Path(story_path)
        self.images_path = self.story_path / "images"
        self.ensure_directories()
    
    def ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        self.images_path.mkdir(exist_ok=True)
        # Create subdirectories for organization
        for img_type in ImageType:
            (self.images_path / img_type.value).mkdir(exist_ok=True)
    
    def get_image_path(self, metadata: ImageMetadata) -> Path:
        """Get path for image based on metadata"""
        return self.images_path / metadata.filename
    
    def generate_filename(self, image_type: ImageType, name: Optional[str] = None,
                         scene_id: Optional[str] = None, extension: str = "png") -> str:
        """Generate filename for image based on type and context"""
        prefix_map = {
            ImageType.CHARACTER: "char",
            ImageType.SCENE: "scene",
            ImageType.LOCATION: "loc",
            ImageType.ITEM: "item",
            ImageType.CUSTOM: "img"
        }
        
        prefix = prefix_map.get(image_type, "img")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if image_type == ImageType.CHARACTER and name:
            # char-aletha-20250718_143022.png
            safe_name = "".join(c for c in name.lower() if c.isalnum() or c in '-_')
            return f"{prefix}-{safe_name}-{timestamp}.{extension}"
            
        elif image_type == ImageType.SCENE and scene_id:
            # scene-000123-20250718_143022.png
            return f"{prefix}-{scene_id}-{timestamp}.{extension}"
            
        else:
            # Generic naming
            return f"{prefix}-{timestamp}.{extension}"
    
    def save_image_data(self, data: bytes, filename: str) -> bool:
        """Save image data to file"""
        try:
            with open(self.images_path / filename, 'wb') as f:
                f.write(data)
            return True
        except Exception:
            return False
    
    def delete_image(self, filename: str) -> bool:
        """Delete image file"""
        try:
            image_path = self.images_path / filename
            if image_path.exists():
                image_path.unlink()
            return True
        except Exception:
            return False


# storage/metadata_store.py
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
from ...metadata import ImageMetadata, ImageType

logger = logging.getLogger(__name__)


class MetadataStore:
    """Manages image metadata storage"""
    
    def __init__(self, story_path: str):
        """Initialize metadata store"""
        self.story_path = Path(story_path)
        self.images_path = self.story_path / "images"
        self.metadata_file = self.images_path / "images.json"
        self.metadata: Dict[str, ImageMetadata] = {}
        self.load()
    
    def load(self) -> None:
        """Load metadata from file"""
        if not self.metadata_file.exists():
            return
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for image_id, meta_dict in data.items():
                self.metadata[image_id] = ImageMetadata.from_dict(meta_dict)
                
            logger.info(f"Loaded metadata for {len(self.metadata)} images")
            
        except Exception as e:
            logger.error(f"Failed to load image metadata: {e}")
    
    def save(self) -> None:
        """Save metadata to file"""
        try:
            data = {
                image_id: meta.to_dict() 
                for image_id, meta in self.metadata.items()
            }
            
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"Failed to save image metadata: {e}")
    
    def add(self, metadata: ImageMetadata) -> None:
        """Add metadata for an image"""
        self.metadata[metadata.image_id] = metadata
        self.save()
    
    def get(self, image_id: str) -> Optional[ImageMetadata]:
        """Get metadata for an image"""
        return self.metadata.get(image_id)
    
    def delete(self, image_id: str) -> bool:
        """Delete metadata for an image"""
        if image_id in self.metadata:
            del self.metadata[image_id]
            self.save()
            return True
        return False
    
    def get_by_character(self, character_name: str) -> List[ImageMetadata]:
        """Get all images for a specific character"""
        return [
            meta for meta in self.metadata.values()
            if meta.character_name and meta.character_name.lower() == character_name.lower()
        ]
    
    def get_by_scene(self, scene_id: str) -> List[ImageMetadata]:
        """Get all images for a specific scene"""
        return [
            meta for meta in self.metadata.values()
            if meta.scene_id == scene_id
        ]
    
    def get_by_tag(self, tag: str) -> List[ImageMetadata]:
        """Get all images with a specific tag"""
        return [
            meta for meta in self.metadata.values()
            if tag.lower() in [t.lower() for t in meta.tags]
        ]
    
    def get_by_type(self, image_type: ImageType) -> List[ImageMetadata]:
        """Get all images of a specific type"""
        return [
            meta for meta in self.metadata.values()
            if meta.image_type == image_type or 
               (isinstance(meta.image_type, str) and meta.image_type == image_type.value)
        ]
```

### 5. Create Configuration Management

Implement dedicated configuration management:

```python
# config/loader.py
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Loads and processes image generation configuration"""
    
    @staticmethod
    def load_model_registry() -> Dict[str, Any]:
        """Load the model registry configuration."""
        config_path = Path(__file__).parents[3] / "config" / "model_registry.json"
        
        if not config_path.exists():
            logger.warning("No model registry found - defaulting to mock image adapter!")
            return {"default_image_model": "mock", "image_fallback_chain": ["mock"]}
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading model registry: {e}")
            return {"default_image_model": "mock", "image_fallback_chain": ["mock"]}
    
    @staticmethod
    def get_image_config(story_path: Optional[str] = None) -> Dict[str, Any]:
        """Get image configuration from the model registry."""
        registry = ConfigLoader.load_model_registry()
        
        # Extract image models from registry
        image_models = ConfigLoader._extract_image_models(registry)
        
        # Get fallback chain
        fallback_chain = registry.get("fallback_chains", {}).get(
            "primary_image", ["mock"])
        
        # Get default image model
        default_image_model = registry.get("defaults", {}).get(
            "image_model", "mock")
        
        # Build provider configuration
        providers = ConfigLoader._build_provider_config(
            fallback_chain, image_models)
        
        return {
            "enabled": True,
            "providers": providers,
            "auto_generate": {
                "character_portraits": True,
                "scene_images": True,
                "scene_triggers": ["major_event", "new_location"]
            },
            "fallback_chain": fallback_chain,
            "default_model": default_image_model
        }
    
    @staticmethod
    def _extract_image_models(registry: Dict[str, Any]) -> Dict[str, Any]:
        """Extract image models from registry"""
        image_model_data = registry.get("image_models", {})
        image_models = {}
        
        # Collect image models from all priority groups
        all_image_models = []
        for priority_group in ["primary", "testing"]:
            if priority_group in image_model_data:
                all_image_models.extend(image_model_data[priority_group])
        
        # Build image models dict
        for model in all_image_models:
            model_name = model["name"]
            image_models[model_name] = model
        
        return image_models
    
    @staticmethod
    def _build_provider_config(fallback_chain: List[str], 
                             image_models: Dict[str, Any]) -> Dict[str, Any]:
        """Build provider configuration"""
        providers = {}
        
        for model_name in fallback_chain:
            if model_name == "openai_dalle":
                providers["openai_dalle"] = {"enabled": True}
            elif model_name == "stability_ai":
                providers["stability_ai"] = {"enabled": True}
            elif model_name == "mock":
                providers["mock"] = {"enabled": True}
            else:
                # Handle other image models by mapping provider names
                model_info = image_models.get(model_name, {})
                provider = model_info.get("provider", model_name)
                providers[provider] = {"enabled": True}
        
        # Always ensure mock is available as fallback
        if "mock" not in providers:
            providers["mock"] = {"enabled": True}
        
        return providers


# config/registry.py
from typing import Dict, List, Any, Optional
from ..providers import get_provider, get_provider_names
from .loader import ConfigLoader
from ...metadata import ImageGenerationRequest, ImageGenerationResult


class ProviderRegistry:
    """Registry for managing image generation providers"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize provider registry"""
        self.config = config
        self.providers = {}
        self.fallback_chain = config.get("fallback_chain", ["mock"])
        
        # Initialize providers
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize all configured providers"""
        provider_configs = self.config.get("providers", {})
        
        for provider_name, provider_config in provider_configs.items():
            if provider_config.get("enabled", True):
                provider = get_provider(provider_name, provider_config)
                if provider:
                    self.providers[provider_name] = provider
    
    def get_provider(self, name: str) -> Optional[Any]:
        """Get provider by name"""
        return self.providers.get(name)
    
    def get_available_providers(self) -> List[Any]:
        """Get all available providers"""
        return [
            provider for provider in self.providers.values()
            if provider.is_available()
        ]
    
    def get_best_provider(self, request: ImageGenerationRequest) -> Optional[Any]:
        """Get best provider for request"""
        for provider_name in self.fallback_chain:
            provider = self.providers.get(provider_name)
            if provider and provider.is_available() and provider.supports_size(request.size):
                return provider
        return None
    
    async def generate_image(self, request: ImageGenerationRequest, 
                           preferred_provider: Optional[str] = None) -> ImageGenerationResult:
        """Generate image with fallback"""
        # Try preferred provider first
        if preferred_provider:
            provider = self.get_provider(preferred_provider)
            if provider and provider.is_available() and provider.supports_size(request.size):
                result = await provider.generate_image(request)
                if result.success:
                    return result
        
        # Try fallback chain
        provider = self.get_best_provider(request)
        if provider:
            return await provider.generate_image(request)
        
        return ImageGenerationResult(
            success=False,
            error_message="No available image generation providers"
        )
```

### 6. Create Specialized Generators

Implement specialized generators for different image types:

```python
# generation/character_generator.py
from typing import Dict, Any, Optional
from ...metadata import ImageGenerationRequest, ImageType, ImageSize


class CharacterPortraitGenerator:
    """Specialized generator for character portraits"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration"""
        self.config = config
    
    def build_request(self, character_name: str, 
                     character_data: Dict[str, Any],
                     size: ImageSize = ImageSize.PORTRAIT_512) -> ImageGenerationRequest:
        """Build generation request from character data"""
        # Build prompt from character data
        prompt_parts = []
        
        # Basic description
        if "description" in character_data:
            prompt_parts.append(character_data["description"])
            
        # Physical traits
        if "appearance" in character_data:
            appearance = character_data["appearance"]
            if isinstance(appearance, dict):
                for key, value in appearance.items():
                    if value:
                        prompt_parts.append(f"{key}: {value}")
            else:
                prompt_parts.append(str(appearance))
                
        # Personality influences on appearance
        if "personality" in character_data:
            personality = character_data.get("personality", {})
            if "demeanor" in personality:
                prompt_parts.append(f"demeanor: {personality['demeanor']}")
                
        prompt = ", ".join(prompt_parts) if prompt_parts else f"Portrait of {character_name}"
        
        # Character-specific style modifiers
        style_modifiers = [
            "character portrait",
            "detailed face",
            "high quality",
            "fantasy art"
        ]
        
        # Add clothing/style if available
        if "equipment" in character_data or "clothing" in character_data:
            style_modifiers.append("detailed clothing")
        
        return ImageGenerationRequest(
            prompt=prompt,
            image_type=ImageType.CHARACTER,
            character_name=character_name,
            size=size,
            style_modifiers=style_modifiers
        )


# generation/scene_generator.py
from typing import Dict, Any, Optional
from ...metadata import ImageGenerationRequest, ImageType, ImageSize


class SceneImageGenerator:
    """Specialized generator for scene images"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with configuration"""
        self.config = config
    
    def build_request(self, scene_id: str, 
                    scene_data: Dict[str, Any],
                    context: Optional[Dict[str, Any]] = None,
                    size: ImageSize = ImageSize.LANDSCAPE_768) -> ImageGenerationRequest:
        """Build generation request from scene data"""
        # Build prompt from scene data
        prompt_parts = []
        
        # Scene description
        if "description" in scene_data:
            prompt_parts.append(scene_data["description"])
            
        # Location/setting
        if "location" in scene_data:
            prompt_parts.append(f"Setting: {scene_data['location']}")
            
        # Time of day/mood
        if "atmosphere" in scene_data:
            prompt_parts.append(scene_data["atmosphere"])
            
        # Add context from memory or previous scenes
        if context and "recent_events" in context:
            prompt_parts.append(f"Context: {context['recent_events']}")
            
        prompt = ", ".join(prompt_parts) if prompt_parts else f"Scene {scene_id}"
        
        style_modifiers = [
            "detailed environment",
            "atmospheric",
            "cinematic composition",
            "fantasy setting"
        ]
        
        return ImageGenerationRequest(
            prompt=prompt,
            image_type=ImageType.SCENE,
            scene_id=scene_id,
            size=size,
            style_modifiers=style_modifiers
        )
    
    def should_generate(self, scene_data: Dict[str, Any]) -> bool:
        """Determine if scene should trigger image generation"""
        # Get trigger configuration
        triggers = self.config.get("auto_generate", {}).get(
            "scene_triggers", ["major_event", "new_location"])
        
        if "major_event" in triggers and scene_data.get("importance", "normal") == "high":
            return True
        
        if "new_location" in triggers and scene_data.get("new_location", False):
            return True
        
        return False
```

### 7. Refine Main Engine Class

Simplify the main engine to use the specialized components:

```python
# engine.py
from pathlib import Path
import time
import logging
import httpx
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import uuid

from .metadata import ImageMetadata, ImageGenerationRequest, ImageGenerationResult
from .metadata import ImageType, ImageSize
from .storage.file_manager import ImageFileManager
from .storage.metadata_store import MetadataStore
from .config.registry import ProviderRegistry
from .config.loader import ConfigLoader
from .generation.character_generator import CharacterPortraitGenerator
from .generation.scene_generator import SceneImageGenerator

logger = logging.getLogger(__name__)


class ImageGenerationEngine:
    """Main engine for managing image generation in stories"""
    
    def __init__(self, story_path: str, config: Optional[Dict[str, Any]] = None):
        """Initialize image generation engine"""
        self.story_path = Path(story_path)
        
        # Load configuration
        self.config = config or ConfigLoader.get_image_config(story_path)
        
        # Initialize components
        self.file_manager = ImageFileManager(story_path)
        self.metadata_store = MetadataStore(story_path)
        self.registry = ProviderRegistry(self.config)
        
        # Initialize generators
        self.character_generator = CharacterPortraitGenerator(self.config)
        self.scene_generator = SceneImageGenerator(self.config)
        
        # Initialize statistics
        self.stats = {
            "images_generated": 0,
            "total_cost": 0.0,
            "generation_time": 0.0,
            "providers_used": set()
        }
    
    async def generate_image(self, request: ImageGenerationRequest,
                          preferred_provider: Optional[str] = None,
                          tags: Optional[List[str]] = None) -> Optional[str]:
        """Generate an image and save it to the story's images directory"""
        if tags is None:
            tags = []
        
        logger.info(f"Generating {request.image_type.value} image: {request.prompt[:50]}...")
        
        try:
            # Generate image
            result = await self.registry.generate_image(request, preferred_provider)
            
            if not result.success:
                logger.error(f"Image generation failed: {result.error_message}")
                return None
            
            # Generate ID and filename
            image_id = self._generate_image_id(request.image_type, request.character_name)
            filename = self.file_manager.generate_filename(
                request.image_type, request.character_name, request.scene_id)
            
            # Download and save image
            if result.image_url:
                image_data = await self._download_image(result.image_url)
                if not image_data or not self.file_manager.save_image_data(image_data, filename):
                    logger.error("Failed to save image data")
                    return None
            
            # Create metadata
            metadata = ImageMetadata(
                image_id=image_id,
                filename=filename,
                image_type=request.image_type,
                prompt=request.prompt,
                character_name=request.character_name,
                scene_id=request.scene_id,
                provider=result.metadata.get("provider", "unknown") if result.metadata else "unknown",
                model=result.metadata.get("model", "unknown") if result.metadata else "unknown",
                size=request.size.value,
                generation_time=result.generation_time or 0.0,
                cost=result.cost or 0.0,
                timestamp=datetime.now().isoformat(),
                tags=tags
            )
            
            # Save metadata
            self.metadata_store.add(metadata)
            
            # Update statistics
            self.stats["images_generated"] += 1
            self.stats["total_cost"] += metadata.cost
            self.stats["generation_time"] += metadata.generation_time
            self.stats["providers_used"].add(metadata.provider)
            
            logger.info(f"Generated image {image_id}: {filename}")
            return image_id
            
        except Exception as e:
            logger.error(f"Failed to generate image: {e}")
            return None
    
    async def _download_image(self, image_url: str) -> Optional[bytes]:
        """Download image from URL or decode base64"""
        try:
            if image_url.startswith("data:"):
                # Handle base64 data URLs
                import base64
                header, data = image_url.split(",", 1)
                return base64.b64decode(data)
            else:
                # Download from URL
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url)
                    response.raise_for_status()
                    return response.content
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return None
    
    def _generate_image_id(self, image_type: ImageType, name: Optional[str] = None) -> str:
        """Generate unique image ID"""
        base = f"{image_type.value}"
        if name:
            base += f"_{name}"
        timestamp = int(time.time() * 1000)
        return f"{base}_{timestamp}"
    
    async def generate_character_portrait(self, character_name: str, 
                                       character_data: Dict[str, Any],
                                       size: ImageSize = ImageSize.PORTRAIT_512) -> Optional[str]:
        """Generate a character portrait from character data"""
        request = self.character_generator.build_request(
            character_name, character_data, size)
        
        tags = ["character", "portrait", character_name.lower()]
        return await self.generate_image(request, tags=tags)
    
    async def generate_scene_image(self, scene_id: str, 
                                scene_data: Dict[str, Any],
                                context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Generate an image for a scene"""
        request = self.scene_generator.build_request(
            scene_id, scene_data, context)
        
        tags = ["scene", f"scene_{scene_id}"]
        return await self.generate_image(request, tags=tags)
    
    # Other methods for image management, search, and retrieval...


# Factory function for integration with main system
def create_image_engine(story_id: str, config: Optional[Dict[str, Any]] = None) -> ImageGenerationEngine:
    """Create and configure an image generation engine for a story"""
    try:
        # Convert story_id to story path
        story_path = f"storage/temp/test_data/{story_id}"
        
        # Load configuration if not provided
        if not config:
            config = ConfigLoader.get_image_config(story_path)
        
        # Create engine
        return ImageGenerationEngine(story_path, config)
        
    except Exception as e:
        logger.error(f"Error creating image engine: {e}")
        # Fallback to basic configuration
        fallback_config = {
            "enabled": True,
            "providers": {
                "mock": {
                    "enabled": True
                }
            },
            "fallback_chain": ["mock"]
        }
        story_path = f"storage/temp/test_data/{story_id}"
        return ImageGenerationEngine(story_path, fallback_config)
```

## Implementation Strategy

1. **Create Package Structure**: Set up the directory structure for the refactored modules
2. **Implement Models**: Create data models for metadata, requests, and results
3. **Implement Provider System**: Refactor the adapter system into a provider strategy pattern
4. **Create Storage Components**: Implement file manager and metadata store
5. **Implement Configuration**: Create configuration management components
6. **Implement Generators**: Create specialized generators for different image types
7. **Refine Main Engine**: Update the main engine to use the specialized components

## Benefits of Refactoring

1. **Improved Organization**: Clear separation of concerns with specialized components
2. **Enhanced Testability**: Components can be tested in isolation with proper mocking
3. **Better Error Handling**: More robust error handling throughout the system
4. **Configuration Management**: Centralized configuration loading and processing
5. **Extensibility**: Easy to add new providers, image types, or generation strategies
6. **Maintainability**: Smaller, focused components with clear responsibilities
7. **Type Safety**: Comprehensive type annotations throughout the codebase

## Migration Plan

1. **Incremental Refactoring**: Create the new package structure alongside the existing files
2. **Component-by-Component Migration**: Implement and test each component independently
3. **Integration Testing**: Test the full system with the new components
4. **Backward Compatibility**: Provide adapters for existing code during transition
5. **Final Cleanup**: Remove the original files once migration is complete

By following this refactoring plan, the image generation system will be transformed into a well-structured, maintainable package that adheres to modern Python best practices and provides a solid foundation for future enhancements.
