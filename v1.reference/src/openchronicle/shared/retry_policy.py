"""Generic async retry policy with exponential backoff and jitter.

Lightweight infrastructure to progressively replace ad-hoc try/except blocks.
Deliberately small surface area; expand with cancellation, metrics later.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable
from typing import Callable
from typing import Type

from .exceptions import InfrastructureError


# Default retriable exceptions - focus on transient infrastructure failures
DEFAULT_RETRIABLE_EXCEPTIONS = (
    ConnectionError,  # Network connectivity issues
    OSError,  # System-level errors (file access, etc.)
    TimeoutError,  # Timeout-related errors
    InfrastructureError,  # Our custom infrastructure errors
    asyncio.TimeoutError,  # Async timeout errors
)


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.5  # seconds
    max_delay: float = 5.0
    jitter: float = 0.25  # proportion of delay for jitter window
    retry_exceptions: tuple[Type[Exception], ...] = DEFAULT_RETRIABLE_EXCEPTIONS

    async def run(self, fn: Callable[[], Awaitable]):  # type: ignore[override]
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await fn()
            except self.retry_exceptions as e:  # type: ignore[misc]
                last_error = e
                if attempt == self.max_attempts:
                    break
                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
                jitter_range = delay * self.jitter
                delay = delay + random.uniform(-jitter_range, jitter_range)
                await asyncio.sleep(max(0.05, delay))
        if last_error:
            raise last_error
        raise RuntimeError("RetryPolicy failed without capturing an error")


def retryable(*exceptions: Type[Exception]):
    """Convenience decorator to attach a simple retry with default policy.

    Args:
        *exceptions: Specific exceptions to retry on. If none provided,
                    uses DEFAULT_RETRIABLE_EXCEPTIONS.

    Example:
        @retryable(ConnectionError, TimeoutError)
        async def fetch_data():
            # This will retry on ConnectionError and TimeoutError
            pass
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            policy = RetryPolicy(retry_exceptions=exceptions or DEFAULT_RETRIABLE_EXCEPTIONS)
            return await policy.run(lambda: func(*args, **kwargs))

        return wrapper

    return decorator
