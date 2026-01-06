"""Tests for LLM rate limiting and retry policy."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.models.project import TaskStatus
from openchronicle.core.domain.ports.llm_port import LLMProviderError, LLMResponse
from openchronicle.core.domain.ports.llm_port import LLMUsage as LLMUsageModel
from openchronicle.core.infrastructure.rate_limiter import RateLimitTimeoutError


@pytest.fixture
def container() -> CoreContainer:
    """Create a fresh container for each test."""
    return CoreContainer()


@pytest.fixture
def project_id(container: CoreContainer) -> str:
    """Create a test project."""
    orchestrator = container.orchestrator
    project = orchestrator.create_project("Rate Limit Test")
    return project.id


@pytest.fixture
def task_id(container: CoreContainer, project_id: str, agent_id: str) -> str:
    """Create a test task."""
    orchestrator = container.orchestrator
    task = orchestrator.submit_task(project_id, "analysis.worker.summarize", {"text": "Test text"})
    return task.id


@pytest.fixture
def agent_id(container: CoreContainer, project_id: str) -> str:
    """Create a test agent."""
    orchestrator = container.orchestrator
    agent = orchestrator.register_agent(project_id=project_id, name="TestWorker", role="worker")
    return agent.id


@pytest.mark.asyncio
async def test_rpm_rate_limiting_waits(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test that RPM rate limiting causes wait on second call."""
    # Set RPM limit to 1 (one request per minute = very restrictive)
    monkeypatch.setenv("OC_LLM_RPM_LIMIT", "1")
    monkeypatch.setenv("OC_LLM_MAX_WAIT_MS", "100000")  # High enough to not timeout

    # Create fresh container with rate limit
    container2 = CoreContainer()
    project2 = container2.orchestrator.create_project("Rate Test")
    agent2 = container2.orchestrator.register_agent(project_id=project2.id, name="Worker", role="worker")

    # Mock time.sleep in the rate_limiter module to make test fast
    def mock_sleep(seconds: float) -> None:
        pass  # Don't actually sleep

    with patch("openchronicle.core.infrastructure.rate_limiter.time.sleep", mock_sleep):

        async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
            return LLMResponse(
                provider="stub",
                model="stub-model",
                content="summary",
                finish_reason="stop",
                usage=LLMUsageModel(input_tokens=5, output_tokens=3, total_tokens=8),
            )

        container2.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

        # First call - bucket starts with 1 token, should succeed immediately
        task1 = container2.orchestrator.submit_task(project2.id, "analysis.worker.summarize", {"text": "Test 1"})
        result1 = await container2.orchestrator._run_worker_summarize(task1, agent2.id)
        assert result1 == "summary"

        # Check NO rate_limited event on first call
        events1 = container2.storage.list_events(task1.id)
        rate_limited_events1 = [e for e in events1 if e.type == "llm.rate_limited"]
        assert len(rate_limited_events1) == 0

        # Second call immediately - bucket should be empty (used 1 token), trigger rate limiting
        task2 = container2.orchestrator.submit_task(project2.id, "analysis.worker.summarize", {"text": "Test 2"})
        result2 = await container2.orchestrator._run_worker_summarize(task2, agent2.id)
        assert result2 == "summary"

        # Check for llm.rate_limited event on second call
        events2 = container2.storage.list_events(task2.id)
        rate_limited_events2 = [e for e in events2 if e.type == "llm.rate_limited"]
        assert len(rate_limited_events2) == 1
        event = rate_limited_events2[0]
        assert event.payload["wait_ms"] > 0
        assert event.payload["rpm_limit"] == 1


@pytest.mark.asyncio
async def test_rate_limiting_timeout(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test that rate limiting timeout fails cleanly."""
    # Set very restrictive RPM limit and very low timeout
    monkeypatch.setenv("OC_LLM_RPM_LIMIT", "1")  # 1 per minute = very restrictive
    monkeypatch.setenv("OC_LLM_MAX_WAIT_MS", "10")  # Very low timeout (10ms)

    # Create fresh container with these limits
    container2 = CoreContainer()
    project2 = container2.orchestrator.create_project("Timeout Test")
    agent2 = container2.orchestrator.register_agent(project_id=project2.id, name="Worker", role="worker")

    with patch("openchronicle.core.infrastructure.rate_limiter.time.sleep"):  # Prevent actual sleeping

        async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
            return LLMResponse(
                provider="stub",
                model="stub-model",
                content="summary",
                finish_reason="stop",
            )

        container2.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

        # First call consumes the 1 token
        task1 = container2.orchestrator.submit_task(project2.id, "analysis.worker.summarize", {"text": "Test 1"})
        await container2.orchestrator._run_worker_summarize(task1, agent2.id)

        # Second call immediately - bucket empty, needs to wait ~60s but timeout is 10ms
        task2 = container2.orchestrator.submit_task(project2.id, "analysis.worker.summarize", {"text": "Test 2"})

        with pytest.raises(RateLimitTimeoutError) as exc_info:
            await container2.orchestrator._run_worker_summarize(task2, agent2.id)

        # Verify exception details
        assert exc_info.value.max_wait_ms == 10

        # Check for llm.rate_limit_timeout event
        events = container2.storage.list_events(task2.id)
        timeout_events = [e for e in events if e.type == "llm.rate_limit_timeout"]
        assert len(timeout_events) == 1
        event = timeout_events[0]
        assert event.payload["max_wait_ms"] == 10


@pytest.mark.asyncio
async def test_retry_success_after_429(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test retry succeeds after 429 failure."""
    monkeypatch.setenv("OC_LLM_MAX_RETRIES", "2")

    # Mock adapter to fail once with 429, then succeed
    call_count = [0]

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: fail with 429
            raise LLMProviderError("Rate limited", status_code=429, error_code="rate_limit_exceeded")
        # Second call: succeed
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="success after retry",
            finish_reason="stop",
            usage=LLMUsageModel(input_tokens=10, output_tokens=5, total_tokens=15),
        )

    # Mock asyncio.sleep to avoid delays
    with patch("asyncio.sleep", new_callable=AsyncMock):
        container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

        # Execute task
        task = container.storage.get_task(task_id)
        assert task is not None
        result = await container.orchestrator._run_worker_summarize(task, agent_id)
        assert result == "success after retry"

        # Verify LLM was called twice (1 failure + 1 success)
        assert call_count[0] == 2

        # Check events
        events = container.storage.list_events(task_id)
        event_types = [e.type for e in events]

        # Should have retry_scheduled event
        assert "llm.retry_scheduled" in event_types
        retry_events = [e for e in events if e.type == "llm.retry_scheduled"]
        assert len(retry_events) == 1
        retry_event = retry_events[0]
        assert retry_event.payload["attempt"] == 1
        assert retry_event.payload["status_code"] == 429

        # Should have final llm.completed event (no llm.failed for transient errors that succeed)
        assert "llm.completed" in event_types
        assert "llm.failed" not in event_types
        assert "llm.retry_exhausted" not in event_types

        # Verify usage was recorded (only once for successful call)
        usage_list = container.storage.list_llm_usage_by_project(project_id)
        assert len(usage_list) == 1
        usage = usage_list[0]
        assert usage.total_tokens == 15

        # Verify task succeeded
        stored_task = container.storage.get_task(task_id)
        assert stored_task is not None
        assert stored_task.status == TaskStatus.PENDING  # Not completed yet (no result stored)


@pytest.mark.asyncio
async def test_retry_exhausted_on_persistent_500(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test retry exhaustion on persistent 500 errors."""
    monkeypatch.setenv("OC_LLM_MAX_RETRIES", "2")

    # Mock adapter to always fail with 500
    call_count = [0]

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        call_count[0] += 1
        raise LLMProviderError("Server error", status_code=500, error_code="server_error")

    # Mock asyncio.sleep to avoid delays
    with patch("asyncio.sleep", new_callable=AsyncMock):
        container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

        # Execute task - should raise after retries exhausted
        task = container.storage.get_task(task_id)
        assert task is not None

        with pytest.raises(LLMProviderError) as exc_info:
            await container.orchestrator._run_worker_summarize(task, agent_id)

        # Verify LLM was called 3 times (initial + 2 retries)
        assert call_count[0] == 3
        assert exc_info.value.status_code == 500

        # Check events
        events = container.storage.list_events(task_id)
        event_types = [e.type for e in events]

        # Should have 2 retry_scheduled events (attempts 1 and 2)
        retry_events = [e for e in events if e.type == "llm.retry_scheduled"]
        assert len(retry_events) == 2
        assert retry_events[0].payload["attempt"] == 1
        assert retry_events[1].payload["attempt"] == 2

        # Should have retry_exhausted event
        assert "llm.retry_exhausted" in event_types
        exhausted_events = [e for e in events if e.type == "llm.retry_exhausted"]
        assert len(exhausted_events) == 1
        exhausted = exhausted_events[0]
        assert exhausted.payload["attempts"] == 3
        assert exhausted.payload["last_error_type"] == "LLMProviderError"
        assert exhausted.payload["last_status_code"] == 500

        # Should have final llm.failed event
        assert "llm.failed" in event_types
        failed_events = [e for e in events if e.type == "llm.failed"]
        assert len(failed_events) == 1

        # Should NOT have llm.completed
        assert "llm.completed" not in event_types

        # Verify NO usage was recorded (all calls failed)
        usage_list = container.storage.list_llm_usage_by_project(project_id)
        assert len(usage_list) == 0


@pytest.mark.asyncio
async def test_budget_check_before_retries(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str, monkeypatch: Any
) -> None:
    """Test that budget is checked before retries start."""
    # Set very low budget
    monkeypatch.setenv("OC_MAX_TOKENS_PER_TASK", "5")

    # Pre-fill usage to exceed budget
    from openchronicle.core.domain.models.project import LLMUsage

    container.storage.insert_llm_usage(
        LLMUsage(
            project_id=project_id,
            task_id=task_id,
            agent_id=agent_id,
            provider="stub",
            model="stub-model",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
    )

    # Mock adapter (should never be called)
    llm_called = [False]

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        llm_called[0] = True
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="should not be called",
            finish_reason="stop",
        )

    container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

    # Execute task - should fail at budget check
    task = container.storage.get_task(task_id)
    assert task is not None

    from openchronicle.core.domain.exceptions import BudgetExceededError

    with pytest.raises(BudgetExceededError):
        await container.orchestrator._run_worker_summarize(task, agent_id)

    # Verify LLM was NEVER called (budget check blocked it)
    assert not llm_called[0]

    # Verify NO retry events were emitted
    events = container.storage.list_events(task_id)
    event_types = [e.type for e in events]
    assert "llm.retry_scheduled" not in event_types
    assert "llm.retry_exhausted" not in event_types
    assert "llm.requested" not in event_types  # Should not get to request stage

    # Should have budget_exceeded event
    assert "llm.budget_exceeded" in event_types


@pytest.mark.asyncio
async def test_rate_limiting_disabled_by_default(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str
) -> None:
    """Test that rate limiting is disabled when no env vars are set."""
    # Ensure no rate limit env vars are set
    import os

    for key in ["OC_LLM_RPM_LIMIT", "OC_LLM_TPM_LIMIT"]:
        os.environ.pop(key, None)

    # Create fresh container without rate limits
    container2 = CoreContainer()
    project2 = container2.orchestrator.create_project("No Limits")
    agent2 = container2.orchestrator.register_agent(project_id=project2.id, name="Worker", role="worker")
    task2 = container2.orchestrator.submit_task(project2.id, "analysis.worker.summarize", {"text": "Test"})

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="no limits",
            finish_reason="stop",
        )

    container2.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

    # Execute task
    result = await container2.orchestrator._run_worker_summarize(task2, agent2.id)
    assert result == "no limits"

    # Verify NO rate_limited events
    events = container2.storage.list_events(task2.id)
    event_types = [e.type for e in events]
    assert "llm.rate_limited" not in event_types
    assert "llm.rate_limit_timeout" not in event_types

    # Should complete normally
    assert "llm.completed" in event_types


@pytest.mark.asyncio
async def test_estimated_input_tokens_in_llm_requested(
    container: CoreContainer, project_id: str, task_id: str, agent_id: str
) -> None:
    """Test that estimated_input_tokens is included in llm.requested payload."""

    async def mock_complete_async(*args: Any, **kwargs: Any) -> LLMResponse:
        return LLMResponse(
            provider="stub",
            model="stub-model",
            content="test",
            finish_reason="stop",
        )

    container.orchestrator.llm.complete_async = mock_complete_async  # type: ignore[method-assign]

    # Execute task
    task = container.storage.get_task(task_id)
    assert task is not None
    await container.orchestrator._run_worker_summarize(task, agent_id)

    # Check llm.requested event has estimated_input_tokens
    events = container.storage.list_events(task_id)
    requested_events = [e for e in events if e.type == "llm.requested"]
    assert len(requested_events) == 1
    requested = requested_events[0]
    assert "estimated_input_tokens" in requested.payload
    # Should be > 0 (we have messages)
    assert requested.payload["estimated_input_tokens"] > 0
