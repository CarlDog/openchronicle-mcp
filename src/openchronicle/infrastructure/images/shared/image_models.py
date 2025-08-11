"""
Shared Image Data Models and Structures for OpenChronicle

Provides common data classes, enums, and types used across the image systems.
Consolidates shared functionality from image_generation_engine.py and image_adapter.py
"""

from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ImageProvider(Enum):
    """Supported image generation providers"""

    OPENAI_DALLE = "openai_dalle"
    STABILITY_AI = "stability_ai"
    LOCAL_SD = "local_sd"
    MOCK = "mock"


class ImageSize(Enum):
    """Standard image sizes for generation"""

    SQUARE_512 = "512x512"
    SQUARE_1024 = "1024x1024"
    PORTRAIT_512 = "512x768"
    LANDSCAPE_768 = "768x512"
    WIDE_1024 = "1024x512"


class ImageType(Enum):
    """Types of images for organization"""

    CHARACTER = "character"
    SCENE = "scene"
    LOCATION = "location"
    ITEM = "item"
    CUSTOM = "custom"


@dataclass
class ImageGenerationRequest:
    """Request for image generation"""

    prompt: str
    image_type: ImageType
    size: ImageSize = ImageSize.SQUARE_1024
    provider: ImageProvider | None = None
    style: str | None = None
    quality: str = "standard"
    negative_prompt: str | None = None

    # Story context
    story_id: str | None = None
    scene_id: str | None = None
    character_names: list[str] | None = None
    location: str | None = None

    def __post_init__(self):
        """Validate request parameters"""
        if not self.prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Auto-set provider if not specified
        if self.provider is None:
            if "character" in self.prompt.lower():
                self.provider = ImageProvider.OPENAI_DALLE
            else:
                self.provider = ImageProvider.MOCK

        # Add type-specific style suggestions
        if self.style is None:
            if self.image_type == ImageType.CHARACTER:
                self.style = "portrait, detailed character art"
            elif self.image_type == ImageType.SCENE:
                self.style = "cinematic scene, atmospheric"
            elif self.image_type == ImageType.LOCATION:
                self.style = "detailed environment, landscape"


@dataclass
class ImageGenerationResult:
    """Result from image generation"""

    success: bool
    image_path: str | None = None
    image_data: bytes | None = None
    provider: ImageProvider | None = None
    generation_time: float = 0.0
    cost: float = 0.0
    error_message: str | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)


@dataclass
class ImageMetadata:
    """Metadata for generated images"""

    image_id: str
    image_type: ImageType
    prompt: str
    provider: str
    size: str
    file_path: str
    created_at: str
    cost: float = 0.0
    generation_time: float = 0.0

    # Story context
    story_id: str | None = None
    scene_id: str | None = None
    character_names: list[str] | None = None
    location: str | None = None

    # Generation details
    style: str | None = None
    negative_prompt: str | None = None
    quality: str = "standard"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert enum to string for JSON serialization
        if isinstance(data["image_type"], ImageType):
            data["image_type"] = data["image_type"].value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImageMetadata":
        """Create ImageMetadata from dictionary"""
        # Convert string back to enum
        if isinstance(data.get("image_type"), str):
            data["image_type"] = ImageType(data["image_type"])
        return cls(**data)


@dataclass
class ImageStats:
    """Statistics for image generation tracking"""

    images_generated: int = 0
    total_cost: float = 0.0
    generation_time: float = 0.0
    providers_used: set = None

    def __post_init__(self):
        if self.providers_used is None:
            self.providers_used = set()

    def add_generation(self, result: ImageGenerationResult):
        """Add a generation result to statistics"""
        if result.success:
            self.images_generated += 1
            self.total_cost += result.cost or 0.0
            self.generation_time += result.generation_time or 0.0
            if result.provider:
                self.providers_used.add(result.provider.value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "images_generated": self.images_generated,
            "total_cost": self.total_cost,
            "generation_time": self.generation_time,
            "providers_used": list(self.providers_used),
            "avg_generation_time": self.generation_time / max(1, self.images_generated),
            "avg_cost_per_image": self.total_cost / max(1, self.images_generated),
        }


# Type aliases for convenience
ImageConfig = dict[str, Any]
NamingConfig = dict[str, str]
AutoGenerateConfig = dict[str, Any]
