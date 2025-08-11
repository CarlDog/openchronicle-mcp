"""
Configuration classes for management systems.
Defines configuration data structures for token and bookmark management.
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from .management_models import TokenUsageType, BookmarkType


@dataclass
class TokenManagerConfig:
    """Configuration for token management system."""

    default_model: str = "gpt-3.5-turbo"
    available_models: List[str] = field(default_factory=lambda: ["gpt-3.5-turbo"])
    fallback_chain: List[str] = field(default_factory=lambda: ["gpt-3.5-turbo"])
    cache_size: int = 1000
    padding_factor: float = 1.1
    safety_margin: int = 100
    model_configs: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenManagerConfig":
        """Create config from dictionary."""
        return cls(
            default_model=data.get("default_model", "gpt-3.5-turbo"),
            available_models=data.get("available_models", ["gpt-3.5-turbo"]),
            fallback_chain=data.get("fallback_chain", ["gpt-3.5-turbo"]),
            cache_size=data.get("cache_size", 1000),
            padding_factor=data.get("padding_factor", 1.1),
            safety_margin=data.get("safety_margin", 100),
            model_configs=data.get("model_configs", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "default_model": self.default_model,
            "available_models": self.available_models,
            "fallback_chain": self.fallback_chain,
            "cache_size": self.cache_size,
            "padding_factor": self.padding_factor,
            "safety_margin": self.safety_margin,
            "model_configs": self.model_configs,
        }


@dataclass
class BookmarkManagerConfig:
    """Configuration for bookmark management system."""

    default_bookmark_type: BookmarkType = BookmarkType.USER
    max_search_results: int = 100
    enable_full_text_search: bool = True
    cache_size: int = 500
    auto_create_chapters: bool = True
    chapter_detection_keywords: List[str] = field(
        default_factory=lambda: ["chapter", "section", "part", "book", "volume"]
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BookmarkManagerConfig":
        """Create config from dictionary."""
        return cls(
            default_bookmark_type=BookmarkType(
                data.get("default_bookmark_type", "user")
            ),
            max_search_results=data.get("max_search_results", 100),
            enable_full_text_search=data.get("enable_full_text_search", True),
            cache_size=data.get("cache_size", 500),
            auto_create_chapters=data.get("auto_create_chapters", True),
            chapter_detection_keywords=data.get(
                "chapter_detection_keywords",
                ["chapter", "section", "part", "book", "volume"],
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "default_bookmark_type": self.default_bookmark_type.value,
            "max_search_results": self.max_search_results,
            "enable_full_text_search": self.enable_full_text_search,
            "cache_size": self.cache_size,
            "auto_create_chapters": self.auto_create_chapters,
            "chapter_detection_keywords": self.chapter_detection_keywords,
        }


@dataclass
class ManagementConfig:
    """Unified configuration for the management orchestrator."""

    token_config: Dict[str, Any] = field(default_factory=dict)
    bookmark_config: Dict[str, Any] = field(default_factory=dict)
    enable_cross_system_analytics: bool = True
    cache_size: int = 1000

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ManagementConfig":
        """Create config from dictionary."""
        return cls(
            token_config=data.get("token_config", {}),
            bookmark_config=data.get("bookmark_config", {}),
            enable_cross_system_analytics=data.get(
                "enable_cross_system_analytics", True
            ),
            cache_size=data.get("cache_size", 1000),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "token_config": self.token_config,
            "bookmark_config": self.bookmark_config,
            "enable_cross_system_analytics": self.enable_cross_system_analytics,
            "cache_size": self.cache_size,
        }


class ConfigValidator:
    """Validates configuration for management systems."""

    @staticmethod
    def validate_token_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate token management configuration."""
        validated = {}

        # Validate default_model
        validated["default_model"] = config.get("default_model", "gpt-3.5-turbo")

        # Validate available_models
        available_models = config.get("available_models", ["gpt-3.5-turbo"])
        if not isinstance(available_models, list) or not available_models:
            available_models = ["gpt-3.5-turbo"]
        validated["available_models"] = available_models

        # Validate fallback_chain
        fallback_chain = config.get("fallback_chain", ["gpt-3.5-turbo"])
        if not isinstance(fallback_chain, list) or not fallback_chain:
            fallback_chain = ["gpt-3.5-turbo"]
        validated["fallback_chain"] = fallback_chain

        # Validate numeric values
        validated["cache_size"] = max(1, config.get("cache_size", 1000))
        validated["padding_factor"] = max(1.0, config.get("padding_factor", 1.1))
        validated["safety_margin"] = max(0, config.get("safety_margin", 100))

        # Validate model_configs
        validated["model_configs"] = config.get("model_configs", {})

        return validated

    @staticmethod
    def validate_bookmark_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate bookmark management configuration."""
        validated = {}

        # Validate bookmark type
        bookmark_type = config.get("default_bookmark_type", "user")
        try:
            validated["default_bookmark_type"] = BookmarkType(bookmark_type)
        except ValueError:
            validated["default_bookmark_type"] = BookmarkType.USER

        # Validate numeric values
        validated["max_search_results"] = max(1, config.get("max_search_results", 100))
        validated["cache_size"] = max(1, config.get("cache_size", 500))

        # Validate boolean values
        validated["enable_full_text_search"] = bool(
            config.get("enable_full_text_search", True)
        )
        validated["auto_create_chapters"] = bool(
            config.get("auto_create_chapters", True)
        )

        # Validate chapter detection keywords
        keywords = config.get(
            "chapter_detection_keywords",
            ["chapter", "section", "part", "book", "volume"],
        )
        if not isinstance(keywords, list):
            keywords = ["chapter", "section", "part", "book", "volume"]
        validated["chapter_detection_keywords"] = keywords

        return validated

    @staticmethod
    def validate_management_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate unified management configuration."""
        validated = {}

        # Validate sub-configs
        validated["token_config"] = ConfigValidator.validate_token_config(
            config.get("token_config", {})
        )
        validated["bookmark_config"] = ConfigValidator.validate_bookmark_config(
            config.get("bookmark_config", {})
        )

        # Validate other settings
        validated["enable_cross_system_analytics"] = bool(
            config.get("enable_cross_system_analytics", True)
        )
        validated["cache_size"] = max(1, config.get("cache_size", 1000))

        return validated
