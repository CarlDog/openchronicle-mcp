"""Provider-aware LLM facade for routing-based execution."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from openchronicle.core.application.config.model_config import ConfigError, ModelConfigLoader, ResolvedModelConfig
from openchronicle.core.domain.error_codes import (
    PROVIDER_NOT_CONFIGURED,
    PROVIDER_REQUIRED,
)
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse


def extract_providers_from_routing_config() -> set[str]:
    """Helper to read providers from routing environment variables."""

    providers: set[str] = set()

    default_provider = os.getenv("OC_LLM_PROVIDER", "").strip()
    if default_provider:
        providers.add(default_provider)

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
    """LLM facade that routes calls to provider adapters backed by model configs."""

    def __init__(
        self,
        adapters: dict[str, LLMPort] | None = None,
        *,
        config_loader: ModelConfigLoader | None = None,
        adapter_factories: dict[str, Callable[[ResolvedModelConfig], LLMPort]] | None = None,
        default_provider: str | None = None,
    ) -> None:
        # Static test adapters (e.g., stub or injected fakes for tests)
        self._adapters: dict[str, LLMPort] = adapters or {}

        # Config-driven factories + loader (new path)
        self._config_loader = config_loader
        self._adapter_factories = adapter_factories or {}
        self._adapter_cache: dict[tuple[str, str], LLMPort] = {}
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
        available = list(self._adapters) + [p for p in self._adapter_factories if p not in self._adapters]

        if provider is None:
            if self.default_provider is not None:
                provider = self.default_provider
            else:
                raise LLMProviderError(
                    f"Provider parameter is required. Available providers: {', '.join(available) if available else 'none'}",
                    status_code=None,
                    error_code=PROVIDER_REQUIRED,
                    configured_providers=available,
                    hint="Set OC_LLM_PROVIDER to configure a default provider, or ensure routing provides a provider parameter.",
                )

        adapter: LLMPort

        # Config-driven providers: always resolve per (provider, model)
        if provider in self._adapter_factories and self._config_loader is not None:
            try:
                resolved_config = self._config_loader.resolve(provider, model)
            except ConfigError as exc:  # pragma: no cover - exercised in tests via control paths
                raise LLMProviderError(str(exc), status_code=None, error_code="config_error") from exc

            adapter = self._get_adapter(provider, resolved_config)
        else:
            # Static adapters must be explicitly present for test/stub providers
            if provider in self._adapters:
                adapter = self._adapters[provider]
            else:
                hint = self._generate_configuration_hint(provider)
                raise LLMProviderError(
                    f"Provider '{provider}' not configured. Available: {', '.join(available)}",
                    status_code=None,
                    error_code=PROVIDER_NOT_CONFIGURED,
                    provider=provider,
                    configured_providers=available,
                    hint=hint,
                )

        return await adapter.complete_async(
            messages,
            model=model,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            provider=provider,
        )

    def _get_adapter(self, provider: str, cfg: ResolvedModelConfig) -> LLMPort:
        cache_key = (provider, cfg.model)
        if cache_key in self._adapter_cache:
            return self._adapter_cache[cache_key]

        factory = self._adapter_factories[provider]
        adapter = factory(cfg)
        self._adapter_cache[cache_key] = adapter
        return adapter

    def _generate_configuration_hint(self, provider: str) -> str:
        """Generate configuration hint prioritizing config-file setup."""
        config_dir = os.getenv("OC_CONFIG_DIR", "config")
        config_file_hint = f"Add an enabled model config in {config_dir}/models/{provider}_*.json"

        if provider == "openai":
            return f"{config_file_hint}. Optionally set OPENAI_API_KEY environment variable as override."
        if provider == "ollama":
            return (
                f"{config_file_hint}. "
                "Optionally set OLLAMA_HOST environment variable (e.g., http://localhost:11434)."
            )
        return (
            f"{config_file_hint}. "
            "Or add the provider to routing pools (OC_LLM_FAST_POOL, OC_LLM_QUALITY_POOL) via environment."
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


def create_provider_aware_llm(
    providers: list[str] | None = None, config_dir: str | None = None
) -> ProviderAwareLLMFacade:
    """Factory function to create provider-aware LLM facade with config-driven routing."""

    resolved_config_dir: str = config_dir if config_dir is not None else (os.getenv("OC_CONFIG_DIR") or "config")
    loader = ModelConfigLoader(resolved_config_dir)

    # Always include stub adapter for compatibility/tests
    from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

    static_adapters: dict[str, LLMPort] = {"stub": StubLLMAdapter()}
    adapter_factories: dict[str, Callable[[ResolvedModelConfig], LLMPort]] = {}

    # Determine which providers to wire
    if providers is None:
        providers = sorted(extract_providers_from_routing_config())
        if "stub" not in providers:
            providers.append("stub")
        # Also include providers discovered from model configs
        providers_from_configs = sorted(loader.providers())
        for p in providers_from_configs:
            if p not in providers:
                providers.append(p)

    provider_set = set(providers)

    def _make_openai_adapter(cfg: ResolvedModelConfig) -> LLMPort:
        from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

        return OpenAIAdapter(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)

    def _make_ollama_adapter(cfg: ResolvedModelConfig) -> LLMPort:
        from openchronicle.core.infrastructure.llm.ollama_adapter import OllamaAdapter

        return OllamaAdapter(model=cfg.model, base_url=cfg.base_url or cfg.endpoint)

    # Configure factories for providers found in configs
    providers_with_configs = sorted(loader.providers())
    for provider in providers_with_configs:
        if provider not in provider_set:
            continue
        if provider == "openai":
            adapter_factories[provider] = _make_openai_adapter
        elif provider == "ollama":
            adapter_factories[provider] = _make_ollama_adapter

    # Env-based wiring for providers without configs
    # Only wire env-based providers if they're NOT already configured via config files
    if providers:
        for provider in providers:
            if provider in adapter_factories or provider in static_adapters:
                continue  # Already configured via config file or static setup
            # Wire from env configuration for referenced providers without config files
            if provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    static_adapters[provider] = _make_openai_adapter(
                        ResolvedModelConfig(provider="openai", model="gpt-4o", api_key=api_key)
                    )
            elif provider == "ollama":
                # Ollama doesn't require API key, wire it up unconditionally
                static_adapters[provider] = _make_ollama_adapter(
                    ResolvedModelConfig(provider="ollama", model="default", endpoint=os.getenv("OLLAMA_HOST"))
                )

    default_provider_name = os.getenv("OC_LLM_PROVIDER", "").strip()
    available_for_default = set(static_adapters.keys()) | set(adapter_factories.keys())
    default_provider = default_provider_name if default_provider_name in available_for_default else None

    return ProviderAwareLLMFacade(
        adapters=static_adapters,
        config_loader=loader,
        adapter_factories=adapter_factories,
        default_provider=default_provider,
    )
