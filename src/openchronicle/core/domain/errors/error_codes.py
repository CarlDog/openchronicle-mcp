"""Canonical error code constants for v3.

All public-facing error responses (HTTP, MCP) use these constants, never
inline string literals — `tests/test_error_codes_canonical.py` enforces
the rule. v2's task/plugin/MoE/router/budget codes are gone with their
subsystems.
"""

from __future__ import annotations

# Request / validation
INVALID_ARGUMENT = "INVALID_ARGUMENT"
INVALID_REQUEST = "INVALID_REQUEST"
INVALID_JSON = "INVALID_JSON"

# Not-found / file-system
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
MEMORY_NOT_FOUND = "MEMORY_NOT_FOUND"
FILE_NOT_FOUND = "FILE_NOT_FOUND"

# Runtime / config
INTERNAL_ERROR = "INTERNAL_ERROR"
CONFIG_ERROR = "CONFIG_ERROR"
UNEXPECTED_ERROR = "UNEXPECTED_ERROR"

# External provider (embedding adapters today; future external systems)
PROVIDER_ERROR = "PROVIDER_ERROR"
MISSING_PACKAGE = "MISSING_PACKAGE"
TIMEOUT = "TIMEOUT"
CONNECTION_ERROR = "CONNECTION_ERROR"
UNKNOWN_ERROR = "UNKNOWN_ERROR"


__all__ = [
    "INVALID_ARGUMENT",
    "INVALID_REQUEST",
    "INVALID_JSON",
    "PROJECT_NOT_FOUND",
    "MEMORY_NOT_FOUND",
    "FILE_NOT_FOUND",
    "INTERNAL_ERROR",
    "CONFIG_ERROR",
    "UNEXPECTED_ERROR",
    "PROVIDER_ERROR",
    "MISSING_PACKAGE",
    "TIMEOUT",
    "CONNECTION_ERROR",
    "UNKNOWN_ERROR",
]
