from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.models.project import SpanStatus, TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse, LLMUsage


class _FakeLLMSuccess(LLMPort):
    def __init__(self, content: str = "fake summary") -> None:
        self.content = content

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
            provider="openai",
            model=model,
            request_id="req-123",
            finish_reason="stop",
            usage=usage,
            latency_ms=12,
        )


class _FakeLLMFailure(LLMPort):
    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        raise LLMProviderError("boom", status_code=500, error_code="server_error")


@pytest.mark.asyncio
async def test_worker_summarize_uses_stub_by_default(tmp_path: Path, monkeypatch: Any) -> None:
    """Without OC_LLM_PROVIDER or override, uses stub adapter."""

    monkeypatch.delenv("OC_LLM_PROVIDER", raising=False)
    container = CoreContainer(db_path=str(tmp_path / "stub-default.db"))
    orchestrator = container.orchestrator

    project = orchestrator.create_project("StubDefault")
    worker = orchestrator.register_agent(project_id=project.id, name="Worker", role="worker")

    task = orchestrator.submit_task(project.id, "analysis.worker.summarize", {"text": "Hello world"})
    result = await orchestrator.execute_task(task.id, agent_id=worker.id)

    assert result == "Hello world"

    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]
    assert "llm.requested" in event_types
    assert "llm.completed" in event_types

    # Check that provider is stub
    completed = next(e for e in events if e.type == "llm.completed")
    assert completed.payload.get("provider") == "stub"

    stored = container.storage.get_task(task.id)
    assert stored is not None and stored.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_worker_summarize_uses_injected_fake_adapter(tmp_path: Path, monkeypatch: Any) -> None:
    """With injected fake adapter, llm events and usage are recorded."""

    fake_llm = _FakeLLMSuccess(content="summarized text")
    container = CoreContainer(db_path=str(tmp_path / "llm-success.db"), llm=fake_llm)
    orchestrator = container.orchestrator

    project = orchestrator.create_project("LLM")
    worker = orchestrator.register_agent(project_id=project.id, name="Worker", role="worker")

    task = orchestrator.submit_task(project.id, "analysis.worker.summarize", {"text": "Hello world"})
    result = await orchestrator.execute_task(task.id, agent_id=worker.id)

    assert result == "summarized text"

    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]
    assert "llm.requested" in event_types
    assert "llm.completed" in event_types

    completed = next(e for e in events if e.type == "llm.completed")
    assert completed.payload.get("usage") == {"input_tokens": 5, "output_tokens": 3, "total_tokens": 8}

    stored = container.storage.get_task(task.id)
    assert stored is not None and stored.status == TaskStatus.COMPLETED
    assert json.loads(stored.result_json or "{}") in (
        "summarized text",
        {"value": "summarized text"},
        {"summary": "summarized text"},
    )


@pytest.mark.asyncio
async def test_worker_summarize_llm_failure_marks_task_failed(tmp_path: Path) -> None:
    """LLM provider errors emit llm.failed and fail the task atomically."""

    fake_llm = _FakeLLMFailure()
    container = CoreContainer(db_path=str(tmp_path / "llm-fail.db"), llm=fake_llm)
    orchestrator = container.orchestrator

    project = orchestrator.create_project("LLM Fail")
    worker = orchestrator.register_agent(project_id=project.id, name="Worker", role="worker")

    task = orchestrator.submit_task(project.id, "analysis.worker.summarize", {"text": "Hello world"})

    with pytest.raises(LLMProviderError):
        await orchestrator.execute_task(task.id, agent_id=worker.id)

    stored = container.storage.get_task(task.id)
    assert stored is not None and stored.status == TaskStatus.FAILED
    assert stored.error_json is not None

    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]
    assert "llm.requested" in event_types
    assert "llm.failed" in event_types
    assert "task_failed" in event_types

    spans = container.storage.list_spans(task.id)
    assert spans
    assert spans[0].status == SpanStatus.FAILED
    assert spans[0].end_event_id == next(e.id for e in events if e.type == "task_failed")
