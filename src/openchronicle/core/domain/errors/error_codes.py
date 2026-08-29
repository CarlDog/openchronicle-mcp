"""Canonical error code constants for v3.

All public-facing error responses (HTTP, MCP) use these constants, never
inline string literals — `tests/test_error_codes_canonical.py` enforces
the rule (including `code=` kwargs and `"code":` dict keys since
2026-08-16). Every constant here has a real call site; the 2026-08-15
review pruned the ones that didn't (INVALID_REQUEST, INVALID_JSON,
UNEXPECTED_ERROR, UNKNOWN_ERROR — v2 vocabulary that outlived its
callers).
"""

from __future__ import annotations

# Request / validation
INVALID_ARGUMENT = "INVALID_ARGUMENT"
INVALID_HOST = "INVALID_HOST"

# Not-found / file-system
NOT_FOUND = "NOT_FOUND"
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
MEMORY_NOT_FOUND = "MEMORY_NOT_FOUND"
FILE_NOT_FOUND = "FILE_NOT_FOUND"

# Runtime / config
INTERNAL_ERROR = "INTERNAL_ERROR"
CONFIG_ERROR = "CONFIG_ERROR"

# External provider (embedding adapters today; future external systems)
PROVIDER_ERROR = "PROVIDER_ERROR"
MISSING_PACKAGE = "MISSING_PACKAGE"
TIMEOUT = "TIMEOUT"
CONNECTION_ERROR = "CONNECTION_ERROR"
# The upstream rejected THIS content as exceeding the embedding model's
# context (ADR 0009). Permanent per (space × content) — not provider
# health: consumers park the row as a tombstone instead of retrying,
# and the failure counters ignore it.
CONTENT_TOO_LONG = "CONTENT_TOO_LONG"


__all__ = [
    "CONFIG_ERROR",
    "CONNECTION_ERROR",
    "CONTENT_TOO_LONG",
    "FILE_NOT_FOUND",
    "INTERNAL_ERROR",
    "INVALID_ARGUMENT",
    "INVALID_HOST",
    "MEMORY_NOT_FOUND",
    "MISSING_PACKAGE",
    "NOT_FOUND",
    "PROJECT_NOT_FOUND",
    "PROVIDER_ERROR",
    "TIMEOUT",
]
