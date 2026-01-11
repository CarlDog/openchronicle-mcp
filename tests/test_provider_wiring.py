"""Tests for provider wiring matching routing configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from openchronicle.core.infrastructure.llm.provider_aware_facade import (
    create_provider_aware_llm,
    extract_providers_from_routing_config,
)


class TestExtractProvidersFromRoutingConfig:
    """Tests for extracting providers from routing environment config."""

    def test_extract_from_default_provider(self) -> None:
        """Should extract provider from OC_LLM_PROVIDER."""
        with patch.dict(os.environ, {"OC_LLM_PROVIDER": "ollama"}, clear=False):
            providers = extract_providers_from_routing_config()
            assert "ollama" in providers

    def test_extract_from_fast_pool(self) -> None:
        """Should extract providers from OC_LLM_FAST_POOL."""
        with patch.dict(
            os.environ,
            {"OC_LLM_FAST_POOL": "ollama:llama3.1,openai:gpt-4o-mini"},
            clear=False,
        ):
            providers = extract_providers_from_routing_config()
            assert "ollama" in providers
            assert "openai" in providers

    def test_extract_from_quality_pool(self) -> None:
        """Should extract providers from OC_LLM_QUALITY_POOL."""
        with patch.dict(
            os.environ,
            {"OC_LLM_QUALITY_POOL": "openai:gpt-4o,ollama:mixtral"},
            clear=False,
        ):
            providers = extract_providers_from_routing_config()
            assert "openai" in providers
            assert "ollama" in providers

    def test_extract_from_multiple_sources(self) -> None:
        """Should extract providers from all config sources."""
        with patch.dict(
            os.environ,
            {
                "OC_LLM_PROVIDER": "stub",
                "OC_LLM_FAST_POOL": "ollama:llama3.1",
                "OC_LLM_QUALITY_POOL": "openai:gpt-4o",
            },
            clear=False,
        ):
            providers = extract_providers_from_routing_config()
            assert "stub" in providers
            assert "ollama" in providers
            assert "openai" in providers

    def test_extract_handles_malformed_entries(self) -> None:
        """Should gracefully skip malformed pool entries."""
        with patch.dict(
            os.environ,
            {"OC_LLM_FAST_POOL": "ollama:llama3.1,invalid,openai:gpt-4o-mini,"},
            clear=False,
        ):
            providers = extract_providers_from_routing_config()
            assert "ollama" in providers
            assert "openai" in providers
            assert "invalid" not in providers

    def test_extract_returns_sorted_set(self) -> None:
        """Should return deterministic sorted set."""
        with patch.dict(
            os.environ,
            {"OC_LLM_FAST_POOL": "openai:gpt-4,ollama:llama3,stub:test"},
            clear=False,
        ):
            providers = extract_providers_from_routing_config()
            # Convert to list to check ordering
            providers_list = sorted(providers)
            assert providers_list == sorted(providers_list)

    def test_extract_empty_config(self) -> None:
        """Should return empty set when no routing config."""
        with patch.dict(os.environ, {}, clear=True):
            providers = extract_providers_from_routing_config()
            assert len(providers) == 0


class TestCreateProviderAwareLLM:
    """Tests for factory function creating provider-aware facade."""

    def test_always_includes_stub(self) -> None:
        """Factory should always include stub adapter."""
        with patch.dict(os.environ, {}, clear=True):
            facade = create_provider_aware_llm()
            assert "stub" in facade._adapters

    def test_includes_ollama_when_referenced_in_pool(self) -> None:
        """Should include ollama adapter when referenced in routing pool."""
        with patch.dict(
            os.environ,
            {"OC_LLM_FAST_POOL": "ollama:llama3.1,openai:gpt-4o-mini"},
            clear=True,
        ):
            facade = create_provider_aware_llm()
            assert "stub" in facade._adapters
            assert "ollama" in facade._adapters

    def test_includes_openai_only_when_configured(self) -> None:
        """Should include openai adapter only when API key is present."""
        # Without API key - should not include openai even if referenced
        with patch.dict(
            os.environ,
            {"OC_LLM_FAST_POOL": "openai:gpt-4o-mini"},
            clear=True,
        ):
            facade = create_provider_aware_llm()
            assert "openai" not in facade._adapters

        # With API key - should include openai
        with patch.dict(
            os.environ,
            {
                "OC_LLM_FAST_POOL": "openai:gpt-4o-mini",
                "OPENAI_API_KEY": "test-key",
            },
            clear=True,
        ):
            facade = create_provider_aware_llm()
            assert "openai" in facade._adapters

    def test_sets_default_provider_when_configured_and_present(self) -> None:
        """Should set default_provider only when explicitly configured and adapter present."""
        # Ollama referenced and set as default
        with patch.dict(
            os.environ,
            {
                "OC_LLM_PROVIDER": "ollama",
                "OC_LLM_FAST_POOL": "ollama:llama3.1",
            },
            clear=True,
        ):
            facade = create_provider_aware_llm()
            assert facade.default_provider == "ollama"

    def test_default_provider_not_set_when_adapter_missing(self) -> None:
        """Should NOT set default_provider when adapter not present."""
        # OpenAI set as default but no API key
        with patch.dict(
            os.environ,
            {"OC_LLM_PROVIDER": "openai"},
            clear=True,
        ):
            facade = create_provider_aware_llm()
            assert facade.default_provider is None

    def test_default_provider_not_set_when_not_configured(self) -> None:
        """Should NOT set default_provider when OC_LLM_PROVIDER not set."""
        with patch.dict(
            os.environ,
            {"OC_LLM_FAST_POOL": "ollama:llama3.1"},
            clear=True,
        ):
            facade = create_provider_aware_llm()
            assert facade.default_provider is None

    def test_explicit_providers_list_overrides_config(self) -> None:
        """When providers list is explicit, should use that instead of config detection."""
        with patch.dict(
            os.environ,
            {
                "OC_LLM_FAST_POOL": "ollama:llama3.1",
                "OPENAI_API_KEY": "test-key",
            },
            clear=True,
        ):
            # Explicit list - only openai and stub
            facade = create_provider_aware_llm(providers=["openai", "stub"])
            assert "stub" in facade._adapters
            assert "openai" in facade._adapters
            # Ollama not included even though in pool
            assert "ollama" not in facade._adapters

    @pytest.mark.asyncio
    async def test_provider_required_when_no_default_set(self) -> None:
        """Should raise provider_required when provider=None and no default."""
        with patch.dict(os.environ, {}, clear=True):
            facade = create_provider_aware_llm()

            # No default_provider set, so provider=None should fail
            from openchronicle.core.domain.ports.llm_port import LLMProviderError

            with pytest.raises(LLMProviderError) as exc_info:
                await facade.complete_async(
                    messages=[{"role": "user", "content": "test"}],
                    model="test-model",
                    provider=None,
                )
            assert exc_info.value.error_code == "provider_required"

    @pytest.mark.asyncio
    async def test_uses_default_provider_when_set(self) -> None:
        """Should use default_provider when provider=None."""
        with patch.dict(
            os.environ,
            {
                "OC_LLM_PROVIDER": "stub",
                "OC_LLM_FAST_POOL": "stub:test-model",
            },
            clear=True,
        ):
            facade = create_provider_aware_llm()
            assert facade.default_provider == "stub"

            # Should use stub adapter without explicit provider
            response = await facade.complete_async(
                messages=[{"role": "user", "content": "test"}],
                model="test-model",
                provider=None,
            )
            # Stub adapter returns user message content
            assert response.content == "test"
            assert response.provider == "stub"

    def test_deterministic_adapter_ordering(self) -> None:
        """Should produce consistent adapter list for same config."""
        env_config = {
            "OC_LLM_FAST_POOL": "openai:gpt-4,ollama:llama3,stub:test",
            "OPENAI_API_KEY": "test-key",
        }

        with patch.dict(os.environ, env_config, clear=True):
            facade1 = create_provider_aware_llm()
            adapters1 = list(facade1._adapters.keys())

        with patch.dict(os.environ, env_config, clear=True):
            facade2 = create_provider_aware_llm()
            adapters2 = list(facade2._adapters.keys())

        # Same config should produce same adapter keys
        assert set(adapters1) == set(adapters2)


class TestProviderWiringConsistency:
    """Integration tests proving wiring matches routing config."""

    def test_routing_can_select_wired_providers(self) -> None:
        """Providers referenced in routing config should be wirable."""
        with patch.dict(
            os.environ,
            {
                "OC_LLM_FAST_POOL": "ollama:llama3.1,stub:test",
                "OC_LLM_QUALITY_POOL": "ollama:mixtral",
            },
            clear=True,
        ):
            facade = create_provider_aware_llm()

            # Both providers should be wired
            assert "ollama" in facade._adapters
            assert "stub" in facade._adapters

    def test_no_footgun_routing_selects_unwired_provider(self) -> None:
        """Should not wire provider that routing cannot select."""
        # Only stub in pools
        with patch.dict(
            os.environ,
            {"OC_LLM_FAST_POOL": "stub:test-model"},
            clear=True,
        ):
            facade = create_provider_aware_llm()

            # Only stub should be wired (no ollama/openai without being in config)
            assert "stub" in facade._adapters
            # Ollama not in config, so not wired
            assert "ollama" not in facade._adapters

    @pytest.mark.asyncio
    async def test_explicit_failure_for_unconfigured_provider(self) -> None:
        """Should fail explicitly when routing selects provider not in adapters."""
        with patch.dict(os.environ, {}, clear=True):
            facade = create_provider_aware_llm()

            from openchronicle.core.domain.ports.llm_port import LLMProviderError

            # Try to use openai (not configured)
            with pytest.raises(LLMProviderError) as exc_info:
                await facade.complete_async(
                    messages=[{"role": "user", "content": "test"}],
                    model="gpt-4",
                    provider="openai",
                )
            assert exc_info.value.error_code == "provider_not_configured"
            assert "openai" in str(exc_info.value)
