"""
Image Processing Adapter for OpenChronicle

Provides unified interface for multiple image generation providers.
Extracted and modularized from core/image_adapter.py
"""

import asyncio
import base64
import io
import logging
import os
import time
from abc import ABC
from abc import abstractmethod
from typing import Any

import httpx
from PIL import Image

from ..shared.image_models import ImageGenerationRequest
from ..shared.image_models import ImageGenerationResult
from ..shared.image_models import ImageProvider
from ..shared.image_models import ImageSize
from ..shared.validation_utils import ImageValidator


logger = logging.getLogger(__name__)


class ImageAdapter(ABC):
    """Abstract base class for image generation adapters"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.provider = ImageProvider(config.get("provider", "mock"))
        self.enabled = config.get("enabled", True)

    @abstractmethod
    async def generate_image(
        self, request: ImageGenerationRequest
    ) -> ImageGenerationResult:
        """Generate an image from the request"""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the adapter is available and configured"""

    def get_provider_name(self) -> str:
        """Get human-readable provider name"""
        return self.provider.value

    def supports_size(self, size: ImageSize) -> bool:
        """Check if adapter supports the requested size"""
        # Default implementation supports all sizes
        return True


class OpenAIImageAdapter(ImageAdapter):
    """Adapter for OpenAI DALL-E image generation"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", os.getenv("OPENAI_API_KEY"))
        self.model = config.get("model", "dall-e-3")
        self.quality = config.get("quality", "standard")
        self.timeout = config.get("timeout", 60)
        self.max_retries = config.get("max_retries", 3)

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured"""
        return bool(self.api_key and self.enabled)

    def supports_size(self, size: ImageSize) -> bool:
        """DALL-E 3 supports specific sizes"""
        if self.model == "dall-e-3":
            return size in [
                ImageSize.SQUARE_1024,
                ImageSize.PORTRAIT_512,
                ImageSize.LANDSCAPE_768,
            ]
        return size in [ImageSize.SQUARE_512, ImageSize.SQUARE_1024]

    async def generate_image(
        self, request: ImageGenerationRequest
    ) -> ImageGenerationResult:
        """Generate image using OpenAI DALL-E"""
        start_time = time.time()

        if not self.is_available():
            return ImageGenerationResult(
                success=False, error_message="OpenAI API key not configured"
            )

        if not self.supports_size(request.size):
            return ImageGenerationResult(
                success=False,
                error_message=f"Size {request.size.value} not supported by {self.model}",
            )

        # Validate request
        validation_issues = ImageValidator.validate_request(request)
        if validation_issues:
            return ImageGenerationResult(
                success=False,
                error_message=f"Invalid request: {'; '.join(validation_issues)}",
            )

        try:
            import openai

            client = openai.AsyncOpenAI(api_key=self.api_key)

            response = await client.images.generate(
                model=self.model,
                prompt=request.prompt,
                size=request.size.value,
                quality=self.quality,
                n=1,
            )

            # Download the image
            image_url = response.data[0].url
            async with httpx.AsyncClient(timeout=self.timeout) as http_client:
                image_response = await http_client.get(image_url)
                image_response.raise_for_status()
                image_data = image_response.content

            generation_time = time.time() - start_time

            # Estimate cost (rough estimates for DALL-E 3)
            cost_map = {"1024x1024": 0.040, "512x768": 0.040, "768x512": 0.040}
            estimated_cost = cost_map.get(request.size.value, 0.040)

            return ImageGenerationResult(
                success=True,
                image_data=image_data,
                provider=self.provider,
                generation_time=generation_time,
                cost=estimated_cost,
                metadata={
                    "model": self.model,
                    "quality": self.quality,
                    "revised_prompt": (
                        response.data[0].revised_prompt
                        if hasattr(response.data[0], "revised_prompt")
                        else None
                    ),
                },
            )

        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(f"OpenAI image generation failed: {e}")
            return ImageGenerationResult(
                success=False, error_message=str(e), generation_time=generation_time
            )


class StabilityImageAdapter(ImageAdapter):
    """Adapter for Stability AI image generation"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key", os.getenv("STABILITY_API_KEY"))
        self.model = config.get("model", "stable-diffusion-xl-1024-v1-0")
        self.timeout = config.get("timeout", 120)
        self.max_retries = config.get("max_retries", 3)

    def is_available(self) -> bool:
        """Check if Stability API key is configured"""
        return bool(self.api_key and self.enabled)

    def supports_size(self, size: ImageSize) -> bool:
        """Stability AI supports most standard sizes"""
        return size in [
            ImageSize.SQUARE_512,
            ImageSize.SQUARE_1024,
            ImageSize.LANDSCAPE_768,
        ]

    async def generate_image(
        self, request: ImageGenerationRequest
    ) -> ImageGenerationResult:
        """Generate image using Stability AI"""
        start_time = time.time()

        if not self.is_available():
            return ImageGenerationResult(
                success=False, error_message="Stability API key not configured"
            )

        if not self.supports_size(request.size):
            return ImageGenerationResult(
                success=False,
                error_message=f"Size {request.size.value} not supported by Stability AI",
            )

        try:
            # Parse dimensions
            width, height = map(int, request.size.value.split("x"))

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "text_prompts": [{"text": request.prompt}],
                "cfg_scale": 7,
                "height": height,
                "width": width,
                "samples": 1,
                "steps": 30,
            }

            if request.negative_prompt:
                payload["text_prompts"].append(
                    {"text": request.negative_prompt, "weight": -1}
                )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"https://api.stability.ai/v1/generation/{self.model}/text-to-image",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()

                data = response.json()
                image_data = base64.b64decode(data["artifacts"][0]["base64"])

            generation_time = time.time() - start_time

            # Rough cost estimate for Stability AI
            estimated_cost = 0.02  # Approximate cost per generation

            return ImageGenerationResult(
                success=True,
                image_data=image_data,
                provider=self.provider,
                generation_time=generation_time,
                cost=estimated_cost,
                metadata={"model": self.model, "cfg_scale": 7, "steps": 30},
            )

        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(f"Stability AI image generation failed: {e}")
            return ImageGenerationResult(
                success=False, error_message=str(e), generation_time=generation_time
            )


class MockImageAdapter(ImageAdapter):
    """Mock adapter for testing and fallback"""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.delay = config.get("delay", 1.0)  # Simulate generation time

    def is_available(self) -> bool:
        """Mock adapter is always available"""
        return True

    def supports_size(self, size: ImageSize) -> bool:
        """Mock adapter supports all sizes"""
        return True

    async def generate_image(
        self, request: ImageGenerationRequest
    ) -> ImageGenerationResult:
        """Generate a placeholder image"""
        start_time = time.time()

        # Simulate generation delay
        await asyncio.sleep(self.delay)

        try:
            # Parse dimensions
            width, height = map(int, request.size.value.split("x"))

            # Create a simple placeholder image
            image = Image.new("RGB", (width, height), color="lightgray")

            # Add some text to the image
            try:
                from PIL import ImageDraw
                from PIL import ImageFont

                draw = ImageDraw.Draw(image)

                # Try to use a nice font, fall back to default
                try:
                    font = ImageFont.truetype("arial.ttf", 20)
                except:
                    font = ImageFont.load_default()

                # Add text
                text_lines = [
                    "PLACEHOLDER IMAGE",
                    f"{width}x{height}",
                    f"Type: {request.image_type.value}",
                    "Generated by Mock Adapter",
                ]

                y_offset = height // 2 - (len(text_lines) * 25) // 2
                for line in text_lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                    x = (width - text_width) // 2
                    draw.text((x, y_offset), line, fill="black", font=font)
                    y_offset += 30

            except ImportError:
                # PIL ImageDraw not available, just use solid color
                pass

            # Convert to bytes
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            image_data = buffer.getvalue()

            generation_time = time.time() - start_time

            return ImageGenerationResult(
                success=True,
                image_data=image_data,
                provider=self.provider,
                generation_time=generation_time,
                cost=0.0,  # Mock is free
                metadata={"type": "placeholder", "dimensions": f"{width}x{height}"},
            )

        except Exception as e:
            generation_time = time.time() - start_time
            logger.error(f"Mock image generation failed: {e}")
            return ImageGenerationResult(
                success=False, error_message=str(e), generation_time=generation_time
            )


class ImageAdapterRegistry:
    """Registry for managing image adapters"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.adapters: dict[str, ImageAdapter] = {}
        self._initialize_adapters()

    def _initialize_adapters(self):
        """Initialize adapters based on configuration"""
        adapter_configs = self.config.get("adapters", {})

        for adapter_name, adapter_config in adapter_configs.items():
            if not adapter_config.get("enabled", False):
                continue

            adapter_class_name = adapter_config.get("class")

            try:
                if adapter_class_name == "OpenAIImageAdapter":
                    self.adapters[adapter_name] = OpenAIImageAdapter(adapter_config)
                elif adapter_class_name == "StabilityImageAdapter":
                    self.adapters[adapter_name] = StabilityImageAdapter(adapter_config)
                elif adapter_class_name == "MockImageAdapter":
                    self.adapters[adapter_name] = MockImageAdapter(adapter_config)
                else:
                    logger.warning(f"Unknown adapter class: {adapter_class_name}")

            except Exception as e:
                logger.error(f"Failed to initialize adapter {adapter_name}: {e}")

    def get_adapter(
        self, provider: ImageProvider | None = None
    ) -> ImageAdapter | None:
        """Get an adapter for the specified provider"""
        if provider:
            # Look for specific provider
            provider_name = provider.value.replace(
                "_", ""
            )  # openai_dalle -> openaidalle
            for name, adapter in self.adapters.items():
                if provider_name in name.lower() and adapter.is_available():
                    return adapter

        # Fall back to first available adapter
        for adapter in self.adapters.values():
            if adapter.is_available():
                return adapter

        return None

    def list_available_adapters(self) -> list[str]:
        """List names of available adapters"""
        return [
            name for name, adapter in self.adapters.items() if adapter.is_available()
        ]

    def get_adapter_info(self) -> dict[str, dict[str, Any]]:
        """Get information about all adapters"""
        info = {}
        for name, adapter in self.adapters.items():
            info[name] = {
                "provider": adapter.get_provider_name(),
                "available": adapter.is_available(),
                "enabled": adapter.enabled,
            }
        return info


def create_image_registry(config: dict[str, Any]) -> ImageAdapterRegistry:
    """Create and configure an image adapter registry"""
    return ImageAdapterRegistry(config)
