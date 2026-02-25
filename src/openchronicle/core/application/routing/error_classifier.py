"""Error classification for LLM call failures to drive fallback decisions."""

from __future__ import annotations

from typing import Literal

from openchronicle.core.application.policies.rate_limiter import RateLimitTimeoutError
from openchronicle.core.domain.exceptions import BudgetExceededError
from openchronicle.core.domain.ports.llm_port import LLMProviderError

ErrorClass = Literal["constraint", "transient", "refusal", "permanent"]


def classify_error(exc: Exception) -> ErrorClass:
    """
    Classify LLM call errors into categories for fallback decision-making.

    Categories:
    - constraint: Budget exceeded or rate limit timeout (hard limits reached)
    - transient: Temporary failures that may succeed on retry (429, 5xx, timeouts)
    - refusal: Content policy rejection or explicit refusal
    - permanent: All other failures (bad request, auth, etc.)

    Args:
        exc: Exception raised during LLM call

    Returns:
        Error classification category
    """
    # Constraint errors: budget or rate limits
    if isinstance(exc, BudgetExceededError | RateLimitTimeoutError):
        return "constraint"

    # LLM provider errors: check status code and error code
    if isinstance(exc, LLMProviderError):
        status_code = exc.status_code
        error_code = exc.error_code or ""

        # Transient: rate limits, server errors, timeouts
        if status_code in (429, 500, 502, 503, 504) or error_code in ("TIMEOUT", "CONNECTION_ERROR"):
            return "transient"

        # Refusal: content policy violations
        # OpenAI uses specific error codes for refusals
        if (
            error_code in ("content_policy_violation", "content_filter", "safety_system")
            or "content_filter" in error_code.lower()
            or "policy" in error_code.lower()
        ):
            return "refusal"

        # Check status code for refusal patterns (e.g., 400 with specific messages)
        if status_code == 400:
            message = str(exc).lower()
            if any(keyword in message for keyword in ["content", "policy", "violation", "refused", "unsafe"]):
                return "refusal"

        # Client errors (4xx except 429) are permanent
        if status_code and 400 <= status_code < 500 and status_code != 429:
            return "permanent"

        # Default to transient for unknown provider errors
        return "transient"

    # All other exceptions are permanent
    return "permanent"
