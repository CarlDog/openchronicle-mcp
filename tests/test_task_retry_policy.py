"""Tests for task execution-level retry policy and retry controller."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.application.policies.retry_controller import (
    RetryController,
)
from openchronicle.core.domain.models.retry_policy import TaskRetryPolicy
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.wiring.container import CoreContainer


def test_retry_policy_no_retry() -> None:
    """Test default no-retry policy."""
    policy = TaskRetryPolicy.no_retry()
    assert policy.max_attempts == 1
    assert policy.retry_on_errors is None
    assert policy.backoff_seconds == 0
    assert not policy.should_allow_retry()


def test_retry_policy_with_max_attempts() -> None:
    """Test policy that allows retries on any error."""
    policy = TaskRetryPolicy.with_max_attempts(max_attempts=3, backoff_seconds=2)
    assert policy.max_attempts == 3
    assert policy.retry_on_errors is None
    assert policy.backoff_seconds == 2
    assert policy.should_allow_retry()


def test_retry_policy_with_selective_retry() -> None:
    """Test policy that retries only on specific error codes."""
    policy = TaskRetryPolicy.with_selective_retry(
        max_attempts=2,
        retry_on_errors=["rate_limit_exceeded", "server_error"],
        backoff_seconds=1,
    )
    assert policy.max_attempts == 2
    assert policy.retry_on_errors == ["rate_limit_exceeded", "server_error"]
    assert policy.backoff_seconds == 1
    assert policy.should_allow_retry()


def test_retry_policy_serialization() -> None:
    """Test policy serializes to dict for event payload."""
    policy = TaskRetryPolicy.with_max_attempts(max_attempts=2)
    payload = policy.to_dict()
    assert payload == {
        "max_attempts": 2,
        "retry_on_errors": None,
        "backoff_seconds": 0,
    }


# Tests for RetryController


def test_retry_controller_disables_retry_at_max() -> None:
    """Test retry disabled when max attempts reached."""
    policy = TaskRetryPolicy.with_max_attempts(max_attempts=2)
    # 2 prior attempts means we've exhausted max_attempts=2
    result = RetryController.should_retry(
        task_id="task1",
        attempt_id="attempt1",
        error_code=None,
        policy=policy,
        prior_attempts=2,
    )
    assert not result, "Should not retry when max_attempts reached"


def test_retry_controller_allows_retry_within_limit() -> None:
    """Test retry allowed when under max attempts."""
    policy = TaskRetryPolicy.with_max_attempts(max_attempts=3)
    # 1 prior attempt, max=3, should allow retry
    result = RetryController.should_retry(
        task_id="task1",
        attempt_id="attempt1",
        error_code=None,
        policy=policy,
        prior_attempts=1,
    )
    assert result, "Should allow retry when within max_attempts"


def test_retry_controller_respects_selective_errors() -> None:
    """Test retry only on specified error codes."""
    policy = TaskRetryPolicy.with_selective_retry(
        max_attempts=2,
        retry_on_errors=["rate_limit_exceeded"],
    )

    # Error code matches: retry allowed
    result = RetryController.should_retry(
        task_id="task1",
        attempt_id="attempt1",
        error_code="rate_limit_exceeded",
        policy=policy,
        prior_attempts=1,
    )
    assert result, "Should retry on allowed error code"

    # Error code doesn't match: no retry
    result = RetryController.should_retry(
        task_id="task1",
        attempt_id="attempt1",
        error_code="unknown_error",
        policy=policy,
        prior_attempts=1,
    )
    assert not result, "Should not retry on disallowed error code"


def test_retry_controller_handles_missing_error_code() -> None:
    """Test retry decision with missing error code."""
    policy = TaskRetryPolicy.with_selective_retry(
        max_attempts=2,
        retry_on_errors=["rate_limit_exceeded"],
    )

    # No error code when selective retry is configured: no retry
    result = RetryController.should_retry(
        task_id="task1",
        attempt_id="attempt1",
        error_code=None,
        policy=policy,
        prior_attempts=1,
    )
    assert not result, "Should not retry when error_code is None and selective retry is configured"


def test_retry_controller_allows_retry_with_no_selective_errors() -> None:
    """Test retry allowed for any error when no selective list configured."""
    policy = TaskRetryPolicy.with_max_attempts(max_attempts=2)

    # Any error code allowed (no selective list)
    result = RetryController.should_retry(
        task_id="task1",
        attempt_id="attempt1",
        error_code="any_error",
        policy=policy,
        prior_attempts=1,
    )
    assert result, "Should retry on any error when selective list not configured"

    # Even None error code allowed
    result = RetryController.should_retry(
        task_id="task1",
        attempt_id="attempt1",
        error_code=None,
        policy=policy,
        prior_attempts=1,
    )
    assert result, "Should retry even with no error code when selective list not configured"


# Integration tests with orchestrator


@pytest.fixture
def container(tmp_path: Path) -> CoreContainer:
    """Create a fresh container with isolated temp database for each test."""
    return CoreContainer(db_path=str(tmp_path / "test_retry.db"))


@pytest.fixture
def project_id(container: CoreContainer) -> str:
    """Create a test project."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Retry Policy Test")
    return project.id


@pytest.fixture
def agent_id(container: CoreContainer, project_id: str) -> str:
    """Create a test agent."""
    orchestrator = container.orchestrator
    agent = orchestrator.register_agent(project_id=project_id, name="TestWorker", role="worker")
    return agent.id


@pytest.mark.asyncio
async def test_task_retry_disabled_by_default(container: CoreContainer, project_id: str, agent_id: str) -> None:
    """Test retry disabled by default (no policy configured)."""
    orchestrator = container.orchestrator

    # Create task without retry policy
    task = orchestrator.submit_task(project_id, "test_handler", {"data": "test"})

    # Mock handler to fail
    async def failing_handler(t: Any, context: Any) -> None:
        raise ValueError("Test error")

    orchestrator.handler_registry.register("test_handler", failing_handler)

    # Execute task - should fail
    with pytest.raises(ValueError):
        await orchestrator.execute_task(task.id, agent_id=agent_id)

    # Check events
    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]

    # Should have task_failed event
    assert "task_failed" in event_types

    # Should NOT have task.retry_scheduled event
    assert "task.retry_scheduled" not in event_types

    # Should have exactly 1 task_started event (no retry)
    task_started_events = [e for e in events if e.type == "task_started"]
    assert len(task_started_events) == 1


@pytest.mark.asyncio
async def test_task_retry_allowed_on_specific_error(container: CoreContainer, project_id: str, agent_id: str) -> None:
    """Test retry scheduled when error code matches retry policy."""
    orchestrator = container.orchestrator

    # Create task with retry policy allowing 2 attempts on 'rate_limit_exceeded'
    task = orchestrator.submit_task(
        project_id,
        "test_handler",
        {
            "data": "test",
            "retry_policy": {
                "max_attempts": 2,
                "retry_on_errors": ["rate_limit_exceeded"],
                "backoff_seconds": 1,
            },
        },
    )

    # Mock handler to fail with matching error code
    call_count = [0]

    async def failing_handler(t: Any, context: Any) -> None:
        call_count[0] += 1
        error = LLMProviderError("Rate limited", error_code="rate_limit_exceeded")
        raise error

    orchestrator.handler_registry.register("test_handler", failing_handler)

    # Execute task - should fail but trigger retry
    with pytest.raises(LLMProviderError):
        await orchestrator.execute_task(task.id, agent_id=agent_id)

    # Check events
    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]

    # Should have task_failed event
    assert "task_failed" in event_types

    # Should have task.retry_scheduled event
    assert "task.retry_scheduled" in event_types
    retry_events = [e for e in events if e.type == "task.retry_scheduled"]
    assert len(retry_events) == 1
    retry_event = retry_events[0]
    assert retry_event.payload["failed_attempt_id"]
    assert retry_event.payload["prior_attempts"] == 1
    assert retry_event.payload["max_attempts"] == 2
    assert retry_event.payload["error_code"] == "rate_limit_exceeded"
    assert retry_event.payload["reason"] == "policy"


@pytest.mark.asyncio
async def test_task_retry_not_allowed_on_different_error(
    container: CoreContainer, project_id: str, agent_id: str
) -> None:
    """Test retry NOT scheduled when error code doesn't match retry policy."""
    orchestrator = container.orchestrator

    # Create task with retry policy limiting to specific error
    task = orchestrator.submit_task(
        project_id,
        "test_handler",
        {
            "data": "test",
            "retry_policy": {
                "max_attempts": 2,
                "retry_on_errors": ["rate_limit_exceeded"],
                "backoff_seconds": 0,
            },
        },
    )

    # Mock handler to fail with different error code
    async def failing_handler(t: Any, context: Any) -> None:
        error = LLMProviderError("Server error", error_code="server_error")
        raise error

    orchestrator.handler_registry.register("test_handler", failing_handler)

    # Execute task - should fail without retry
    with pytest.raises(LLMProviderError):
        await orchestrator.execute_task(task.id, agent_id=agent_id)

    # Check events
    events = container.storage.list_events(task.id)
    event_types = [e.type for e in events]

    # Should have task_failed event
    assert "task_failed" in event_types

    # Should NOT have task.retry_scheduled event (error code doesn't match)
    assert "task.retry_scheduled" not in event_types


@pytest.mark.asyncio
async def test_task_retry_max_attempts_exhaustion(container: CoreContainer, project_id: str, agent_id: str) -> None:
    """Test retry scheduling stops after max_attempts reached."""
    orchestrator = container.orchestrator

    # Create task with max 2 attempts on any error
    task = orchestrator.submit_task(
        project_id,
        "test_handler",
        {
            "data": "test",
            "retry_policy": {
                "max_attempts": 2,
                "retry_on_errors": None,  # Retry on any error
                "backoff_seconds": 0,
            },
        },
    )

    # Mock handler to always fail
    async def failing_handler(t: Any, context: Any) -> None:
        raise ValueError("Persistent error")

    orchestrator.handler_registry.register("test_handler", failing_handler)

    # First attempt
    with pytest.raises(ValueError):
        await orchestrator.execute_task(task.id, agent_id=agent_id)

    events_after_first = container.storage.list_events(task.id)
    retry_events_after_first = [e for e in events_after_first if e.type == "task.retry_scheduled"]
    assert len(retry_events_after_first) == 1  # First failure allows retry

    # Simulate second attempt (manually for test, since we're not auto-retrying)
    # In real flow, orchestration would call execute_task again with same task_id
    task_started_first = [e for e in events_after_first if e.type == "task_started"]
    assert len(task_started_first) == 1

    # For this test, just verify the policy would reject a 3rd attempt
    policy = TaskRetryPolicy.with_max_attempts(max_attempts=2)
    should_retry_third = RetryController.should_retry(
        task_id=task.id,
        attempt_id="attempt3",
        error_code=None,
        policy=policy,
        prior_attempts=2,  # 2 attempts already made
    )
    assert not should_retry_third, "Should not allow 3rd attempt when max_attempts=2"


@pytest.mark.asyncio
async def test_retry_event_includes_policy_metadata(container: CoreContainer, project_id: str, agent_id: str) -> None:
    """Test retry_scheduled event includes full retry policy metadata."""
    orchestrator = container.orchestrator

    # Create task with specific retry policy
    retry_policy_config = {
        "max_attempts": 3,
        "retry_on_errors": ["timeout", "rate_limit_exceeded"],
        "backoff_seconds": 5,
    }
    task = orchestrator.submit_task(
        project_id,
        "test_handler",
        {"data": "test", "retry_policy": retry_policy_config},
    )

    # Mock handler to fail with matching error
    async def failing_handler(t: Any, context: Any) -> None:
        error = LLMProviderError("Timeout", error_code="timeout")
        raise error

    orchestrator.handler_registry.register("test_handler", failing_handler)

    # Execute task
    with pytest.raises(LLMProviderError):
        await orchestrator.execute_task(task.id, agent_id=agent_id)

    # Find retry_scheduled event
    events = container.storage.list_events(task.id)
    retry_events = [e for e in events if e.type == "task.retry_scheduled"]
    assert len(retry_events) == 1
    retry_event = retry_events[0]

    # Verify event payload includes all required fields
    assert retry_event.payload["task_id"] == task.id
    assert retry_event.payload["failed_attempt_id"]
    assert retry_event.payload["prior_attempts"] == 1
    assert retry_event.payload["max_attempts"] == 3
    assert retry_event.payload["error_code"] == "timeout"
    assert retry_event.payload["backoff_seconds"] == 5
    assert retry_event.payload["reason"] == "policy"


@pytest.mark.asyncio
async def test_get_retry_policy_from_task(container: CoreContainer, project_id: str) -> None:
    """Test orchestrator correctly extracts retry policy from task payload."""
    orchestrator = container.orchestrator

    # Task with retry policy
    task_with_policy = orchestrator.submit_task(
        project_id,
        "test_handler",
        {
            "data": "test",
            "retry_policy": {
                "max_attempts": 2,
                "retry_on_errors": ["rate_limit"],
                "backoff_seconds": 1,
            },
        },
    )

    policy = orchestrator.get_retry_policy(task_with_policy)
    assert policy.max_attempts == 2
    assert policy.retry_on_errors == ["rate_limit"]
    assert policy.backoff_seconds == 1

    # Task without retry policy (defaults to no retry)
    task_without_policy = orchestrator.submit_task(project_id, "test_handler", {"data": "test"})

    policy_default = orchestrator.get_retry_policy(task_without_policy)
    assert policy_default.max_attempts == 1
    assert policy_default.retry_on_errors is None


@pytest.mark.asyncio
async def test_count_prior_attempts(container: CoreContainer, project_id: str, agent_id: str) -> None:
    """Test orchestrator correctly counts prior attempts."""
    orchestrator = container.orchestrator

    task = orchestrator.submit_task(project_id, "test_handler", {"data": "test"})

    # Initially 0 attempts
    count = orchestrator._count_prior_attempts(task.id)
    assert count == 0

    # Mock task started event
    from openchronicle.core.domain.models.project import Event

    orchestrator.emit_event(
        Event(
            project_id=project_id,
            task_id=task.id,
            type="task_started",
            payload={"attempt_id": "attempt1"},
        )
    )

    # Should count 1 attempt
    count = orchestrator._count_prior_attempts(task.id)
    assert count == 1

    # Add another attempt
    orchestrator.emit_event(
        Event(
            project_id=project_id,
            task_id=task.id,
            type="task_started",
            payload={"attempt_id": "attempt2"},
        )
    )

    # Should count 2 attempts
    count = orchestrator._count_prior_attempts(task.id)
    assert count == 2
