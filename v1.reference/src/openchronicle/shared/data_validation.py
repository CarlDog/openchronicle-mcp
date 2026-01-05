"""
Data validation utilities for OpenChronicle.

This module provides common validation patterns and utilities that complement
Pydantic models throughout the application. It includes custom validators,
validation decorators, and data sanitization functions.
"""

import json
import re
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from .exceptions import ValidationError


class DataValidator:
    """Centralized data validation utilities."""

    @staticmethod
    def validate_story_id(story_id: str) -> str:
        """Validate and normalize story ID format."""
        if not story_id:
            raise ValidationError("Story ID cannot be empty")

        # Story IDs should be alphanumeric with hyphens/underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", story_id):
            raise ValidationError(
                f"Invalid story ID format: {story_id}. " "Must contain only letters, numbers, hyphens, and underscores."
            )

        return story_id.strip().lower()

    @staticmethod
    def validate_character_name(name: str) -> str:
        """Validate character name format."""
        if not name or not name.strip():
            raise ValidationError("Character name cannot be empty")

        name = name.strip()
        if len(name) > 100:
            raise ValidationError("Character name too long (max 100 characters)")

        # Allow letters, spaces, apostrophes, hyphens
        if not re.match(r"^[a-zA-Z\s'\-]+$", name):
            raise ValidationError(
                f"Invalid character name: {name}. " "Must contain only letters, spaces, apostrophes, and hyphens."
            )

        return name

    @staticmethod
    def validate_json_structure(data: str, required_keys: Optional[List[str]] = None) -> Dict[str, Any]:
        """Validate JSON string and check for required keys."""
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON format: {e}") from e

        if not isinstance(parsed, dict):
            raise ValidationError("JSON must be an object/dictionary")

        if required_keys:
            missing_keys = [key for key in required_keys if key not in parsed]
            if missing_keys:
                raise ValidationError(f"Missing required keys: {missing_keys}")

        return parsed

    @staticmethod
    def validate_file_path(file_path: Union[str, Path], must_exist: bool = True) -> Path:
        """Validate file path format and existence."""
        path = Path(file_path)

        if must_exist and not path.exists():
            raise ValidationError(f"File not found: {path}")

        # Check for path traversal attempts
        try:
            path.resolve().relative_to(Path.cwd().resolve())
        except ValueError as e:
            raise ValidationError(f"Invalid file path (outside project): {path}") from e

        return path

    @staticmethod
    def sanitize_user_input(text: str, max_length: int = 1000) -> str:
        """Sanitize user input text."""
        if not text:
            return ""

        # Remove null bytes and control characters (except newlines/tabs)
        sanitized = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")

        # Limit length
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()

        return sanitized.strip()


def validate_range(
    value: Union[int, float],
    min_val: Union[int, float],
    max_val: Union[int, float],
) -> Union[int, float]:
    """Validate that a numeric value is within the specified range."""
    if not isinstance(value, (int, float)):
        raise ValidationError(f"Expected numeric value, got {type(value).__name__}")

    if value < min_val or value > max_val:
        raise ValidationError(f"Value {value} must be between {min_val} and {max_val}")

    return value


def validation_decorator(validator_func: Callable) -> Callable:
    """Decorator to add validation to function parameters."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Apply validation to first argument
            if args:
                args = (validator_func(args[0]),) + args[1:]
            return func(*args, **kwargs)

        return wrapper

    return decorator


# Common validation patterns
@validation_decorator(DataValidator.validate_story_id)
def process_story_with_validation(story_id: str, *args, **kwargs):
    """Example of validation decorator usage."""
    pass


# Export commonly used validators
__all__ = [
    "DataValidator",
    "validate_range",
    "validation_decorator",
    "ValidationError",
]
