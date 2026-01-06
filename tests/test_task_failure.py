"""Tests for task failure handling and span linking."""

from __future__ import annotations

from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.models.project import SpanStatus, Task, TaskStatus


@pytest.fixture
def container() -> CoreContainer:
    """Create a fresh container for each test."""
    return CoreContainer()


@pytest.mark.asyncio
async def test_task_failure_emits_event_and_updates_span(container: CoreContainer) -> None:
    """Test that task failures emit task_failed event and link spans properly."""
    # Create a project
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Task Failure Test")
    agent = orchestrator.register_agent(
        project_id=project.id, name="TestAgent", role="worker", provider="stub", model="stub-model"
    )

    # Register a handler that always fails
    async def failing_handler(task: Task, context: dict[str, Any] | None) -> str:
        raise ValueError("Intentional test failure")

    orchestrator.handler_registry.register("test.fail", failing_handler)

    # Submit and execute the failing task
    task = orchestrator.submit_task(project.id, "test.fail", {"text": "This will fail"})

    with pytest.raises(ValueError, match="Intentional test failure"):
        await orchestrator.execute_task(task.id, agent_id=agent.id)

    # Verify task status is FAILED
    updated_task = container.storage.get_task(task.id)
    assert updated_task is not None
    assert updated_task.status == TaskStatus.FAILED, "Task status should be FAILED"

    # Verify task_failed event exists
    events = container.storage.list_events(task.id)
    failed_events = [e for e in events if e.type == "task_failed"]
    assert len(failed_events) == 1, "Should have exactly one task_failed event"

    failed_event = failed_events[0]
    assert "exception_type" in failed_event.payload, "Should include exception type"
    assert failed_event.payload["exception_type"] == "ValueError", "Should capture correct exception type"
    assert "message" in failed_event.payload, "Should include error message"
    assert "Intentional test failure" in failed_event.payload["message"], "Should capture error message"

    # Verify span is marked as FAILED and linked to task_failed event
    spans = container.storage.list_spans(task.id)
    assert len(spans) == 1, "Should have exactly one span"

    span = spans[0]
    assert span.status == SpanStatus.FAILED, "Span should be marked as FAILED"
    assert span.end_event_id == failed_event.id, "Span should link to task_failed event"
    assert span.ended_at is not None, "Span should have ended_at timestamp"
    assert span.ended_at == failed_event.created_at, "Span ended_at should match event timestamp"


@pytest.mark.asyncio
async def test_successful_task_has_no_failed_event(container: CoreContainer) -> None:
    """Test that successful tasks don't emit task_failed events."""
    # Create a project and run a successful task
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Success Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    task = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Success test"})
    await orchestrator.execute_task(task.id, agent_id=supervisor.id)

    # Verify no task_failed events
    events = container.storage.list_events(task.id)
    failed_events = [e for e in events if e.type == "task_failed"]
    assert len(failed_events) == 0, "Successful task should not have task_failed event"

    # Verify task status is COMPLETED
    updated_task = container.storage.get_task(task.id)
    assert updated_task is not None
    assert updated_task.status == TaskStatus.COMPLETED, "Task status should be COMPLETED"

    # Verify span is marked as COMPLETED
    spans = container.storage.list_spans(task.id)
    assert len(spans) == 1, "Should have exactly one span"
    assert spans[0].status == SpanStatus.COMPLETED, "Span should be COMPLETED"
