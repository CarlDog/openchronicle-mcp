"""
Shared JSON utilities for OpenChronicle core modules.
Consolidates JSON handling patterns from 8+ modules to eliminate duplication.
"""

import json
import logging
from pathlib import Path
from typing import Any


# Configure logging for JSON operations
logger = logging.getLogger(__name__)


class JSONUtilities:
    """Standardized JSON operations with error handling and validation."""

    @staticmethod
    def safe_loads(json_str: str, fallback: Any = None, fallback_type: type = dict) -> Any:
        """
        Safe JSON string loading with fallback support.

        Args:
            json_str: JSON string to parse
            fallback: Fallback value if parsing fails
            fallback_type: Type of fallback to use if fallback is None

        Returns:
            Parsed JSON data or fallback value
        """
        if not json_str or json_str.strip() == "":
            return fallback if fallback is not None else fallback_type()

        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"JSON parsing failed: {e}. Using fallback.")
            return fallback if fallback is not None else fallback_type()

    @staticmethod
    def safe_dumps(data: Any, pretty: bool = False, ensure_ascii: bool = True) -> str:
        """
        Safe JSON string serialization.

        Args:
            data: Data to serialize
            pretty: Whether to format with indentation
            ensure_ascii: Whether to escape non-ASCII characters

        Returns:
            JSON string or empty string on error
        """
        try:
            if pretty:
                return json.dumps(data, indent=2, ensure_ascii=ensure_ascii)
            return json.dumps(data, ensure_ascii=ensure_ascii)
        except (TypeError, ValueError):
            logger.exception("JSON serialization failed")
            return "{}" if isinstance(data, dict) else "[]" if isinstance(data, list) else '""'

    @staticmethod
    def load_file(file_path: str | Path, fallback: Any = None) -> Any:
        """
        Load JSON from file with error handling.

        Args:
            file_path: Path to JSON file
            fallback: Fallback value if loading fails

        Returns:
            Parsed JSON data or fallback value
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.warning(f"JSON file not found: {file_path}")
            return fallback if fallback is not None else {}

        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.exception("Failed to load JSON file")
            return fallback if fallback is not None else {}

    @staticmethod
    def save_file(
        data: Any,
        file_path: str | Path,
        pretty: bool = True,
        ensure_ascii: bool = False,
        create_dirs: bool = True,
    ) -> bool:
        """
        Save data to JSON file with error handling.

        Args:
            data: Data to save
            file_path: Path to save file
            pretty: Whether to format with indentation
            ensure_ascii: Whether to escape non-ASCII characters
            create_dirs: Whether to create parent directories

        Returns:
            True if successful, False otherwise
        """
        file_path = Path(file_path)

        if create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=ensure_ascii)
                else:
                    json.dump(data, f, ensure_ascii=ensure_ascii)
        except (TypeError, ValueError, OSError):
            logger.exception("Failed to save JSON file")
            return False
        else:
            return True

    @staticmethod
    def merge_objects(base: dict[str, Any], update: dict[str, Any], deep: bool = True) -> dict[str, Any]:
        """
        Merge two JSON objects.

        Args:
            base: Base dictionary
            update: Dictionary to merge into base
            deep: Whether to perform deep merge

        Returns:
            Merged dictionary
        """
        if not deep:
            result = base.copy()
            result.update(update)
            return result

        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = JSONUtilities.merge_objects(result[key], value, deep=True)
            else:
                result[key] = value
        return result

    @staticmethod
    def validate_schema(
        data: Any, required_keys: list[str], optional_keys: list[str] | None = None
    ) -> tuple[bool, list[str]]:
        """
        Simple schema validation for JSON objects.

        Args:
            data: Data to validate
            required_keys: Keys that must be present
            optional_keys: Keys that may be present

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not isinstance(data, dict):
            errors.append("Data must be a dictionary")
            return False, errors

        # Check required keys
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing required key: {key}")

        # Check for unknown keys if optional_keys is provided
        if optional_keys is not None:
            allowed_keys = set(required_keys) | set(optional_keys)
            for key in data.keys():
                if key not in allowed_keys:
                    errors.append(f"Unknown key: {key}")

        return len(errors) == 0, errors


class DatabaseJSONMixin:
    """Mixin for database-related JSON serialization patterns."""

    @staticmethod
    def safe_db_loads(db_value: str | None, fallback_type: type = dict) -> Any:
        """
        Safe loading of JSON from database fields.
        Common pattern: json.loads(row["field"] or "{}")
        """
        return JSONUtilities.safe_loads(db_value or "", fallback_type=fallback_type)

    @staticmethod
    def safe_db_dumps(data: Any) -> str:
        """
        Safe serialization for database storage.
        """
        return JSONUtilities.safe_dumps(data, pretty=False)


class ConfigJSONMixin:
    """Mixin for configuration file JSON operations."""

    @staticmethod
    def load_config(config_path: str | Path, required_keys: list[str] | None = None) -> dict[str, Any]:
        """
        Load and validate configuration JSON file.
        """
        config = JSONUtilities.load_file(config_path, fallback={})

        if required_keys:
            is_valid, errors = JSONUtilities.validate_schema(config, required_keys)
            if not is_valid:
                logger.error(f"Invalid config {config_path}: {errors}")
                return {}

        return config

    @staticmethod
    def save_config(config: dict[str, Any], config_path: str | Path) -> bool:
        """
        Save configuration with pretty formatting.
        """
        return JSONUtilities.save_file(config, config_path, pretty=True, ensure_ascii=False)
