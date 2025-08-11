"""
Management Systems - Configuration and Validation

Consolidates configuration management and validation logic from token_manager.py
and bookmark_manager.py providing unified config handling and input validation.
"""

import json
from typing import Any

from .management_models import BookmarkType
from .management_models import ManagementException


class ConfigManager:
    """Manages configuration for management systems."""

    def __init__(self):
        self.config_cache = {}
        self.default_config = self._get_default_config()

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration for management systems."""
        return {
            "token_management": {
                "default_max_tokens": 4096,
                "truncation_threshold": 0.9,
                "continuation_overlap": 100,
                "cache_size": 1000,
                "supported_encoders": [
                    "gpt-4",
                    "gpt-3.5-turbo",
                    "claude",
                    "cl100k_base",
                ],
            },
            "bookmark_management": {
                "max_bookmarks_per_scene": 10,
                "auto_cleanup_enabled": True,
                "search_limit": 100,
                "valid_types": ["user", "auto", "chapter", "system"],
            },
        }

    def get_token_config(self) -> dict[str, Any]:
        """Get token management configuration."""
        return self.default_config.get("token_management", {})

    def get_bookmark_config(self) -> dict[str, Any]:
        """Get bookmark management configuration."""
        return self.default_config.get("bookmark_management", {})

    def get_config_value(self, section: str, key: str, default: Any = None) -> Any:
        """Get a specific configuration value."""
        return self.default_config.get(section, {}).get(key, default)


class ValidationManager:
    """Manages validation for management system operations."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def validate_bookmark_type(self, bookmark_type: str) -> BookmarkType:
        """Validate and convert bookmark type."""
        valid_types = self.config.get_config_value(
            "bookmark_management", "valid_types", []
        )

        if bookmark_type not in valid_types:
            raise ManagementException(
                f"Invalid bookmark type: {bookmark_type}. Valid types: {valid_types}"
            )

        return BookmarkType(bookmark_type)

    def validate_bookmark_label(self, label: str) -> str:
        """Validate bookmark label."""
        if not label or not label.strip():
            raise ManagementException("Bookmark label cannot be empty")

        if len(label) > 255:
            raise ManagementException("Bookmark label too long (max 255 characters)")

        return label.strip()

    def validate_scene_id(self, scene_id: str) -> str:
        """Validate scene ID format."""
        if not scene_id or not scene_id.strip():
            raise ManagementException("Scene ID cannot be empty")

        return scene_id.strip()

    def validate_story_id(self, story_id: str) -> str:
        """Validate story ID format."""
        if not story_id or not story_id.strip():
            raise ManagementException("Story ID cannot be empty")

        return story_id.strip()

    def validate_token_count(self, tokens: int) -> int:
        """Validate token count."""
        if tokens < 0:
            raise ManagementException("Token count cannot be negative")

        return tokens

    def validate_model_name(self, model_name: str) -> str:
        """Validate model name."""
        if not model_name or not model_name.strip():
            raise ManagementException("Model name cannot be empty")

        return model_name.strip()

    def validate_text_content(self, text: str, max_length: int = 10000) -> str:
        """Validate text content."""
        if not isinstance(text, str):
            raise ManagementException("Text content must be a string")

        if len(text) > max_length:
            raise ManagementException(
                f"Text content too long (max {max_length} characters)"
            )

        return text

    def validate_json_metadata(self, metadata: Any) -> dict[str, Any]:
        """Validate and ensure metadata is JSON-serializable."""
        if metadata is None:
            return {}

        if not isinstance(metadata, dict):
            raise ManagementException("Metadata must be a dictionary")

        try:
            # Test JSON serialization
            json.dumps(metadata)
            return metadata
        except (TypeError, ValueError) as e:
            raise ManagementException(f"Metadata is not JSON-serializable: {e}")

    def validate_search_query(self, query: str | None) -> str | None:
        """Validate search query."""
        if query is None:
            return None

        if not isinstance(query, str):
            raise ManagementException("Search query must be a string")

        query = query.strip()
        if len(query) > 500:
            raise ManagementException("Search query too long (max 500 characters)")

        return query if query else None

    def validate_pagination(self, limit: int, offset: int) -> tuple[int, int]:
        """Validate pagination parameters."""
        if limit < 1:
            raise ManagementException("Limit must be at least 1")

        if limit > 1000:
            raise ManagementException("Limit cannot exceed 1000")

        if offset < 0:
            raise ManagementException("Offset cannot be negative")

        return limit, offset


class DatabaseHelper:
    """Helper for database operations in management systems."""

    @staticmethod
    def format_sql_conditions(conditions: dict[str, Any]) -> tuple[str, list[Any]]:
        """Format conditions for SQL WHERE clauses."""
        if not conditions:
            return "", []

        where_parts = []
        params = []

        for key, value in conditions.items():
            if value is not None:
                where_parts.append(f"{key} = ?")
                params.append(value)

        where_clause = " AND ".join(where_parts)
        return f"WHERE {where_clause}" if where_clause else "", params

    @staticmethod
    def format_search_conditions(
        query: str | None, search_fields: list[str]
    ) -> tuple[str, list[Any]]:
        """Format search conditions for FTS queries."""
        if not query or not search_fields:
            return "", []

        # Create LIKE conditions for each search field
        like_conditions = []
        params = []

        for field in search_fields:
            like_conditions.append(f"{field} LIKE ?")
            params.append(f"%{query}%")

        search_clause = " OR ".join(like_conditions)
        return f"WHERE ({search_clause})" if search_clause else "", params

    @staticmethod
    def format_metadata_json(metadata: dict[str, Any] | None) -> str:
        """Format metadata as JSON string for database storage."""
        return json.dumps(metadata or {})

    @staticmethod
    def parse_metadata_json(metadata_str: str | None) -> dict[str, Any]:
        """Parse JSON metadata from database."""
        if not metadata_str:
            return {}

        try:
            return json.loads(metadata_str)
        except (json.JSONDecodeError, TypeError):
            return {}
