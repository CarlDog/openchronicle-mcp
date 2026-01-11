"""Provider-aware LLM facade for routing-based execution."""

from __future__ import annotations

import os
from typing import Any

from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse


def extract_providers_from_routing_config() -> set[str]:
    """
    Extract provider names referenced by routing configuration.

    Checks:
    - OC_LLM_PROVIDER (explicit default)
    - OC_LLM_FAST_POOL (fast mode pool entries)
    - OC_LLM_QUALITY_POOL (quality mode pool entries)

    Returns:
        Sorted set of provider names referenced in config
    """
    providers: set[str] = set()

    # Check explicit default provider
    default_provider = os.getenv("OC_LLM_PROVIDER", "").strip()
    if default_provider:
        providers.add(default_provider)

    # Parse pools for provider:model pairs
    fast_pool = os.getenv("OC_LLM_FAST_POOL", "").strip()
    quality_pool = os.getenv("OC_LLM_QUALITY_POOL", "").strip()

    for pool_str in [fast_pool, quality_pool]:
        if not pool_str:
            continue
        for entry in pool_str.split(","):
            entry = entry.strip()
            if ":" in entry:
                provider = entry.split(":", 1)[0].strip()
                if provider:
                    providers.add(provider)

    return providers


class ProviderAwareLLMFacade(LLMPort):
    """
    LLM facade that routes calls to specific provider adapters.

    This enforces that routing decisions are authoritative - if routing
    selects provider X, the call must execute against provider X.
    """

    def __init__(self, adapters: dict[str, LLMPort], default_provider: str | None = None) -> None:
        """
        Initialize facade with provider adapters.

        Args:
            adapters: Mapping of provider name -> adapter instance
                      e.g., {'openai': OpenAIAdapter(...), 'stub': StubLLMAdapter()}
            default_provider: Optional default provider to use when provider=None.
                            If not set, provider parameter is required at runtime.
        """
        self._adapters = adapters
        self.default_provider = default_provider

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
            if self.default_provider is not None:
                # Use explicit default if configured
                provider = self.default_provider
            else:
                # Fail explicitly - no silent defaults
                available = ", ".join(self._adapters.keys()) if self._adapters else "none"
                raise LLMProviderError(
                    f"Provider parameter is required. Available providers: {available}",
                    status_code=None,
                    error_code="provider_required",
                    configured_providers=list(self._adapters.keys()),
                    hint="Set OC_LLM_PROVIDER to configure a default provider, or ensure routing provides a provider parameter.",
                )

        adapter = self._adapters.get(provider)
        if adapter is None:
            # Generate provider-specific hints
            hint = self._generate_configuration_hint(provider)
            raise LLMProviderError(
                f"Provider '{provider}' not configured. Available: {', '.join(self._adapters.keys())}",
                status_code=None,
                error_code="provider_not_configured",
                provider=provider,
                configured_providers=list(self._adapters.keys()),
                hint=hint,
            )

        # Delegate to the specific adapter
        return await adapter.complete_async(
            messages,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            provider=provider,
        )

    def _generate_configuration_hint(self, provider: str) -> str:
        """
        Generate actionable hint for configuring a provider.

        Args:
            provider: Provider name that is not configured

        Returns:
            Actionable hint for resolving configuration
        """
        if provider == "openai":
            # Check if API key is missing
            if not os.getenv("OPENAI_API_KEY"):
                return "Set OPENAI_API_KEY environment variable to use OpenAI provider."
            return "OpenAI provider requires OPENAI_API_KEY and proper adapter wiring."

        if provider == "ollama":
            return (
                "Ollama provider must be included in OC_LLM_FAST_POOL or OC_LLM_QUALITY_POOL, "
                "or explicitly wired during facade initialization."
            )

        # Generic hint
        return (
            f"Provider '{provider}' must be wired during facade initialization. "
            f"Check routing configuration and adapter setup."
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
                   If None, auto-detects based on routing config and environment.

    Returns:
        ProviderAwareLLMFacade with configured adapters
    """
    adapters: dict[str, LLMPort] = {}

    # Determine which providers to configure
    if providers is None:
        # Auto-detect: always include stub, plus providers from routing config
        providers_needed = extract_providers_from_routing_config()
        providers_to_setup = ["stub"]  # Always include stub

        # Add providers referenced by routing config
        for provider in sorted(providers_needed):
            if provider not in providers_to_setup:
                providers_to_setup.append(provider)
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
                # Skip if API key not available - will fail explicitly if routing tries to use it
                continue
            from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

            adapters["openai"] = OpenAIAdapter(api_key=api_key)

        elif provider == "ollama":
            from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

            # Include ollama unconditionally when referenced (no network probing)
            adapters["ollama"] = OllamaAdapter()

    # Set default_provider only if explicitly configured AND adapter is present
    default_provider_name = os.getenv("OC_LLM_PROVIDER", "").strip()
    default_provider = None
    if default_provider_name and default_provider_name in adapters:
        default_provider = default_provider_name

    return ProviderAwareLLMFacade(adapters, default_provider=default_provider)
