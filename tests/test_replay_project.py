"""Tests for event replay and derived state projection.

Verifies that event replay correctly reconstructs project state deterministically
from persisted events without mutations or new behavior.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from openchronicle.core.application.use_cases.replay_project import ReplayService
from openchronicle.core.domain.models.project import Event, Project, Task
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


@pytest.fixture
def db(tmp_path: Path) -> SqliteStore:
    """Provide fresh SQLite store for each test."""
    db_file = tmp_path / "test.db"
    store = SqliteStore(str(db_file))
    store.init_schema()
    return store


def fixed_time(idx: int, base: datetime | None = None) -> datetime:
    """Generate fixed timestamps with 1-second offsets."""
    if base is None:
        base = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    return base + timedelta(seconds=idx)


class TestReplayServiceInterruptedDetection:
    """Tests for correctly identifying interrupted (started but not completed) tasks."""

    def test_detects_interrupted_tasks(self, db: SqliteStore) -> None:
        """ReplayService should identify tasks started but not completed."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        # Create two tasks
        task1 = Task(project_id=project.id, type="summarize")
        task2 = Task(project_id=project.id, type="analyze")
        db.add_task(task1)
        db.add_task(task2)

        # Task 1: started but no completion (interrupted)
        e1 = Event(
            project_id=project.id,
            task_id=task1.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e1.compute_hash()
        db.append_event(e1)

        e2 = Event(
            project_id=project.id,
            task_id=task1.id,
            type="task.started",
            payload={},
            created_at=fixed_time(2),
        )
        e2.prev_hash = e1.hash
        e2.compute_hash()
        db.append_event(e2)

        # Task 2: started and completed (not interrupted)
        e3 = Event(
            project_id=project.id,
            task_id=task2.id,
            type="task.created",
            payload={},
            created_at=fixed_time(3),
        )
        e3.compute_hash()
        db.append_event(e3)

        e4 = Event(
            project_id=project.id,
            task_id=task2.id,
            type="task.started",
            payload={},
            created_at=fixed_time(4),
        )
        e4.prev_hash = e3.hash
        e4.compute_hash()
        db.append_event(e4)

        e5 = Event(
            project_id=project.id,
            task_id=task2.id,
            type="task.completed",
            payload={"result": "ok"},
            created_at=fixed_time(5),
        )
        e5.prev_hash = e4.hash
        e5.compute_hash()
        db.append_event(e5)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert
        assert state.interrupted_task_ids == [task1.id]
        assert state.task_counts.running == 1
        assert state.task_counts.completed == 1
        assert state.task_counts.pending == 0

    def test_pending_tasks_not_interrupted(self, db: SqliteStore) -> None:
        """ReplayService should not count created-only tasks as interrupted."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        task = Task(project_id=project.id, type="summarize")
        db.add_task(task)

        # Only created, never started
        e1 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e1.compute_hash()
        db.append_event(e1)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert
        assert state.interrupted_task_ids == []
        assert state.task_counts.pending == 1
        assert state.task_counts.running == 0


class TestReplayServiceDeterminism:
    """Tests for deterministic derivation across runs."""

    def test_deterministic_ordering_by_event_timestamp(self, db: SqliteStore) -> None:
        """ReplayService should derive same state regardless of insertion order."""
        # Setup: create events in reverse chronological order
        project = Project(name="Test Project")
        db.add_project(project)

        task = Task(project_id=project.id, type="summarize")
        db.add_task(task)

        # Insert in reverse order
        e3 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.completed",
            payload={"result": "done"},
            created_at=fixed_time(3),
        )
        e3.compute_hash()
        db.append_event(e3)

        e1 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e1.compute_hash()
        db.append_event(e1)

        e2 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.started",
            payload={},
            created_at=fixed_time(2),
        )
        e2.prev_hash = e1.hash
        e2.compute_hash()
        db.append_event(e2)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert: should derive correct state despite reverse insertion
        assert state.task_counts.completed == 1
        assert state.task_counts.running == 0
        assert state.task_counts.pending == 0

    def test_last_event_timestamp_tracking(self, db: SqliteStore) -> None:
        """ReplayService should track the latest event timestamp."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        task = Task(project_id=project.id, type="summarize")
        db.add_task(task)

        base_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        e1 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.created",
            payload={},
            created_at=base_time,
        )
        e1.compute_hash()
        db.append_event(e1)

        e2 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.completed",
            payload={"result": "ok"},
            created_at=base_time + timedelta(hours=2),
        )
        e2.prev_hash = e1.hash
        e2.compute_hash()
        db.append_event(e2)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert
        assert state.last_event_at == base_time + timedelta(hours=2)


class TestReplayServiceLLMExecutionCorrelation:
    """Tests for LLM execution summary inclusion."""

    def test_includes_llm_execution_summaries(self, db: SqliteStore) -> None:
        """ReplayService should include LLM execution summaries from events."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        task = Task(project_id=project.id, type="summarize")
        db.add_task(task)

        execution_id = "exec-123"

        # Append task events
        e1 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e1.compute_hash()
        db.append_event(e1)

        # Append LLM events
        e_llm_req = Event(
            project_id=project.id,
            task_id=task.id,
            type="llm.requested",
            payload={"execution_id": execution_id},
            created_at=fixed_time(2),
        )
        e_llm_req.compute_hash()
        db.append_event(e_llm_req)

        e_llm_exec = Event(
            project_id=project.id,
            task_id=task.id,
            type="llm.execution_recorded",
            payload={
                "execution_id": execution_id,
                "provider_requested": "openai",
                "provider_used": "openai",
                "model": "gpt-4",
                "outcome": "completed",
            },
            created_at=fixed_time(3),
        )
        e_llm_exec.compute_hash()
        db.append_event(e_llm_exec)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert
        assert len(state.llm_executions) == 1
        summary = state.llm_executions[0]
        assert summary.execution_id == execution_id
        assert summary.provider_used == "openai"
        assert summary.model_used == "gpt-4"
        assert summary.outcome == "completed"

    def test_multiple_llm_executions_included(self, db: SqliteStore) -> None:
        """ReplayService should include multiple LLM executions."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        task = Task(project_id=project.id, type="summarize")
        db.add_task(task)

        exec1, exec2 = "exec-001", "exec-002"

        # Task setup
        e_task = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e_task.compute_hash()
        db.append_event(e_task)

        # First LLM execution
        e_llm1 = Event(
            project_id=project.id,
            task_id=task.id,
            type="llm.execution_recorded",
            payload={
                "execution_id": exec1,
                "provider_used": "openai",
                "outcome": "completed",
            },
            created_at=fixed_time(2),
        )
        e_llm1.compute_hash()
        db.append_event(e_llm1)

        # Second LLM execution
        e_llm2 = Event(
            project_id=project.id,
            task_id=task.id,
            type="llm.execution_recorded",
            payload={
                "execution_id": exec2,
                "provider_used": "ollama",
                "outcome": "failed",
            },
            created_at=fixed_time(3),
        )
        e_llm2.compute_hash()
        db.append_event(e_llm2)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert
        assert len(state.llm_executions) == 2
        # Should be sorted by execution_id
        exec_ids = [s.execution_id for s in state.llm_executions]
        assert exec1 in exec_ids and exec2 in exec_ids


class TestReplayServiceTaskStatusCounting:
    """Tests for correct task status counting."""

    def test_counts_failed_tasks(self, db: SqliteStore) -> None:
        """ReplayService should count failed tasks correctly."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        task1 = Task(project_id=project.id, type="summarize")
        task2 = Task(project_id=project.id, type="analyze")
        db.add_task(task1)
        db.add_task(task2)

        # Task 1: successful
        e1 = Event(
            project_id=project.id,
            task_id=task1.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e1.compute_hash()
        db.append_event(e1)

        e2 = Event(
            project_id=project.id,
            task_id=task1.id,
            type="task.completed",
            payload={"result": "ok"},
            created_at=fixed_time(2),
        )
        e2.prev_hash = e1.hash
        e2.compute_hash()
        db.append_event(e2)

        # Task 2: failed
        e3 = Event(
            project_id=project.id,
            task_id=task2.id,
            type="task.created",
            payload={},
            created_at=fixed_time(3),
        )
        e3.compute_hash()
        db.append_event(e3)

        e4 = Event(
            project_id=project.id,
            task_id=task2.id,
            type="task.failed",
            payload={"error": "timeout"},
            created_at=fixed_time(4),
        )
        e4.prev_hash = e3.hash
        e4.compute_hash()
        db.append_event(e4)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert
        assert state.task_counts.completed == 1
        assert state.task_counts.failed == 1


class TestReplayServiceProjectLevelEvents:
    """Tests for handling project-level events (no task_id)."""

    def test_ignores_project_level_events_in_task_counting(self, db: SqliteStore) -> None:
        """ReplayService should ignore project events when counting tasks."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        task = Task(project_id=project.id, type="summarize")
        db.add_task(task)

        # Task event
        e1 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e1.compute_hash()
        db.append_event(e1)

        # Project-level event (no task_id)
        e2 = Event(
            project_id=project.id,
            task_id=None,
            type="project.resumed",
            payload={},
            created_at=fixed_time(2),
        )
        e2.compute_hash()
        db.append_event(e2)

        # Act
        service = ReplayService(db)
        state = service.execute(project.id)

        # Assert: task still counted as pending
        assert state.task_counts.pending == 1
        assert state.task_counts.total == 1
        # But last_event_at includes project event
        assert state.last_event_at == fixed_time(2)


class TestReplayServiceReadOnly:
    """Tests to verify no mutations occur during replay."""

    def test_does_not_mutate_tasks(self, db: SqliteStore) -> None:
        """ReplayService should not modify task statuses or other data."""
        # Setup
        project = Project(name="Test Project")
        db.add_project(project)

        task = Task(project_id=project.id, type="summarize")
        db.add_task(task)

        e1 = Event(
            project_id=project.id,
            task_id=task.id,
            type="task.created",
            payload={},
            created_at=fixed_time(1),
        )
        e1.compute_hash()
        db.append_event(e1)

        # Get initial task state
        task_before = db.get_task(task.id)
        assert task_before is not None
        status_before = task_before.status

        # Act: replay
        service = ReplayService(db)
        service.execute(project.id)

        # Assert: task unchanged
        task_after = db.get_task(task.id)
        assert task_after is not None
        assert task_after.status == status_before
