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
