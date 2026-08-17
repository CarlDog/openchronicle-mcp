"""Error domain utilities and constants."""

from __future__ import annotations

from openchronicle.core.domain.errors.error_codes import (
    CONFIG_ERROR,
    CONNECTION_ERROR,
    FILE_NOT_FOUND,
    INTERNAL_ERROR,
    INVALID_ARGUMENT,
    INVALID_HOST,
    MEMORY_NOT_FOUND,
    MISSING_PACKAGE,
    NOT_FOUND,
    PROJECT_NOT_FOUND,
    PROVIDER_ERROR,
    TIMEOUT,
)

__all__ = [
    "CONFIG_ERROR",
    "CONNECTION_ERROR",
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
