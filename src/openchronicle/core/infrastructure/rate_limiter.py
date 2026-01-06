"""Rate limiter with token bucket algorithm for LLM calls."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Literal


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting per (provider, model) scope."""

    rpm_limit: int | None = None  # Requests per minute
    tpm_limit: int | None = None  # Tokens per minute
    max_wait_ms: int = 5000  # Maximum wait time before failing


@dataclass
class TokenBucket:
    """Token bucket for rate limiting a specific resource (RPM or TPM)."""

    capacity: float  # Maximum tokens
    tokens: float  # Current available tokens
    refill_rate: float  # Tokens added per second
    last_refill: float  # Last refill timestamp


class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm.

    Supports two types of limits:
    - RPM (Requests Per Minute): limits number of requests
    - TPM (Tokens Per Minute): limits total token consumption

    Rate limits are scoped per (provider, model, api_key_hash).
    """

    def __init__(self, config: RateLimitConfig | None = None):
        """Initialize rate limiter with optional configuration."""
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, dict[Literal["rpm", "tpm"], TokenBucket]] = {}
        self._lock = threading.Lock()

    def _get_scope_key(self, provider: str, model: str, api_key_hash: str | None = None) -> str:
        """Generate scope key for rate limit buckets."""
        if api_key_hash:
            return f"{provider}:{model}:{api_key_hash}"
        return f"{provider}:{model}"

    def _get_or_create_buckets(self, scope_key: str) -> dict[Literal["rpm", "tpm"], TokenBucket]:
        """Get or create token buckets for a scope."""
        if scope_key not in self._buckets:
            now = time.time()
            buckets: dict[Literal["rpm", "tpm"], TokenBucket] = {}

            if self.config.rpm_limit is not None:
                # RPM bucket: capacity = rpm_limit, refills at rpm_limit/60 per second
                buckets["rpm"] = TokenBucket(
                    capacity=float(self.config.rpm_limit),
                    tokens=float(self.config.rpm_limit),
                    refill_rate=self.config.rpm_limit / 60.0,
                    last_refill=now,
                )

            if self.config.tpm_limit is not None:
                # TPM bucket: capacity = tpm_limit, refills at tpm_limit/60 per second
                buckets["tpm"] = TokenBucket(
                    capacity=float(self.config.tpm_limit),
                    tokens=float(self.config.tpm_limit),
                    refill_rate=self.config.tpm_limit / 60.0,
                    last_refill=now,
                )

            self._buckets[scope_key] = buckets
        return self._buckets[scope_key]

    def _refill_bucket(self, bucket: TokenBucket, now: float) -> None:
        """Refill bucket based on elapsed time."""
        elapsed = now - bucket.last_refill
        bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.refill_rate)
        bucket.last_refill = now

    def _time_until_tokens_available(self, bucket: TokenBucket, tokens_needed: float, now: float) -> float:
        """Calculate time in seconds until tokens_needed are available."""
        if bucket.tokens >= tokens_needed:
            return 0.0
        deficit = tokens_needed - bucket.tokens
        return deficit / bucket.refill_rate

    def is_enabled(self) -> bool:
        """Check if rate limiting is enabled (any limit is set)."""
        return self.config.rpm_limit is not None or self.config.tpm_limit is not None

    def acquire(
        self,
        provider: str,
        model: str,
        estimated_tokens: int | None = None,
        api_key_hash: str | None = None,
    ) -> dict[str, float | None]:
        """
        Acquire rate limit tokens before making an LLM call.

        Args:
            provider: LLM provider name
            model: Model name
            estimated_tokens: Estimated input tokens (for TPM limiting)
            api_key_hash: Optional hash of API key for finer scope

        Returns:
            dict with 'wait_ms' and any limit info

        Raises:
            RateLimitTimeoutError: If wait time exceeds max_wait_ms
        """
        if not self.is_enabled():
            return {"wait_ms": 0.0}

        scope_key = self._get_scope_key(provider, model, api_key_hash)

        with self._lock:
            buckets = self._get_or_create_buckets(scope_key)
            now = time.time()

            # Refill all buckets
            for bucket in buckets.values():
                self._refill_bucket(bucket, now)

            # Calculate max wait time needed
            max_wait_seconds = 0.0

            # Check RPM
            if "rpm" in buckets:
                rpm_bucket = buckets["rpm"]
                wait_seconds = self._time_until_tokens_available(rpm_bucket, 1.0, now)
                max_wait_seconds = max(max_wait_seconds, wait_seconds)

            # Check TPM (only if estimate available)
            if "tpm" in buckets and estimated_tokens is not None and estimated_tokens > 0:
                tpm_bucket = buckets["tpm"]
                wait_seconds = self._time_until_tokens_available(tpm_bucket, float(estimated_tokens), now)
                max_wait_seconds = max(max_wait_seconds, wait_seconds)

            wait_ms = max_wait_seconds * 1000.0

            # Check if wait exceeds max
            if wait_ms > self.config.max_wait_ms:
                raise RateLimitTimeoutError(
                    max_wait_ms=self.config.max_wait_ms,
                    required_wait_ms=wait_ms,
                    provider=provider,
                    model=model,
                    rpm_limit=self.config.rpm_limit,
                    tpm_limit=self.config.tpm_limit,
                )

            # Wait if needed (release lock during sleep)
            if max_wait_seconds > 0:
                self._lock.release()
                try:
                    time.sleep(max_wait_seconds)
                finally:
                    self._lock.acquire()

                # Refill again after wait
                now = time.time()
                for bucket in buckets.values():
                    self._refill_bucket(bucket, now)

            # Consume tokens
            if "rpm" in buckets:
                buckets["rpm"].tokens -= 1.0

            if "tpm" in buckets and estimated_tokens is not None and estimated_tokens > 0:
                buckets["tpm"].tokens -= float(estimated_tokens)

            return {
                "wait_ms": wait_ms,
                "rpm_limit": float(self.config.rpm_limit) if self.config.rpm_limit is not None else None,
                "tpm_limit": float(self.config.tpm_limit) if self.config.tpm_limit is not None else None,
            }


class RateLimitTimeoutError(Exception):
    """Raised when rate limit wait time exceeds maximum allowed."""

    def __init__(
        self,
        max_wait_ms: int,
        required_wait_ms: float,
        provider: str,
        model: str,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
    ):
        self.max_wait_ms = max_wait_ms
        self.required_wait_ms = required_wait_ms
        self.provider = provider
        self.model = model
        self.rpm_limit = rpm_limit
        self.tpm_limit = tpm_limit
        super().__init__(
            f"Rate limit wait time {required_wait_ms:.0f}ms exceeds maximum {max_wait_ms}ms for {provider}/{model}"
        )


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text length using rough heuristic.

    Uses ~4 characters per token as a simple estimation.
    This is approximate and may vary by model/tokenizer.
    """
    if not text:
        return 0
    return math.ceil(len(text) / 4)
