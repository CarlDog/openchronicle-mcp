"""Domain exceptions for the v3 memory surface.

(The module docstring used to say "for LLM operations" and the file
carried BudgetExceededError — v2 vocabulary with zero callers, pruned
in the 2026-08-15 review's dead-code sweep.)
"""

from __future__ import annotations

from openchronicle.core.domain.errors.error_codes import (
    CONFIG_ERROR,
    INVALID_ARGUMENT,
    NOT_FOUND,
    PROVIDER_ERROR,
)


class NotFoundError(Exception):
    """Raised when a requested entity does not exist."""

    def __init__(self, message: str, *, code: str = NOT_FOUND) -> None:
        self.code = code
        super().__init__(message)


class ValidationError(Exception):
    """Raised when input fails domain validation rules."""

    def __init__(self, message: str, *, code: str = INVALID_ARGUMENT) -> None:
        self.code = code
        super().__init__(message)


class ConfigError(Exception):
    """Raised when runtime configuration is missing or invalid."""

    def __init__(self, message: str, *, code: str = CONFIG_ERROR) -> None:
        self.code = code
        super().__init__(message)


class ProviderError(Exception):
    """Raised when an external provider (embedding adapter, etc.) fails.

    Carries an error_code (free-form, often a domain code like PROVIDER_ERROR
    or MISSING_PACKAGE), an optional hint for the user, and optional details
    for structured logging. Replaces v2's LLMProviderError now that the LLM
    subsystem is gone.
    """

    def __init__(
        self,
        message: str,
        *,
        error_code: str = PROVIDER_ERROR,
        hint: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self.error_code = error_code
        self.hint = hint
        self.details = details
        super().__init__(message)
