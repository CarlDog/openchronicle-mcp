"""
Image System Configuration Manager for OpenChronicle

Handles configuration loading, validation, and management for image systems.
Consolidates configuration logic from image_generation_engine.py and image_adapter.py
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from .image_models import ImageProvider, ImageConfig, NamingConfig, AutoGenerateConfig

logger = logging.getLogger(__name__)


class ImageConfigManager:
    """Manages configuration for image systems"""
    
    def __init__(self, story_path: Optional[str] = None):
        self.story_path = Path(story_path) if story_path else None
        self._model_registry = None
        self._config_cache = {}
    
    def load_model_registry(self) -> Dict[str, Any]:
        """Load the model registry configuration."""
        if self._model_registry is not None:
            return self._model_registry
        
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "model_registry.json"
        
        if not config_path.exists():
            logger.warning("CRITICAL: No model registry found - defaulting to mock image adapter!")
            logger.warning("Mock image adapter provides placeholder images only - NOT for production use!")
            self._model_registry = {
                "default_image_model": "mock_image", 
                "image_fallback_chain": ["mock_image"]
            }
            return self._model_registry
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._model_registry = json.load(f)
                logger.info(f"Loaded model registry from {config_path}")
                return self._model_registry
        except Exception as e:
            logger.error(f"Failed to load model registry: {e}")
            logger.warning("Falling back to mock configuration")
            self._model_registry = {
                "default_image_model": "mock_image",
                "image_fallback_chain": ["mock_image"]
            }
            return self._model_registry
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default image system configuration"""
        return {
            "enabled": True,
            "adapters": {
                "mock": {"enabled": True, "class": "MockImageAdapter"}
            },
            "auto_generate": {
                "character_portraits": True,
                "scene_images": True,
                "scene_triggers": ["major_event", "new_location"]
            },
            "naming": {
                "character_prefix": "char",
                "scene_prefix": "scene", 
                "location_prefix": "loc",
                "item_prefix": "item",
                "custom_prefix": "img"
            },
            "fallback_chain": ["mock"],
            "default_model": "mock_image"
        }
    
    def get_image_config_from_registry(self, story_path: Optional[str] = None) -> Dict[str, Any]:
        """Extract image configuration from registry and story config"""
        # Use provided story_path or fall back to instance path
        working_story_path = Path(story_path) if story_path else self.story_path
        
        registry = self.load_model_registry()
        
        # Check for story-specific configuration
        story_config = {}
        if working_story_path:
            config_path = working_story_path / "config.json"
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        story_config = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load story config: {e}")
        
        # Build adapter configuration
        adapters = {}
        
        # Check environment variables for API keys
        openai_key = os.getenv("OPENAI_API_KEY")
        stability_key = os.getenv("STABILITY_API_KEY")
        
        if openai_key:
            adapters["openai"] = {"enabled": True, "class": "OpenAIImageAdapter"}
        else:
            adapters["stability"] = {"enabled": False, "class": "StabilityImageAdapter"}  # Disabled by default
        
        adapters["mock"] = {"enabled": True, "class": "MockImageAdapter"}
        
        # Override with story config if available
        if "image_generation" in story_config:
            story_image_config = story_config["image_generation"]
            if "adapters" in story_image_config:
                adapters["openai"] = {"enabled": True, "class": "OpenAIImageAdapter"}
            if "stability_enabled" in story_image_config:
                adapters["stability"] = {"enabled": True, "class": "StabilityImageAdapter"}
            # Mock is always available
            adapters["mock"] = {"enabled": True, "class": "MockImageAdapter"}
        
        return {
            "enabled": True,
            "adapters": adapters,
            "auto_generate": {
                "character_portraits": True,
                "scene_images": True,
                "scene_triggers": ["major_event", "new_location"]
            },
            "fallback_chain": ["openai", "stability", "mock"] if openai_key else ["mock"],
            "default_model": registry.get("default_image_model", "mock_image")
        }
    
    def get_naming_config(self, custom_config: Optional[Dict[str, str]] = None) -> NamingConfig:
        """Get naming configuration with defaults"""
        default_naming = {
            "character_prefix": "char",
            "scene_prefix": "scene", 
            "location_prefix": "loc",
            "item_prefix": "item",
            "custom_prefix": "img"
        }
        
        if custom_config:
            default_naming.update(custom_config)
        
        return default_naming
    
    def get_auto_generate_config(self, custom_config: Optional[Dict[str, Any]] = None) -> AutoGenerateConfig:
        """Get auto-generation configuration with defaults"""
        default_auto = {
            "enabled": False,
            "trigger_keywords": ["describe", "appears", "looks like"],
            "character_triggers": ["new character", "character appears"],
            "scene_triggers": ["new scene", "setting changes"],
            "location_triggers": ["travels to", "arrives at"],
            "max_auto_per_scene": 3,
            "require_confirmation": True
        }
        
        if custom_config:
            default_auto.update(custom_config)
        
        return default_auto
    
    def get_provider_config(self, provider: ImageProvider) -> ImageConfig:
        """Get configuration for a specific provider"""
        cache_key = f"provider_{provider.value}"
        
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
        
        registry = self.load_model_registry()
        
        # Default configurations by provider
        configs = {
            ImageProvider.OPENAI_DALLE: {
                "provider": "openai_dalle",
                "model": "dall-e-3",
                "quality": "standard",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "timeout": 60,
                "max_retries": 3,
                "supported_sizes": ["1024x1024", "512x768", "768x512"]
            },
            ImageProvider.STABILITY_AI: {
                "provider": "stability_ai",
                "model": "stable-diffusion-xl-1024-v1-0",
                "api_key": os.getenv("STABILITY_API_KEY"),
                "timeout": 120,
                "max_retries": 3,
                "supported_sizes": ["512x512", "1024x1024", "768x512"]
            },
            ImageProvider.LOCAL_SD: {
                "provider": "local_sd",
                "endpoint": "http://localhost:7860",
                "timeout": 180,
                "max_retries": 2,
                "supported_sizes": ["512x512", "768x768", "512x768"]
            },
            ImageProvider.MOCK: {
                "provider": "mock",
                "enabled": True,
                "supported_sizes": ["512x512", "1024x1024", "512x768", "768x512"]
            }
        }
        
        config = configs.get(provider, {})
        
        # Override with registry settings if available
        if "image_adapters" in registry:
            provider_registry = registry["image_adapters"].get(provider.value, {})
            config.update(provider_registry)
        
        self._config_cache[cache_key] = config
        return config
    
    def validate_config(self, config: ImageConfig) -> List[str]:
        """Validate image configuration and return list of issues"""
        issues = []
        
        if not config.get("adapters"):
            issues.append("No image adapters configured")
        
        # Check for at least one working adapter
        working_adapters = 0
        for adapter_name, adapter_config in config.get("adapters", {}).items():
            if adapter_config.get("enabled", False):
                if adapter_name == "openai" and not os.getenv("OPENAI_API_KEY"):
                    issues.append("OpenAI adapter enabled but OPENAI_API_KEY not set")
                elif adapter_name == "stability" and not os.getenv("STABILITY_API_KEY"):
                    issues.append("Stability adapter enabled but STABILITY_API_KEY not set")
                else:
                    working_adapters += 1
        
        if working_adapters == 0:
            issues.append("No working image adapters available")
        
        return issues
    
    def get_fallback_chain(self) -> List[str]:
        """Get the fallback chain for image generation"""
        config = self.get_image_config_from_registry()
        return config.get("fallback_chain", ["mock"])
    
    def clear_cache(self):
        """Clear the configuration cache"""
        self._config_cache.clear()
        self._model_registry = None
