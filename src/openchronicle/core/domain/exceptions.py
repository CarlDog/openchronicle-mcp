"""Common exceptions for LLM operations."""

from __future__ import annotations


class BudgetExceededError(Exception):
    """Raised when a task exceeds its token budget."""

    def __init__(self, limit: int, current: int, provider: str, model: str) -> None:
        self.limit = limit
        self.current = current
        self.provider = provider
        self.model = model
        super().__init__(f"Task token budget exceeded: {current} >= {limit}")


class NotFoundError(Exception):
    """Raised when a requested entity does not exist."""

    def __init__(self, message: str, *, code: str = "NOT_FOUND") -> None:
        self.code = code
        super().__init__(message)


class ValidationError(Exception):
    """Raised when input fails domain validation rules."""

    def __init__(self, message: str, *, code: str = "INVALID_ARGUMENT") -> None:
        self.code = code
        super().__init__(message)


class ConfigError(Exception):
    """Raised when runtime configuration is missing or invalid."""

    def __init__(self, message: str, *, code: str = "CONFIG_ERROR") -> None:
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
        error_code: str = "PROVIDER_ERROR",
        hint: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        self.error_code = error_code
        self.hint = hint
        self.details = details
        super().__init__(message)
