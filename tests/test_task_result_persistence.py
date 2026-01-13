"""Tests for task result and error persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.models.project import Task, TaskStatus
from openchronicle.core.domain.services.replay import ReplayMode, ReplayService


@pytest.fixture
def container() -> CoreContainer:
    """Create a fresh container with isolated database for each test."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test.db"
    return CoreContainer(db_path=str(db_path))


@pytest.mark.asyncio
async def test_task_result_persisted_on_success(container: CoreContainer) -> None:
    """Test that successful task execution persists result_json."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Result Persistence Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Run a task
    task = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Test persistence"})
    result = await orchestrator.execute_task(task.id, agent_id=supervisor.id)

    # Verify result was persisted
    persisted_task = container.storage.get_task(task.id)
    assert persisted_task is not None, "Task should exist"
    assert persisted_task.result_json is not None, "result_json should be set"
    assert persisted_task.status == TaskStatus.COMPLETED, "Task should be completed"

    # Parse and verify result content
    stored_result = json.loads(persisted_task.result_json)
    assert "summary" in stored_result, "Result should contain summary key"
    assert "worker_summaries" in stored_result, "Result should contain worker_summaries"

    # Verify result matches execution result
    assert stored_result == result, "Stored result should match execution result"


@pytest.mark.asyncio
async def test_task_error_persisted_on_failure(container: CoreContainer) -> None:
    """Test that failed task execution persists error_json."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Error Persistence Test")
    agent = orchestrator.register_agent(
        project_id=project.id, name="TestAgent", role="worker", provider="stub", model="stub-model"
    )

    # Register a handler that always fails
    async def failing_handler(task: Task, context: dict | None) -> str:
        raise ValueError("Intentional test failure")

    orchestrator.handler_registry.register("test.fail", failing_handler)

    # Submit and execute the failing task
    task = orchestrator.submit_task(project.id, "test.fail", {"text": "This will fail"})

    with pytest.raises(ValueError, match="Intentional test failure"):
        await orchestrator.execute_task(task.id, agent_id=agent.id)

    # Verify error was persisted
    persisted_task = container.storage.get_task(task.id)
    assert persisted_task is not None, "Task should exist"
    assert persisted_task.error_json is not None, "error_json should be set"
    assert persisted_task.status == TaskStatus.FAILED, "Task should be failed"
    assert persisted_task.result_json is None, "result_json should not be set on failure"

    # Parse and verify error content
    stored_error = json.loads(persisted_task.error_json)
    assert "exception_type" in stored_error, "Error should contain exception_type"
    assert stored_error["exception_type"] == "ValueError", "Should capture ValueError"
    assert "message" in stored_error, "Error should contain message"
    assert "Intentional test failure" in stored_error["message"], "Should capture error message"
    assert "failed_event_id" in stored_error, "Error should contain failed_event_id"

    # Verify task_failed event exists
    events = container.storage.list_events(task.id)
    failed_events = [e for e in events if e.type == "task_failed"]
    assert len(failed_events) == 1, "Should have exactly one task_failed event"

    # Verify span is linked to failed event
    spans = container.storage.list_spans(task.id)
    assert len(spans) == 1, "Should have exactly one span"
    assert spans[0].end_event_id == failed_events[0].id, "Span should link to failed event"


@pytest.mark.asyncio
async def test_replay_uses_stored_result_fast_path(container: CoreContainer) -> None:
    """Test that ReplayService uses stored result_json (fast path)."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Replay Fast Path Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Run a task
    task = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Fast path test"})
    execution_result = await orchestrator.execute_task(task.id, agent_id=supervisor.id)

    # Get stored result
    persisted_task = container.storage.get_task(task.id)
    assert persisted_task is not None
    assert persisted_task.result_json is not None
    stored_result = json.loads(persisted_task.result_json)

    # Replay using ReplayService
    replay_service = ReplayService(container.storage)
    replay_result = replay_service.replay_task(task.id, ReplayMode.REPLAY_EVENTS)

    assert replay_result.success, "Replay should succeed"
    assert replay_result.reconstructed_output is not None, "Should have reconstructed output"

    # Verify replay returned the stored result (fast path was used)
    assert replay_result.reconstructed_output == stored_result, "Replay should return stored result"
    assert replay_result.reconstructed_output == execution_result, "Should match original execution"


@pytest.mark.asyncio
async def test_list_tasks_deterministic_ordering(container: CoreContainer) -> None:
    """Test that list_tasks_by_project returns tasks in deterministic order."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Ordering Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Create two tasks (each creates 3 total: 1 main + 2 worker sub-tasks)
    task1 = orchestrator.submit_task(project.id, "analysis.summary", {"text": "First task"})
    await orchestrator.execute_task(task1.id, agent_id=supervisor.id)

    task2 = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Second task"})
    await orchestrator.execute_task(task2.id, agent_id=supervisor.id)

    # Get all tasks
    all_tasks = container.storage.list_tasks_by_project(project.id)

    # Verify ordering (should be created_at ASC, id ASC)
    assert len(all_tasks) == 6, "Should have 6 tasks total (2 main + 4 worker sub-tasks)"

    # First task should be task1
    assert all_tasks[0].id == task1.id, "First task should be task1"

    # Verify tasks are in chronological order
    for i in range(len(all_tasks) - 1):
        assert (
            all_tasks[i].created_at <= all_tasks[i + 1].created_at
        ), f"Tasks should be ordered by created_at (task {i} vs {i + 1})"

    # Verify all tasks have results or errors
    for task in all_tasks:
        if task.status == TaskStatus.COMPLETED:
            assert task.result_json is not None, f"Completed task {task.id} should have result_json"
        elif task.status == TaskStatus.FAILED:
            assert task.error_json is not None, f"Failed task {task.id} should have error_json"


@pytest.mark.asyncio
async def test_replay_fallback_when_no_stored_result(container: CoreContainer) -> None:
    """Test that replay falls back to event reconstruction if result_json is missing."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Replay Fallback Test")
    supervisor = orchestrator.register_agent(
        project_id=project.id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker1", role="worker", provider="stub", model="stub-model"
    )
    orchestrator.register_agent(
        project_id=project.id, name="Worker2", role="worker", provider="stub", model="stub-model"
    )

    # Run a task
    task = orchestrator.submit_task(project.id, "analysis.summary", {"text": "Fallback test"})
    execution_result = await orchestrator.execute_task(task.id, agent_id=supervisor.id)

    # Manually clear the stored result to simulate old data

    conn = container.storage._conn
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET result_json = NULL WHERE id = ?", (task.id,))
    conn.commit()

    # Verify result was cleared
    persisted_task = container.storage.get_task(task.id)
    assert persisted_task is not None
    assert persisted_task.result_json is None, "result_json should be cleared"

    # Replay should still work by reconstructing from events
    replay_service = ReplayService(container.storage)
    replay_result = replay_service.replay_task(task.id, ReplayMode.REPLAY_EVENTS)

    assert replay_result.success, "Replay should succeed via fallback"
    assert replay_result.reconstructed_output is not None, "Should have reconstructed output"
    assert replay_result.reconstructed_output == execution_result, "Should match original execution via events"
