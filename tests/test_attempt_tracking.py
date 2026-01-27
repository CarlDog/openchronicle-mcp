"""Tests for task execution attempt tracking.

Verifies that:
- attempt_id is generated once per task execution
- attempt_id propagates through task lifecycle events
- attempt_id propagates to llm.execution_recorded events
- ReplayService can distinguish multiple attempts of the same task
"""

from __future__ import annotations

from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases.replay_project import ReplayService
from openchronicle.core.domain.models.project import Event, Task


@pytest.fixture
def container(tmp_path: Any) -> CoreContainer:
    """Create a fresh container for each test."""
    db_path = tmp_path / "test.db"
    return CoreContainer(db_path=str(db_path))


@pytest.fixture
def project_id(container: CoreContainer) -> str:
    """Create a project and return its ID."""
    project = container.orchestrator.create_project("Attempt Tracking Test")
    return project.id


class TestAttemptIdGeneration:
    """Test that attempt_id is generated and consistent within a single execution."""

    @pytest.mark.asyncio
    async def test_attempt_id_in_task_started_event(self, container: CoreContainer, project_id: str) -> None:
        """task.started event should contain attempt_id."""
        # Arrange
        task = container.orchestrator.submit_task(project_id, "test.task", {"data": "test"})

        # Register a simple handler
        async def simple_handler(t: Task, context: dict[str, Any] | None) -> str:
            return "done"

        container.orchestrator.handler_registry.register("test.task", simple_handler)

        # Act
        await container.orchestrator.execute_task(task.id)

        # Assert: task.started event exists with attempt_id
        events = container.storage.list_events(task_id=task.id)
        started_events = [e for e in events if e.type == "task_started"]
        assert len(started_events) == 1, "Should have exactly one task_started event"

        started_event = started_events[0]
        assert "attempt_id" in started_event.payload, "task_started should contain attempt_id"
        assert isinstance(started_event.payload["attempt_id"], str), "attempt_id should be a string"
        assert len(started_event.payload["attempt_id"]) == 32, "attempt_id should be uuid4().hex (32 chars)"

    @pytest.mark.asyncio
    async def test_attempt_id_in_task_completed_event(self, container: CoreContainer, project_id: str) -> None:
        """task.completed event should contain the same attempt_id as task.started."""
        # Arrange
        task = container.orchestrator.submit_task(project_id, "test.task", {"data": "test"})

        async def simple_handler(t: Task, context: dict[str, Any] | None) -> str:
            return "success"

        container.orchestrator.handler_registry.register("test.task", simple_handler)

        # Act
        await container.orchestrator.execute_task(task.id)

        # Assert: task.completed has same attempt_id as task.started
        events = container.storage.list_events(task_id=task.id)
        started_events = [e for e in events if e.type == "task_started"]
        completed_events = [e for e in events if e.type == "task_completed"]

        assert len(started_events) == 1
        assert len(completed_events) == 1

        started_attempt_id = started_events[0].payload["attempt_id"]
        completed_attempt_id = completed_events[0].payload["attempt_id"]

        assert started_attempt_id == completed_attempt_id, "task.completed should have same attempt_id as task.started"

    @pytest.mark.asyncio
    async def test_attempt_id_in_task_failed_event(self, container: CoreContainer, project_id: str) -> None:
        """task.failed event should contain the same attempt_id as task.started."""
        # Arrange
        task = container.orchestrator.submit_task(project_id, "test.fail", {"data": "test"})

        async def failing_handler(t: Task, context: dict[str, Any] | None) -> str:
            raise ValueError("Intentional failure")

        container.orchestrator.handler_registry.register("test.fail", failing_handler)

        # Act
        with pytest.raises(ValueError, match="Intentional failure"):
            await container.orchestrator.execute_task(task.id)

        # Assert: task.failed has same attempt_id as task.started
        events = container.storage.list_events(task_id=task.id)
        started_events = [e for e in events if e.type == "task_started"]
        failed_events = [e for e in events if e.type == "task_failed"]

        assert len(started_events) == 1
        assert len(failed_events) == 1

        started_attempt_id = started_events[0].payload["attempt_id"]
        failed_attempt_id = failed_events[0].payload["attempt_id"]

        assert started_attempt_id == failed_attempt_id, "task.failed should have same attempt_id as task.started"


class TestAttemptIdPropagation:
    """Test that attempt_id propagates to related events like llm.execution_recorded."""

    @pytest.mark.asyncio
    async def test_attempt_id_propagates_to_llm_execution_recorded(
        self, container: CoreContainer, project_id: str
    ) -> None:
        """llm.execution_recorded event should contain attempt_id when tied to a task."""
        # Arrange: Create a worker task that will make an LLM call
        container.orchestrator.register_agent(
            project_id=project_id, name="Supervisor", role="supervisor", provider="stub", model="stub-model"
        )
        worker = container.orchestrator.register_agent(
            project_id=project_id, name="Worker1", role="worker", provider="stub", model="stub-model"
        )

        task = container.orchestrator.submit_task(
            project_id, "analysis.worker.summarize", {"text": "Test text", "desired_quality": "fast"}
        )

        # Act: Execute task (will make LLM call via builtin handler)
        await container.orchestrator.execute_task(task.id, agent_id=worker.id)

        # Assert: llm.execution_recorded contains attempt_id
        events = container.storage.list_events(task_id=task.id)
        started_events = [e for e in events if e.type == "task_started"]
        llm_recorded_events = [e for e in events if e.type == "llm.execution_recorded"]

        assert len(started_events) == 1, "Should have task_started event"
        assert len(llm_recorded_events) >= 1, "Should have at least one llm.execution_recorded event"

        started_attempt_id = started_events[0].payload["attempt_id"]

        # Check that all llm.execution_recorded events have the same attempt_id
        for llm_event in llm_recorded_events:
            assert "attempt_id" in llm_event.payload, (
                f"llm.execution_recorded should contain attempt_id: {llm_event.payload}"
            )
            assert llm_event.payload["attempt_id"] == started_attempt_id, (
                "llm.execution_recorded should have same attempt_id as task.started"
            )


class TestMultipleAttempts:
    """Test that multiple attempts of the same task are distinguishable."""

    def test_same_task_two_attempts(self, container: CoreContainer, project_id: str) -> None:
        """ReplayService should distinguish two attempts of the same task."""
        # Arrange: Create a task and emit events for two attempts
        task = container.orchestrator.submit_task(project_id, "test.task", {"data": "test"})

        # Attempt A: started -> failed
        started_event_a = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.started",
            payload={"attempt_id": "attempt_a_12345678901234567890123456789012"},
        )
        started_event_a.compute_hash()
        container.storage.append_event(started_event_a)

        failed_event_a = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.failed",
            payload={
                "attempt_id": "attempt_a_12345678901234567890123456789012",
                "exception_type": "ValueError",
                "message": "First attempt failed",
            },
        )
        failed_event_a.compute_hash()
        container.storage.append_event(failed_event_a)

        # Attempt B: started (no terminal event - interrupted)
        started_event_b = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.started",
            payload={"attempt_id": "attempt_b_98765432109876543210987654321098"},
        )
        started_event_b.compute_hash()
        container.storage.append_event(started_event_b)

        # Act: Derive state via replay
        replay_service = ReplayService(container.storage)
        state = replay_service.execute(project_id)

        # Assert: Replay should show one interrupted task (latest attempt is running)
        assert len(state.interrupted_task_ids) == 1, "Should detect one interrupted task"
        assert task.id in state.interrupted_task_ids, "Task should be in interrupted list"

        # Task counts: latest attempt is running (interrupted)
        assert state.task_counts.running == 1, "Should count task as running (latest attempt interrupted)"
        assert state.task_counts.failed == 0, "Should not count as failed (latest attempt is running)"

    def test_three_attempts_last_completed(self, container: CoreContainer, project_id: str) -> None:
        """ReplayService should track task through multiple attempts, final status from latest."""
        # Arrange: Create task with three attempts
        task = container.orchestrator.submit_task(project_id, "test.task", {"data": "test"})

        # Attempt 1: started -> failed
        e1 = Event(project_id=project_id, task_id=task.id, type="task.started", payload={"attempt_id": "attempt_1_xxx"})
        e1.compute_hash()
        container.storage.append_event(e1)

        e2 = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.failed",
            payload={"attempt_id": "attempt_1_xxx", "exception_type": "ValueError", "message": "Fail 1"},
        )
        e2.compute_hash()
        container.storage.append_event(e2)

        # Attempt 2: started -> failed
        e3 = Event(project_id=project_id, task_id=task.id, type="task.started", payload={"attempt_id": "attempt_2_yyy"})
        e3.compute_hash()
        container.storage.append_event(e3)

        e4 = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.failed",
            payload={"attempt_id": "attempt_2_yyy", "exception_type": "ValueError", "message": "Fail 2"},
        )
        e4.compute_hash()
        container.storage.append_event(e4)

        # Attempt 3: started -> completed
        e5 = Event(project_id=project_id, task_id=task.id, type="task.started", payload={"attempt_id": "attempt_3_zzz"})
        e5.compute_hash()
        container.storage.append_event(e5)

        e6 = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.completed",
            payload={"attempt_id": "attempt_3_zzz", "result": "success"},
        )
        e6.compute_hash()
        container.storage.append_event(e6)

        # Act: Derive state via replay
        replay_service = ReplayService(container.storage)
        state = replay_service.execute(project_id)

        # Assert: Latest attempt succeeded
        assert state.task_counts.completed == 1, "Should count task as completed (latest attempt)"
        assert state.task_counts.failed == 0, "Should not count as failed (latest attempt succeeded)"
        assert len(state.interrupted_task_ids) == 0, "Should have no interrupted tasks"


class TestMissingAttemptIdHandling:
    """Test that replay gracefully handles events where attempt_id is not present in payload."""

    def test_replay_handles_missing_attempt_id(self, container: CoreContainer, project_id: str) -> None:
        """ReplayService should handle task.started events without attempt_id in payload."""
        # Arrange: Create task with old-style events (no attempt_id)
        task = container.orchestrator.submit_task(project_id, "test.task", {"data": "test"})

        started_event = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.started",
            payload={},  # No attempt_id
        )
        started_event.compute_hash()
        container.storage.append_event(started_event)

        # Act: Derive state via replay
        replay_service = ReplayService(container.storage)
        state = replay_service.execute(project_id)

        # Assert: Should detect interrupted task (no terminal event)
        assert len(state.interrupted_task_ids) == 1, "Should detect interrupted task even without attempt_id"
        assert task.id in state.interrupted_task_ids

    def test_replay_handles_mixed_events(self, container: CoreContainer, project_id: str) -> None:
        """ReplayService should handle mix of events with and without attempt_id in payload."""
        # Arrange: Task with one old attempt and one new attempt
        task = container.orchestrator.submit_task(project_id, "test.task", {"data": "test"})

        # Old attempt: no attempt_id
        e1 = Event(project_id=project_id, task_id=task.id, type="task.started", payload={})
        e1.compute_hash()
        container.storage.append_event(e1)

        e2 = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.failed",
            payload={"exception_type": "ValueError", "message": "Old style failure"},
        )
        e2.compute_hash()
        container.storage.append_event(e2)

        # New attempt: with attempt_id
        e3 = Event(
            project_id=project_id, task_id=task.id, type="task.started", payload={"attempt_id": "attempt_new_abc"}
        )
        e3.compute_hash()
        container.storage.append_event(e3)

        e4 = Event(
            project_id=project_id,
            task_id=task.id,
            type="task.completed",
            payload={"attempt_id": "attempt_new_abc", "result": "success"},
        )
        e4.compute_hash()
        container.storage.append_event(e4)

        # Act: Derive state via replay
        replay_service = ReplayService(container.storage)
        state = replay_service.execute(project_id)

        # Assert: Latest attempt (new) succeeded
        assert state.task_counts.completed == 1, "Should count task as completed (latest attempt)"
        assert len(state.interrupted_task_ids) == 0, "Should have no interrupted tasks"
