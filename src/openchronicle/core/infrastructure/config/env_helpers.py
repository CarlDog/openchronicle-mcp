"""Consolidated environment variable and config value parsing helpers.

These helpers handle three-layer precedence: dataclass defaults -> JSON file
values -> env var overrides. They work with both string values (from env vars)
and native JSON types (bool, int, float) from config files.
"""

from __future__ import annotations

import os


def parse_bool(value: object, *, default: bool) -> bool:
    """Parse a boolean from string, native bool, or None.

    Truthy strings: "1", "true", "yes", "on" (case-insensitive).
    Falsy strings: "0", "false", "no", "off" (case-insensitive).
    Native bools pass through. None returns default.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def parse_int(value: object, *, default: int) -> int:
    """Parse an integer from string, native int, or None.

    Native ints pass through. Strings are stripped and converted.
    Invalid values return default. None returns default.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        # bool is a subclass of int in Python — reject it
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        try:
            return int(raw)
        except ValueError:
            return default
    return default


def parse_float(value: object, *, default: float) -> float:
    """Parse a float from string, native float/int, or None.

    Native floats/ints pass through. Strings are stripped and converted.
    Invalid values return default. None returns default.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        raw = value.strip()
        try:
            return float(raw)
        except ValueError:
            return default
    return default


def parse_str(value: object, *, default: str) -> str:
    """Parse a string value, returning default for None or empty."""
    if value is None:
        return default
    if isinstance(value, str):
        return value if value else default
    return str(value)


def parse_str_list(value: object, *, default: list[str]) -> list[str]:
    """Parse a list of strings from a JSON array or CSV string.

    - list[str]: pass through (filtering empties)
    - str: split on commas, strip, filter empties
    - None: return default
    """
    if value is None:
        return list(default)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(default)


def env_override(env_name: str, file_value: object) -> object:
    """Return env var if set, otherwise file_value.

    This implements the precedence: env var > JSON file > (caller's default).
    Only returns the env var when it is explicitly set in the environment.
    """
    env_val = os.getenv(env_name)
    if env_val is not None:
        return env_val
    return file_value
