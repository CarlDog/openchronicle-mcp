"""Retry policy with exponential backoff for transient LLM failures."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

from openchronicle.core.domain.ports.llm_port import LLMProviderError

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry policy."""

    max_retries: int = 2  # Maximum number of retry attempts
    max_retry_sleep_ms: int = 2000  # Maximum sleep duration per retry
    base_delay_ms: int = 100  # Base delay for exponential backoff
    jitter: bool = True  # Add random jitter to backoff


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""

    attempt: int
    max_retries: int
    sleep_ms: float
    reason: str
    status_code: int | None = None
    error_type: str | None = None


class RetryPolicy:
    """
    Retry policy for transient LLM failures with exponential backoff.

    Retries on:
    - HTTP 429 (rate limit)
    - HTTP 500-599 (server errors)
    - Timeouts and connection errors
    """

    def __init__(self, config: RetryConfig | None = None):
        """Initialize retry policy with configuration."""
        self.config = config or RetryConfig()

    def _should_retry(self, error: Exception) -> bool:
        """Determine if an error should trigger a retry."""
        # Check for LLMProviderError with retryable status codes
        if isinstance(error, LLMProviderError) and error.status_code is not None:
            # Retry on 429 (rate limit) and 5xx (server errors)
            return error.status_code == 429 or (500 <= error.status_code < 600)

        # Retry on timeout and connection errors
        error_name = type(error).__name__.lower()
        return any(
            keyword in error_name
            for keyword in ["timeout", "connection", "connect", "timedout", "asyncio.timeouterror"]
        )

    def _calculate_sleep_ms(self, attempt: int, retry_after: float | None = None) -> float:
        """
        Calculate sleep duration with exponential backoff and jitter.

        Args:
            attempt: Current attempt number (1-indexed)
            retry_after: Optional retry-after hint from response (in seconds)

        Returns:
            Sleep duration in milliseconds
        """
        # Use retry-after if available, otherwise exponential backoff
        sleep_ms = retry_after * 1000.0 if retry_after is not None else self.config.base_delay_ms * (2 ** (attempt - 1))

        # Add jitter (±25% random variation)
        if self.config.jitter:
            jitter_range = sleep_ms * 0.25
            sleep_ms += random.uniform(-jitter_range, jitter_range)

        # Cap at max_retry_sleep_ms
        sleep_ms = min(sleep_ms, self.config.max_retry_sleep_ms)

        return max(0, sleep_ms)

    def _extract_retry_after(self, error: Exception) -> float | None:
        """Extract retry-after hint from error if available."""
        if isinstance(error, LLMProviderError):
            # Check if error has retry_after attribute (some providers include this)
            return getattr(error, "retry_after", None)
        return None

    async def execute(
        self,
        func: Callable[[], Awaitable[T]],
        on_retry: Callable[[RetryAttempt], None] | None = None,
        on_exhausted: Callable[[int, Exception], None] | None = None,
    ) -> T:
        """
        Execute function with retry policy.

        Args:
            func: Async function to execute
            on_retry: Callback for each retry attempt
            on_exhausted: Callback when retries are exhausted

        Returns:
            Result from successful function call

        Raises:
            Exception: Original exception if retries exhausted
        """
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await func()
            except Exception as exc:  # noqa: BLE001
                last_error = exc

                # Check if we should retry
                if not self._should_retry(exc):
                    raise

                # Check if we have retries left
                if attempt >= self.config.max_retries:
                    if on_exhausted:
                        on_exhausted(attempt + 1, exc)
                    raise

                # Calculate sleep duration
                retry_after = self._extract_retry_after(exc)
                sleep_ms = self._calculate_sleep_ms(attempt + 1, retry_after)

                # Create retry attempt info
                status_code = getattr(exc, "status_code", None) if isinstance(exc, LLMProviderError) else None
                retry_info = RetryAttempt(
                    attempt=attempt + 1,
                    max_retries=self.config.max_retries,
                    sleep_ms=sleep_ms,
                    reason=str(exc)[:200],
                    status_code=status_code,
                    error_type=type(exc).__name__,
                )

                # Notify callback
                if on_retry:
                    on_retry(retry_info)

                # Sleep before retry
                if sleep_ms > 0:
                    await asyncio.sleep(sleep_ms / 1000.0)

        # Should never reach here, but satisfy type checker
        if last_error:
            raise last_error
        raise RuntimeError("Retry loop ended without success or error")


class RetryExhaustedError(Exception):
    """Raised when retry policy exhausts all attempts."""

    def __init__(self, attempts: int, last_error_type: str, last_status_code: int | None = None):
        self.attempts = attempts
        self.last_error_type = last_error_type
        self.last_status_code = last_status_code
        msg = f"Retries exhausted after {attempts} attempts. Last error: {last_error_type}"
        if last_status_code:
            msg += f" (status {last_status_code})"
        super().__init__(msg)
