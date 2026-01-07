"""Tests for LLM usage tracking and budget enforcement."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.exceptions import BudgetExceededError
from openchronicle.core.domain.models.project import LLMUsage as LLMUsageModel
from openchronicle.core.domain.ports.llm_port import LLMResponse, LLMUsage
from openchronicle.core.domain.services.usage_tracker import UsageTracker


@pytest.fixture
def container(tmp_path: Any) -> CoreContainer:
    """Create test container with in-memory database."""
    db_path = tmp_path / "test.db"
    return CoreContainer(db_path=str(db_path))


@pytest.fixture
def project_id(container: CoreContainer) -> str:
    """Create test project and return its ID."""
    project = container.orchestrator.create_project("test-project")
    return project.id


@pytest.fixture
def task_id(container: CoreContainer, project_id: str) -> str:
    """Create test task and return its ID."""
    task = container.orchestrator.submit_task(
        project_id=project_id,
        task_type="analysis.worker.summarize",
        payload={"text": "test"},
    )
    return task.id


@pytest.fixture
def agent_id(container: CoreContainer, project_id: str) -> str:
    """Create test agent and return its ID."""
    from openchronicle.core.application.use_cases import register_agent

    agent = register_agent.execute(
        container.orchestrator,
        project_id=project_id,
        name="Test Agent",
        role="worker",
        provider="stub",
        model="stub-model",
    )
    return agent.id


def test_usage_tracker_records_call(container: CoreContainer, project_id: str, task_id: str, agent_id: str) -> None:
    """Test that UsageTracker records LLM calls correctly."""
    usage_tracker = UsageTracker(container.storage)

    # Create a mock response with usage data
    response = LLMResponse(
        provider="stub",
        model="stub-model",
        content="test summary",
        finish_reason="stop",
        request_id="req-123",
        latency_ms=100,
        usage=LLMUsage(input_tokens=10, output_tokens=20, total_tokens=30),
    )

    # Record the call
    usage_tracker.record_call(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        response=response,
    )

    # Verify usage was stored
    usage_list = container.storage.list_llm_usage_by_project(project_id)
    assert len(usage_list) == 1

    usage = usage_list[0]
    assert usage.project_id == project_id
    assert usage.task_id == task_id
    assert usage.agent_id == agent_id
    assert usage.provider == "stub"
    assert usage.model == "stub-model"
    assert usage.request_id == "req-123"
    assert usage.input_tokens == 10
    assert usage.output_tokens == 20
    assert usage.total_tokens == 30
    assert usage.latency_ms == 100


def test_usage_tracker_handles_missing_usage(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str
) -> None:
    """Test that UsageTracker handles responses without usage data."""
    usage_tracker = UsageTracker(container.storage)

    # Create response without usage data
    response = LLMResponse(
        provider="stub",
        model="stub-model",
        content="test",
        finish_reason="stop",
        request_id=None,
        latency_ms=None,
        usage=None,
    )

    # Should not raise
    usage_tracker.record_call(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        response=response,
    )

    # Verify usage was stored with null tokens
    usage_list = container.storage.list_llm_usage_by_project(project_id)
    assert len(usage_list) == 1

    usage = usage_list[0]
    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.total_tokens is None


def test_get_task_token_totals(container: CoreContainer, project_id: str, task_id: str, agent_id: str) -> None:
    """Test retrieving token totals for a task."""
    usage_tracker = UsageTracker(container.storage)

    # Record multiple calls
    for i in range(3):
        response = LLMResponse(
            provider="stub",
            model="stub-model",
            content=f"response {i}",
            finish_reason="stop",
            usage=LLMUsage(input_tokens=10, output_tokens=20, total_tokens=30),
        )
        usage_tracker.record_call(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            response=response,
        )

    # Get totals
    totals = usage_tracker.get_task_token_totals(task_id)

    assert totals["input_tokens"] == 30
    assert totals["output_tokens"] == 60
    assert totals["total_tokens"] == 90


async def test_budget_exceeded_blocks_llm_call(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test that budget exceeded prevents LLM call."""
    # Set a very low budget
    monkeypatch.setenv("OC_MAX_TOKENS_PER_TASK", "10")

    # Pre-populate usage to exceed budget
    usage = LLMUsageModel(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        provider="stub",
        model="stub-model",
        request_id=None,
        input_tokens=5,
        output_tokens=5,
        total_tokens=10,
        latency_ms=100,
    )
    container.storage.insert_llm_usage(usage)

    # Get the task
    task = container.storage.get_task(task_id)
    assert task is not None

    # Track if LLM was called
    llm_called = False

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        nonlocal llm_called
        llm_called = True
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="should not be called",
            finish_reason="stop",
        )

    # Replace LLM complete_async
    container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

    # Try to execute task - should raise BudgetExceededError
    with pytest.raises(BudgetExceededError) as exc_info:
        await container.orchestrator._run_worker_summarize(task, agent_id)

    # Verify LLM was NOT called
    assert not llm_called

    # Verify exception details
    assert exc_info.value.limit == 10
    assert exc_info.value.current == 10

    # Verify event was emitted
    events = container.storage.list_events(task_id)
    budget_events = [e for e in events if e.type == "llm.budget_exceeded"]
    assert len(budget_events) == 1

    event = budget_events[0]
    assert event.payload["limit"] == 10
    assert event.payload["current"] == 10


async def test_output_token_clamping(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test that OC_MAX_OUTPUT_TOKENS_PER_CALL clamps max_output_tokens."""
    # Set output token limit
    monkeypatch.setenv("OC_MAX_OUTPUT_TOKENS_PER_CALL", "100")

    # Track what was passed to LLM
    actual_max_tokens = None

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        nonlocal actual_max_tokens
        actual_max_tokens = kwargs.get("max_output_tokens")
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="clamped response",
            finish_reason="stop",
            usage=LLMUsage(input_tokens=10, output_tokens=90, total_tokens=100),
        )

    container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

    # Get the task
    task = container.storage.get_task(task_id)
    assert task is not None

    # Execute - default max_tokens in orchestrator is 256
    await container.orchestrator._run_worker_summarize(task, agent_id)

    # Verify clamped value was passed
    assert actual_max_tokens == 100

    # Verify clamping event was emitted
    events = container.storage.list_events(task_id)
    clamp_events = [e for e in events if e.type == "llm.request_clamped"]
    assert len(clamp_events) == 1

    event = clamp_events[0]
    assert event.payload["requested_max_tokens"] == 256
    assert event.payload["clamped_max_tokens"] == 100


async def test_usage_recording_after_successful_call(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str
) -> None:
    """Test that usage is recorded after successful LLM call."""

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="test summary",
            finish_reason="stop",
            request_id="req-456",
            latency_ms=150,
            usage=LLMUsage(input_tokens=15, output_tokens=25, total_tokens=40),
        )

    container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

    # Get the task
    task = container.storage.get_task(task_id)
    assert task is not None

    # Execute
    result = await container.orchestrator._run_worker_summarize(task, agent_id)

    assert result == "test summary"

    # Verify usage was recorded
    usage_list = container.storage.list_llm_usage_by_project(project_id)
    assert len(usage_list) == 1

    usage = usage_list[0]
    assert usage.task_id == task_id
    assert usage.request_id == "req-456"
    assert usage.input_tokens == 15
    assert usage.output_tokens == 25
    assert usage.total_tokens == 40


def test_list_llm_usage_deterministic_ordering(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str
) -> None:
    """Test that list_llm_usage_by_project returns deterministic ordering."""

    # Record calls with same timestamp but different IDs
    base_time = datetime.now(UTC).isoformat()

    # Manually insert with controlled IDs and timestamps
    for i in range(5):
        usage = LLMUsageModel(
            id=f"usage-{i:03d}",
            created_at=base_time,
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            provider="stub",
            model="stub-model",
            request_id=None,
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            latency_ms=100,
        )
        container.storage.insert_llm_usage(usage)

    # Retrieve and verify order
    usage_list = container.storage.list_llm_usage_by_project(project_id)

    # Should be ordered DESC by created_at, then DESC by id
    # Since all have same timestamp, should be ordered by id DESC
    assert len(usage_list) == 5
    assert usage_list[0].id == "usage-004"
    assert usage_list[1].id == "usage-003"
    assert usage_list[2].id == "usage-002"
    assert usage_list[3].id == "usage-001"
    assert usage_list[4].id == "usage-000"


def test_sum_tokens_by_project(container: CoreContainer, project_id: str, task_id: str, agent_id: str) -> None:
    """Test project-level token aggregation."""
    # Create another task
    task2_id = container.orchestrator.submit_task(
        project_id=project_id,
        task_type="analysis.worker.summarize",
        payload={"text": "test2"},
    ).id

    # Insert usage for both tasks
    for tid in [task_id, task2_id]:
        usage = LLMUsageModel(
            project_id=project_id,
            task_id=tid,
            agent_id=agent_id,
            provider="stub",
            model="stub-model",
            request_id=None,
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            latency_ms=100,
        )
        container.storage.insert_llm_usage(usage)

    # Get project totals
    totals = container.storage.sum_tokens_by_project(project_id)

    assert totals["input_tokens"] == 20
    assert totals["output_tokens"] == 40
    assert totals["total_tokens"] == 60


def test_no_budget_allows_call(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test that when no budget is set, calls proceed normally."""
    # Ensure no budget env var is set
    monkeypatch.delenv("OC_MAX_TOKENS_PER_TASK", raising=False)

    # Pre-populate large usage
    usage = LLMUsageModel(
        project_id=project_id,
        task_id=task_id,
        agent_id=agent_id,
        provider="stub",
        model="stub-model",
        request_id=None,
        input_tokens=1000,
        output_tokens=2000,
        total_tokens=3000,
        latency_ms=100,
    )
    container.storage.insert_llm_usage(usage)

    # Should still allow calls
    llm_called = False

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        nonlocal llm_called
        llm_called = True
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="allowed",
            finish_reason="stop",
        )

    container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

    # Get the task
    task = container.storage.get_task(task_id)
    assert task is not None

    # Execute - should not raise
    import asyncio

    result = asyncio.run(container.orchestrator._run_worker_summarize(task, agent_id))

    assert llm_called
    assert result == "allowed"
