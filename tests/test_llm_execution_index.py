"""Tests for LLM execution correlation and indexing."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from openchronicle.core.application.observability.execution_index import (
    LLMCallSummary,
    LLMExecutionIndex,
)
from openchronicle.core.domain.models.project import Event


@pytest.fixture
def index() -> LLMExecutionIndex:
    """Provide a fresh index for each test."""
    return LLMExecutionIndex()


@pytest.fixture
def project_id() -> str:
    return "proj-correlation-test"


@pytest.fixture
def task_id() -> str:
    return "task-correlation-test"


@pytest.fixture
def agent_id() -> str:
    return "agent-correlation-test"


@pytest.fixture
def execution_id() -> str:
    return uuid4().hex


class TestLLMCallSummary:
    """Tests for LLMCallSummary dataclass."""

    def test_summary_fields_initialized(self) -> None:
        """Summary should initialize all fields to defaults."""
        summary = LLMCallSummary(execution_id="test-id")
        assert summary.execution_id == "test-id"
        assert summary.task_id is None
        assert summary.started_at is None
        assert summary.outcome == ""
        assert summary.latency_ms is None

    def test_summary_with_all_fields(self) -> None:
        """Summary should accept all field values."""
        now = datetime.utcnow()
        summary = LLMCallSummary(
            execution_id="test-id",
            task_id="task-1",
            route_reference_id="route-1",
            provider_requested="openai",
            provider_used="openai",
            model_requested="gpt-4",
            model_used="gpt-4",
            outcome="completed",
            started_at=now,
            finished_at=now + timedelta(seconds=1),
            latency_ms=1000,
        )
        assert summary.execution_id == "test-id"
        assert summary.task_id == "task-1"
        assert summary.provider_requested == "openai"
        assert summary.model_used == "gpt-4"
        assert summary.outcome == "completed"
        assert summary.latency_ms == 1000


class TestLLMExecutionIndexIngestion:
    """Tests for event ingestion into the index."""

    def test_ingest_ignores_non_llm_events(
        self, index: LLMExecutionIndex, project_id: str, task_id: str, agent_id: str
    ) -> None:
        """Index should ignore events without execution_id."""
        event = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="task.started",
            payload={},
        )
        index.ingest(event)
        assert len(index.summaries()) == 0

    def test_ingest_ignores_llm_event_without_execution_id(
        self, index: LLMExecutionIndex, project_id: str, task_id: str, agent_id: str
    ) -> None:
        """Index should ignore LLM events that don't include execution_id in payload."""
        event = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.requested",
            payload={"provider": "openai"},  # No execution_id
        )
        index.ingest(event)
        assert len(index.summaries()) == 0

    def test_ingest_tracks_execution_events(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
        execution_id: str,
    ) -> None:
        """Index should track events with execution_id."""
        event = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.requested",
            payload={"execution_id": execution_id},
        )
        index.ingest(event)
        assert len(index.summaries()) == 1

    def test_get_returns_none_for_missing_execution(self, index: LLMExecutionIndex) -> None:
        """get() should return None for non-existent execution_id."""
        assert index.get("missing-id") is None

    def test_get_returns_summary_for_existing_execution(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
        execution_id: str,
    ) -> None:
        """get() should return summary for tracked execution_id."""
        event = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.requested",
            payload={"execution_id": execution_id},
        )
        index.ingest(event)
        summary = index.get(execution_id)
        assert summary is not None
        assert summary.execution_id == execution_id


class TestLLMExecutionIndexCorrelation:
    """Tests for proper correlation across LLM lifecycle events."""

    def test_complete_success_path(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
        execution_id: str,
    ) -> None:
        """Index should correlate llm.requested → llm.completed → llm.execution_recorded."""
        now = datetime.utcnow()

        # Ingest events in sequence (simulating LLM call lifecycle)
        event1 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.requested",
            payload={"execution_id": execution_id},
            created_at=now,
        )
        index.ingest(event1)

        event2 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.completed",
            payload={"execution_id": execution_id},
            created_at=now + timedelta(seconds=1),
        )
        index.ingest(event2)

        event3 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.execution_recorded",
            payload={
                "execution_id": execution_id,
                "route_reference_id": "route-1",
                "provider_requested": "openai",
                "provider_used": "openai",
                "model_requested": "gpt-4",
                "model": "gpt-4",
                "outcome": "completed",
            },
            created_at=now + timedelta(seconds=1),
        )
        index.ingest(event3)

        # Verify all fields correlated
        summary = index.get(execution_id)
        assert summary is not None
        assert summary.execution_id == execution_id
        assert summary.task_id == task_id
        assert summary.route_reference_id == "route-1"
        assert summary.provider_requested == "openai"
        assert summary.provider_used == "openai"
        assert summary.model_requested == "gpt-4"
        assert summary.model_used == "gpt-4"
        assert summary.outcome == "completed"
        assert summary.started_at == now
        assert summary.finished_at == now + timedelta(seconds=1)
        assert summary.latency_ms == 1000

    def test_failure_path(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
        execution_id: str,
    ) -> None:
        """Index should handle terminal failure with error_code."""
        now = datetime.utcnow()

        event1 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.requested",
            payload={"execution_id": execution_id},
            created_at=now,
        )
        index.ingest(event1)

        event2 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.failed",
            payload={"execution_id": execution_id},
            created_at=now + timedelta(seconds=1),
        )
        index.ingest(event2)

        event3 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.execution_recorded",
            payload={
                "execution_id": execution_id,
                "outcome": "failed",
                "error_code": "rate_limit_exceeded",
            },
            created_at=now + timedelta(seconds=1),
        )
        index.ingest(event3)

        summary = index.get(execution_id)
        assert summary is not None
        assert summary.outcome == "failed"
        assert summary.error_code == "rate_limit_exceeded"

    def test_refusal_path(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
        execution_id: str,
    ) -> None:
        """Index should handle refusal with error_code from llm.refused."""
        now = datetime.utcnow()

        event1 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.requested",
            payload={"execution_id": execution_id},
            created_at=now,
        )
        index.ingest(event1)

        event2 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.refused",
            payload={"execution_id": execution_id, "error_code": "content_policy"},
            created_at=now + timedelta(seconds=1),
        )
        index.ingest(event2)

        summary = index.get(execution_id)
        assert summary is not None
        assert summary.outcome == "refused"
        assert summary.error_code == "content_policy"

    def test_multiple_executions_independent(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
    ) -> None:
        """Index should independently correlate multiple executions."""
        now = datetime.utcnow()
        exec1 = uuid4().hex
        exec2 = uuid4().hex

        # First execution
        index.ingest(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent_id,
                type="llm.execution_recorded",
                payload={
                    "execution_id": exec1,
                    "model": "gpt-4",
                    "outcome": "completed",
                },
                created_at=now,
            )
        )

        # Second execution (with different model)
        index.ingest(
            Event(
                project_id=project_id,
                task_id=task_id,
                agent_id=agent_id,
                type="llm.execution_recorded",
                payload={
                    "execution_id": exec2,
                    "model": "gpt-3.5",
                    "outcome": "completed",
                },
                created_at=now + timedelta(seconds=1),
            )
        )

        # Verify each tracked independently
        summary1 = index.get(exec1)
        summary2 = index.get(exec2)
        assert summary1 is not None and summary1.model_used == "gpt-4"
        assert summary2 is not None and summary2.model_used == "gpt-3.5"


class TestLLMExecutionIndexDeterminism:
    """Tests for deterministic ordering of summaries."""

    def test_summaries_sorted_by_started_at(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
    ) -> None:
        """summaries() should return in deterministic order by started_at then execution_id."""
        now = datetime.utcnow()

        # Add events in reverse chronological order (to test sorting)
        for i in range(2, 0, -1):
            exec_id = f"exec-{i}"
            index.ingest(
                Event(
                    project_id=project_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    type="llm.requested",
                    payload={"execution_id": exec_id},
                    created_at=now + timedelta(seconds=i),
                )
            )

        summaries = index.summaries()
        assert len(summaries) == 2
        # Should be ordered earliest first
        assert summaries[0].execution_id == "exec-1"
        assert summaries[1].execution_id == "exec-2"

    def test_summaries_deterministic_without_timestamps(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
    ) -> None:
        """summaries() should use execution_id for tiebreaker when no timestamps."""
        # Add events without started_at times
        for i in ["c", "a", "b"]:  # Intentionally not in order
            exec_id = f"exec-{i}"
            index.ingest(
                Event(
                    project_id=project_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    type="llm.execution_recorded",
                    payload={
                        "execution_id": exec_id,
                        "outcome": "completed",
                    },
                )
            )

        summaries = index.summaries()
        # Should be ordered by execution_id when timestamps are equal
        ids = [s.execution_id for s in summaries]
        assert ids == sorted(ids)

    def test_summaries_consistent_across_multiple_calls(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
    ) -> None:
        """Multiple calls to summaries() should return identical ordering."""
        for i in range(3):
            exec_id = f"exec-{i}"
            index.ingest(
                Event(
                    project_id=project_id,
                    task_id=task_id,
                    agent_id=agent_id,
                    type="llm.execution_recorded",
                    payload={
                        "execution_id": exec_id,
                        "outcome": "completed",
                    },
                )
            )

        summaries1 = index.summaries()
        summaries2 = index.summaries()

        ids1 = [s.execution_id for s in summaries1]
        ids2 = [s.execution_id for s in summaries2]
        assert ids1 == ids2


class TestLLMExecutionIndexEventOrdering:
    """Tests for handling events received out of order."""

    def test_handles_events_out_of_order(
        self,
        index: LLMExecutionIndex,
        project_id: str,
        task_id: str,
        agent_id: str,
        execution_id: str,
    ) -> None:
        """Index should correctly handle events arriving out of sequence."""
        later = datetime.utcnow()
        earlier = later - timedelta(seconds=1)

        # Ingest execution_recorded first, then requested (reverse order)
        event1 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.execution_recorded",
            payload={
                "execution_id": execution_id,
                "model": "gpt-4",
                "outcome": "completed",
            },
            created_at=later,
        )
        index.ingest(event1)

        event2 = Event(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            type="llm.requested",
            payload={"execution_id": execution_id},
            created_at=earlier,
        )
        index.ingest(event2)

        # Summary should use the earlier timestamp despite ingestion order
        summary = index.get(execution_id)
        assert summary is not None
        assert summary.started_at == earlier
        assert summary.model_used == "gpt-4"
