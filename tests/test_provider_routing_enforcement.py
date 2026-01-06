"""Tests for provider-aware routing enforcement."""

from __future__ import annotations

from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.models.project import TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage
from openchronicle.core.infrastructure.llm.provider_aware_facade import ProviderAwareLLMFacade


class FakeOpenAIAdapter(LLMPort):
    """Fake OpenAI adapter for testing."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "provider": provider,
                "max_output_tokens": max_output_tokens,
                "temperature": temperature,
            }
        )
        return LLMResponse(
            provider="openai",
            model=model,
            content="OpenAI response",
            finish_reason="stop",
            usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )


class FakeStubAdapter(LLMPort):
    """Fake Stub adapter for testing."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "provider": provider,
                "max_output_tokens": max_output_tokens,
                "temperature": temperature,
            }
        )
        return LLMResponse(
            provider="stub",
            model=model,
            content="Stub response",
            finish_reason="stop",
            usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        )


@pytest.mark.asyncio
async def test_routing_enforces_provider_selection() -> None:
    """Test that routing decisions affect runtime execution."""
    # Arrange: Create two fake adapters
    fake_openai = FakeOpenAIAdapter()
    fake_stub = FakeStubAdapter()

    # Create facade with both providers
    facade = ProviderAwareLLMFacade({"openai": fake_openai, "stub": fake_stub})

    # Create container with facade
    container = CoreContainer(db_path=":memory:", llm=facade)
    project = container.orchestrator.create_project("Provider Test")

    # Register agent with quality tag and openai provider
    agent = container.orchestrator.register_agent(
        project.id, "OpenAI Agent", role="worker", provider="openai", tags=["quality"]
    )

    # Act: Execute a worker task with quality mode (should route to openai)
    task = container.orchestrator.submit_task(
        project_id=project.id,
        task_type="analysis.worker.summarize",
        payload={"text": "Test routing enforcement", "desired_quality": "quality"},
    )

    await container.orchestrator.execute_task(task.id, agent_id=agent.id)

    # Assert: Only openai adapter was called
    assert len(fake_openai.calls) >= 1, f"OpenAI adapter should be called, but got {len(fake_openai.calls)} calls"
    assert fake_openai.calls[0]["provider"] == "openai", "Provider parameter should be 'openai'"

    # Verify task completed
    final_task = container.storage.get_task(task.id)
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED

    # Verify llm.completed event has correct provider
    events = container.storage.list_events(task.id)
    completed_events = [e for e in events if e.type == "llm.completed"]
    assert len(completed_events) >= 1
    assert completed_events[0].payload["provider"] == "openai"


@pytest.mark.asyncio
async def test_provider_not_configured_fails_cleanly() -> None:
    """Test that selecting unconfigured provider fails explicitly."""
    # Arrange: Create facade with only stub provider
    fake_stub = FakeStubAdapter()
    facade = ProviderAwareLLMFacade({"stub": fake_stub})

    # Container created but not used - just testing facade directly
    _ = CoreContainer(db_path=":memory:", llm=facade)

    # Act & Assert: Try to call with openai provider directly (not configured)
    # This should fail immediately
    with pytest.raises(LLMProviderError) as exc_info:
        await facade.complete_async(
            messages=[{"role": "user", "content": "test"}],
            model="gpt-4",
            provider="openai",
        )

    # Verify error is explicit and explains the problem
    assert "openai" in str(exc_info.value).lower()
    assert "not configured" in str(exc_info.value).lower() or "available" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_stub_provider_always_available() -> None:
    """Test that stub provider is always available as fallback."""
    # Arrange: Create facade with only stub
    fake_stub = FakeStubAdapter()
    facade = ProviderAwareLLMFacade({"stub": fake_stub})

    container = CoreContainer(db_path=":memory:", llm=facade)
    project = container.orchestrator.create_project("Stub Test")
    agent = container.orchestrator.register_agent(project.id, "Stub Agent", role="worker")

    # Act: Execute worker task
    task = container.orchestrator.submit_task(
        project_id=project.id,
        task_type="analysis.worker.summarize",
        payload={"text": "Test stub provider"},
    )

    result = await container.orchestrator.execute_task(task.id, agent_id=agent.id)

    # Assert: Task completed successfully
    assert result is not None
    assert len(fake_stub.calls) == 1

    final_task = container.storage.get_task(task.id)
    assert final_task is not None
    assert final_task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_provider_mismatch_emits_event() -> None:
    """Test that provider mismatch between routing and execution is detected."""

    # Create a malicious adapter that lies about its provider
    class LyingAdapter(LLMPort):
        async def complete_async(
            self,
            messages: list[dict[str, Any]],
            *,
            model: str,
            max_output_tokens: int | None = None,
            temperature: float | None = None,
            provider: str | None = None,
        ) -> LLMResponse:
            # Claims to be requested provider but returns stub response
            return LLMResponse(
                provider="stub",  # Mismatch!
                model=model,
                content="Lying response",
                finish_reason="stop",
                usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
            )

    # Arrange
    lying_adapter = LyingAdapter()
    stub_adapter = FakeStubAdapter()
    facade = ProviderAwareLLMFacade({"openai": lying_adapter, "stub": stub_adapter})

    container = CoreContainer(db_path=":memory:", llm=facade)
    project = container.orchestrator.create_project("Mismatch Test")
    agent = container.orchestrator.register_agent(
        project.id, "Test Agent", role="worker", provider="openai", tags=["quality"]
    )

    # Act: Execute worker task
    task = container.orchestrator.submit_task(
        project_id=project.id,
        task_type="analysis.worker.summarize",
        payload={"text": "Test mismatch detection", "desired_quality": "quality"},
    )

    await container.orchestrator.execute_task(task.id, agent_id=agent.id)

    # Assert: Mismatch event was emitted
    events = container.storage.list_events(task.id)
    mismatch_events = [e for e in events if e.type == "llm.provider_mismatch"]
    assert len(mismatch_events) == 1, "Provider mismatch event should be emitted"

    mismatch_payload = mismatch_events[0].payload
    assert mismatch_payload["provider_selected"] == "openai"
    assert mismatch_payload["provider_used"] == "stub"
