"""Provider-aware LLM facade for routing-based execution."""

from __future__ import annotations

import os
from typing import Any

from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse


class ProviderAwareLLMFacade(LLMPort):
    """
    LLM facade that routes calls to specific provider adapters.

    This enforces that routing decisions are authoritative - if routing
    selects provider X, the call must execute against provider X.
    """

    def __init__(self, adapters: dict[str, LLMPort]) -> None:
        """
        Initialize facade with provider adapters.

        Args:
            adapters: Mapping of provider name -> adapter instance
                      e.g., {'openai': OpenAIAdapter(...), 'stub': StubLLMAdapter()}
        """
        self._adapters = adapters

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        """
        Execute LLM call with specified provider.

        Args:
            messages: Chat messages
            model: Model name
            max_output_tokens: Max output tokens
            temperature: Sampling temperature
            provider: Provider name (required for routing enforcement)

        Returns:
            LLMResponse from the specified provider

        Raises:
            LLMProviderError: If provider is not configured or unavailable
        """
        if provider is None:
            # Fallback to first available adapter if no provider specified
            if not self._adapters:
                raise LLMProviderError(
                    "No LLM providers configured",
                    status_code=None,
                    error_code="no_providers",
                )
            provider = next(iter(self._adapters))

        adapter = self._adapters.get(provider)
        if adapter is None:
            available = ", ".join(self._adapters.keys())
            raise LLMProviderError(
                f"Provider '{provider}' not configured. Available: {available}",
                status_code=None,
                error_code="provider_not_configured",
            )

        # Delegate to the specific adapter
        return await adapter.complete_async(
            messages,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            provider=provider,
        )

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        """Synchronous completion (not implemented)."""
        raise NotImplementedError("Use complete_async")


def create_provider_aware_llm(providers: list[str] | None = None) -> ProviderAwareLLMFacade:
    """
    Factory function to create provider-aware LLM facade.

    Args:
        providers: List of provider names to configure.
                   If None, auto-detects based on environment.

    Returns:
        ProviderAwareLLMFacade with configured adapters
    """
    adapters: dict[str, LLMPort] = {}

    # Determine which providers to configure
    if providers is None:
        # Auto-detect based on environment
        providers_to_setup = ["stub"]  # Always include stub
        if os.getenv("OPENAI_API_KEY"):
            providers_to_setup.append("openai")
        # Could add ollama detection here
    else:
        providers_to_setup = providers

    # Create adapters for each provider
    for provider in providers_to_setup:
        if provider == "stub":
            from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

            adapters["stub"] = StubLLMAdapter()

        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                # Skip if API key not available
                continue
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            adapters["openai"] = OpenAIAdapter(api_key=api_key)

        elif provider == "ollama":
            from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

            # Use default model for now
            adapters["ollama"] = OllamaAdapter()

    return ProviderAwareLLMFacade(adapters)
