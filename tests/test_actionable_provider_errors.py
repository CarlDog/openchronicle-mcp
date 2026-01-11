"""
Test actionable provider configuration errors with structured hints.

Verifies that provider configuration failures include:
- Structured error fields (provider, configured_providers, hint)
- Provider-specific hints (OPENAI_API_KEY, pool configuration)
- Event propagation with full error context
"""

import pytest

from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.llm.provider_aware_facade import (
    ProviderAwareLLMFacade,
    create_provider_aware_llm,
)
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter


class TestActionableProviderErrors:
    """Test that provider configuration errors are actionable with hints."""

    @pytest.mark.asyncio
    async def test_provider_required_includes_hint_and_configured_providers(self) -> None:
        """When provider=None and no default, error includes hint and available providers."""
        facade = ProviderAwareLLMFacade(
            adapters={"stub": StubLLMAdapter(), "openai": StubLLMAdapter()},
            default_provider=None,
        )

        with pytest.raises(LLMProviderError) as exc_info:
            await facade.complete_async(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4",
                provider=None,
            )

        error = exc_info.value
        assert error.error_code == "provider_required"
        assert error.configured_providers == ["stub", "openai"]
        assert error.hint is not None
        assert "OC_LLM_PROVIDER" in error.hint
        assert "routing" in error.hint.lower()

    @pytest.mark.asyncio
    async def test_openai_not_configured_mentions_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When openai requested but not configured, hint mentions OPENAI_API_KEY."""
        # Ensure OPENAI_API_KEY is not set
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        facade = ProviderAwareLLMFacade(
            adapters={"stub": StubLLMAdapter()},
            default_provider=None,
        )

        with pytest.raises(LLMProviderError) as exc_info:
            await facade.complete_async(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4",
                provider="openai",
            )

        error = exc_info.value
        assert error.error_code == "provider_not_configured"
        assert error.provider == "openai"
        assert error.configured_providers == ["stub"]
        assert error.hint is not None
        assert "OPENAI_API_KEY" in error.hint

    @pytest.mark.asyncio
    async def test_ollama_not_configured_mentions_pool_wiring(self) -> None:
        """When ollama requested but not configured, hint mentions pool/wiring."""
        facade = ProviderAwareLLMFacade(
            adapters={"stub": StubLLMAdapter()},
            default_provider=None,
        )

        with pytest.raises(LLMProviderError) as exc_info:
            await facade.complete_async(
                messages=[{"role": "user", "content": "test"}],
                model="llama3",
                provider="ollama",
            )

        error = exc_info.value
        assert error.error_code == "provider_not_configured"
        assert error.provider == "ollama"
        assert error.configured_providers == ["stub"]
        assert error.hint is not None
        assert "pool" in error.hint.lower() or "wiring" in error.hint.lower()

    @pytest.mark.asyncio
    async def test_generic_provider_not_configured_includes_basic_hint(self) -> None:
        """Unknown provider gets generic hint about wiring."""
        facade = ProviderAwareLLMFacade(
            adapters={"stub": StubLLMAdapter()},
            default_provider=None,
        )

        with pytest.raises(LLMProviderError) as exc_info:
            await facade.complete_async(
                messages=[{"role": "user", "content": "test"}],
                model="model-x",
                provider="unknown_provider",
            )

        error = exc_info.value
        assert error.error_code == "provider_not_configured"
        assert error.provider == "unknown_provider"
        assert error.configured_providers == ["stub"]
        assert error.hint is not None
        assert "wiring" in error.hint.lower() or "initialization" in error.hint.lower()

    def test_error_fields_are_optional_and_backward_compatible(self) -> None:
        """LLMProviderError can be created without new fields (backward compatible)."""
        # Old-style creation (only message)
        error1 = LLMProviderError("Something went wrong")
        assert error1.error_code is None
        assert error1.provider is None
        assert error1.configured_providers == []
        assert error1.hint is None
        assert error1.details == {}

        # With error_code only
        error2 = LLMProviderError("Another error", error_code="custom_error")
        assert error2.error_code == "custom_error"
        assert error2.provider is None
        assert error2.hint is None

        # With all new fields
        error3 = LLMProviderError(
            "Full error",
            error_code="provider_not_configured",
            provider="openai",
            configured_providers=["stub", "ollama"],
            hint="Set OPENAI_API_KEY",
            details={"attempted_model": "gpt-4"},
        )
        assert error3.error_code == "provider_not_configured"
        assert error3.provider == "openai"
        assert error3.configured_providers == ["stub", "ollama"]
        assert error3.hint == "Set OPENAI_API_KEY"
        assert error3.details == {"attempted_model": "gpt-4"}

    def test_create_provider_aware_llm_skips_openai_when_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        When OPENAI_API_KEY is missing and routing config references openai,
        create_provider_aware_llm skips wiring but hint guides user.
        """
        # Setup: routing config references openai but no API key
        monkeypatch.setenv("OC_LLM_PROVIDER", "openai")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        facade = create_provider_aware_llm()

        # openai should NOT be wired (no API key)
        assert "openai" not in facade._adapters
        assert "stub" in facade._adapters  # stub always present

        # Attempting to use openai should fail with actionable hint
        with pytest.raises(LLMProviderError) as exc_info:
            import asyncio

            asyncio.run(
                facade.complete_async(
                    messages=[{"role": "user", "content": "test"}],
                    model="gpt-4",
                    provider="openai",
                )
            )

        error = exc_info.value
        assert error.error_code == "provider_not_configured"
        assert error.provider == "openai"
        assert error.hint is not None
        assert "OPENAI_API_KEY" in error.hint


class TestErrorHintPropagationInEvents:
    """Test that error hints and context propagate to events."""

    @pytest.mark.asyncio
    async def test_fallback_executor_includes_hint_in_events(self) -> None:
        """
        When LLMProviderError is raised, fallback executor includes hint
        and configured_providers in emitted events.
        """
        from openchronicle.core.application.routing.fallback_executor import FallbackExecutor
        from openchronicle.core.application.routing.pool_config import PoolConfig
        from openchronicle.core.domain.models.project import Event

        events_emitted = []

        def emit_event(event: Event) -> None:
            events_emitted.append(event)

        pool_config = PoolConfig(
            fast_pool=[],
            quality_pool=[],
            provider_weights={},
            max_fallbacks=3,
            fallback_on_transient=True,
            fallback_on_constraint=True,
            fallback_on_refusal=False,
        )
        executor = FallbackExecutor(emit_event=emit_event, pool_config=pool_config)

        # Create a provider error with hint
        error = LLMProviderError(
            "Provider 'openai' not configured",
            error_code="provider_not_configured",
            provider="openai",
            configured_providers=["stub"],
            hint="Set OPENAI_API_KEY environment variable to use OpenAI provider.",
        )

        # Emit failure event (simulating what fallback executor does)
        executor._emit_final_failure(
            exc=error,
            error_class="permanent",
            provider="openai",
            model="gpt-4",
            project_id="proj-1",
            task_id="task-1",
            agent_id="agent-1",
            execution_id="exec-123",
        )

        # Verify event contains hint and configured_providers
        assert len(events_emitted) == 1
        event = events_emitted[0]
        assert event.type == "llm.failed"
        assert event.payload["error_code"] == "provider_not_configured"
        assert event.payload["hint"] == "Set OPENAI_API_KEY environment variable to use OpenAI provider."
        assert event.payload["provider_requested"] == "openai"
        assert event.payload["configured_providers"] == ["stub"]
        assert event.payload["execution_id"] == "exec-123"

    @pytest.mark.asyncio
    async def test_attempt_failure_includes_hint_in_events(self) -> None:
        """Attempt-level failures include hint and provider context."""
        from openchronicle.core.application.routing.fallback_executor import FallbackExecutor
        from openchronicle.core.application.routing.pool_config import PoolConfig
        from openchronicle.core.domain.models.project import Event

        events_emitted = []

        def emit_event(event: Event) -> None:
            events_emitted.append(event)

        pool_config = PoolConfig(
            fast_pool=[],
            quality_pool=[],
            provider_weights={},
            max_fallbacks=3,
            fallback_on_transient=True,
            fallback_on_constraint=True,
            fallback_on_refusal=False,
        )
        executor = FallbackExecutor(emit_event=emit_event, pool_config=pool_config)

        error = LLMProviderError(
            "Provider 'ollama' not configured",
            error_code="provider_not_configured",
            provider="ollama",
            configured_providers=["stub", "openai"],
            hint="Ollama provider must be included in OC_LLM_FAST_POOL or OC_LLM_QUALITY_POOL.",
        )

        executor._emit_attempt_failure(
            exc=error,
            error_class="permanent",
            provider="ollama",
            model="llama3",
            project_id="proj-1",
            task_id="task-1",
            agent_id="agent-1",
        )

        assert len(events_emitted) == 1
        event = events_emitted[0]
        assert event.type == "llm.attempt_failed"
        assert event.payload["error_code"] == "provider_not_configured"
        assert event.payload["hint"] is not None
        assert "pool" in event.payload["hint"].lower() or "wiring" in event.payload["hint"].lower()
        assert event.payload["provider_requested"] == "ollama"
        assert event.payload["configured_providers"] == ["stub", "openai"]
