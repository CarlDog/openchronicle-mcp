from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    request_id: str | None = None
    finish_reason: str | None = None
    usage: LLMUsage | None = None
    latency_ms: int | None = None


class LLMProviderError(Exception):
    """Exception raised when LLM provider encounters an error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_code: str | None = None,
        provider: str | None = None,
        configured_providers: list[str] | None = None,
        hint: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Initialize LLM provider error with structured context.

        Args:
            message: Human-readable error message
            status_code: HTTP status code (if applicable)
            error_code: Machine-readable error code (e.g., "provider_not_configured")
            provider: Provider that was requested
            configured_providers: List of available providers
            hint: Actionable hint for resolving the error
            details: Additional structured error details
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.provider = provider
        self.configured_providers = configured_providers or []
        self.hint = hint
        self.details = details or {}


class LLMPort(ABC):
    @abstractmethod
    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        """Generate a chat completion asynchronously.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name to use
            max_output_tokens: Maximum tokens in response
            temperature: Sampling temperature
            provider: Provider name (e.g., 'openai', 'ollama', 'stub').
                      If None, adapter uses its default provider.

        Returns:
            LLMResponse with content, provider, model, usage, etc.

        Raises:
            LLMProviderError: If the call fails or provider is not available
        """

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        """Synchronous convenience wrapper."""

        raise NotImplementedError

    # Backwards compatibility helpers for legacy prompt-only flows
    def generate(self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None) -> str:
        response = self.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model or "",
            max_output_tokens=parameters.get("max_tokens") if parameters else None,
            temperature=parameters.get("temperature") if parameters else None,
        )
        return response.content

    async def generate_async(
        self, prompt: str, *, model: str | None = None, parameters: dict[str, Any] | None = None
    ) -> str:
        response = await self.complete_async(
            messages=[{"role": "user", "content": prompt}],
            model=model or "",
            max_output_tokens=parameters.get("max_tokens") if parameters else None,
            temperature=parameters.get("temperature") if parameters else None,
        )
        return response.content
