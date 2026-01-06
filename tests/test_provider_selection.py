"""Tests for LLM provider selection logic."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.models.project import TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage
from openchronicle.core.infrastructure.llm.provider_selector import LLMProviderSelector


class _FakeLLMSuccess(LLMPort):
    """Fake LLM that returns success responses."""

    def __init__(self, content: str = "fake summary", provider_name: str = "fake") -> None:
        self.content = content
        self.model = provider_name

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        usage = LLMUsage(input_tokens=5, output_tokens=3, total_tokens=8)
        return LLMResponse(
            content=self.content,
            provider=self.model,
            model=model,
            request_id="req-123",
            finish_reason="stop",
            usage=usage,
            latency_ms=12,
        )


@pytest.mark.asyncio
async def test_default_provider_is_stub(tmp_path: Path, monkeypatch: Any) -> None:
    """Without OC_LLM_PROVIDER set, defaults to stub even if OPENAI_API_KEY is present."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OC_LLM_PROVIDER", raising=False)

    container = CoreContainer(db_path=str(tmp_path / "default.db"))
    orchestrator = container.orchestrator

    project = orchestrator.create_project("Default")
    worker = orchestrator.register_agent(project_id=project.id, name="Worker", role="worker")

    task = orchestrator.submit_task(project.id, "analysis.worker.summarize", {"text": "Hello world"})
    result = await orchestrator.execute_task(task.id, agent_id=worker.id)

    # Stub returns truncated input
    assert result == "Hello world"

    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]

    # Should have llm.requested/completed events (stub still uses the LLM path)
    assert "llm.requested" in event_types
    assert "llm.completed" in event_types

    # Check provider is stub
    completed = next(e for e in events if e.type == "llm.completed")
    assert completed.payload.get("provider") == "stub"

    stored = container.storage.get_task(task.id)
    assert stored is not None and stored.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_explicit_openai_provider_with_key(tmp_path: Path, monkeypatch: Any) -> None:
    """With OC_LLM_PROVIDER=openai and OPENAI_API_KEY, uses fake OpenAI adapter."""
    monkeypatch.setenv("OC_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # Inject fake adapter to avoid network calls
    fake_llm = _FakeLLMSuccess(content="openai summary", provider_name="openai")
    container = CoreContainer(db_path=str(tmp_path / "openai.db"), llm=fake_llm)
    orchestrator = container.orchestrator

    project = orchestrator.create_project("OpenAI")
    worker = orchestrator.register_agent(project_id=project.id, name="Worker", role="worker")

    task = orchestrator.submit_task(project.id, "analysis.worker.summarize", {"text": "Hello world"})
    result = await orchestrator.execute_task(task.id, agent_id=worker.id)

    assert result == "openai summary"

    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]
    assert "llm.requested" in event_types
    assert "llm.completed" in event_types

    completed = next(e for e in events if e.type == "llm.completed")
    assert completed.payload.get("provider") == "openai"
    assert completed.payload.get("usage") == {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}

    stored = container.storage.get_task(task.id)
    assert stored is not None and stored.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_openai_provider_without_key_fails(tmp_path: Path, monkeypatch: Any) -> None:
    """With OC_LLM_PROVIDER=openai but no OPENAI_API_KEY, provider not configured."""
    monkeypatch.setenv("OC_LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # Container init succeeds, but openai won't be in available providers
    container = CoreContainer(db_path=str(tmp_path / "no-key.db"))
    project = container.orchestrator.create_project("NoKey")
    worker = container.orchestrator.register_agent(
        project_id=project.id, name="Worker", role="worker", provider="openai"
    )

    task = container.orchestrator.submit_task(project.id, "analysis.worker.summarize", {"text": "test"})

    # Should fail when trying to execute with openai provider not configured
    with pytest.raises(LLMProviderError, match="Provider 'openai' not configured"):
        await container.orchestrator.execute_task(task.id, agent_id=worker.id)


@pytest.mark.asyncio
async def test_provider_override_forces_provider(tmp_path: Path, monkeypatch: Any) -> None:
    """Runtime provider_override parameter forces provider selection."""
    monkeypatch.delenv("OC_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    # Inject fake to simulate openai
    fake_llm = _FakeLLMSuccess(content="override summary", provider_name="openai")
    container = CoreContainer(db_path=str(tmp_path / "override.db"), llm=fake_llm, provider_override="openai")
    orchestrator = container.orchestrator

    project = orchestrator.create_project("Override")
    worker = orchestrator.register_agent(project_id=project.id, name="Worker", role="worker")

    task = orchestrator.submit_task(project.id, "analysis.worker.summarize", {"text": "Hello world"})
    result = await orchestrator.execute_task(task.id, agent_id=worker.id)

    assert result == "override summary"

    events = container.storage.list_events(task.id)
    completed = next(e for e in events if e.type == "llm.completed")
    assert completed.payload.get("provider") == "openai"


def test_provider_selector_returns_stub_by_default(monkeypatch: Any) -> None:
    """LLMProviderSelector.get_provider_type() defaults to stub."""
    monkeypatch.delenv("OC_LLM_PROVIDER", raising=False)
    assert LLMProviderSelector.get_provider_type() == "stub"


def test_provider_selector_respects_env_var(monkeypatch: Any) -> None:
    """LLMProviderSelector.get_provider_type() respects OC_LLM_PROVIDER."""
    monkeypatch.setenv("OC_LLM_PROVIDER", "openai")
    assert LLMProviderSelector.get_provider_type() == "openai"

    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")
    assert LLMProviderSelector.get_provider_type() == "stub"


def test_provider_selector_override_takes_precedence(monkeypatch: Any) -> None:
    """Runtime override takes precedence over env var."""
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")
    assert LLMProviderSelector.get_provider_type(override="openai") == "openai"


def test_provider_selector_invalid_env_defaults_to_stub(monkeypatch: Any) -> None:
    """Invalid OC_LLM_PROVIDER value defaults to stub."""
    monkeypatch.setenv("OC_LLM_PROVIDER", "invalid")
    assert LLMProviderSelector.get_provider_type() == "stub"


def test_create_provider_stub(monkeypatch: Any) -> None:
    """LLMProviderSelector.create_provider creates stub adapter."""
    from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter

    provider = LLMProviderSelector.create_provider("stub")
    assert isinstance(provider, StubLLMAdapter)
    assert provider.model == "stub"


def test_create_provider_openai_requires_key(monkeypatch: Any) -> None:
    """LLMProviderSelector.create_provider fails without OPENAI_API_KEY."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(LLMProviderError, match="OPENAI_API_KEY environment variable is required"):
        LLMProviderSelector.create_provider("openai")


def test_create_provider_openai_with_key(monkeypatch: Any) -> None:
    """LLMProviderSelector.create_provider creates OpenAI adapter when key present."""
    from openchronicle.core.infrastructure.llm.openai_adapter import OpenAIAdapter

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    provider = LLMProviderSelector.create_provider("openai")
    assert isinstance(provider, OpenAIAdapter)
    assert provider.api_key == "test-key"
