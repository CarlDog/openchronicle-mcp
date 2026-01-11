from __future__ import annotations

from typing import Any

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError, LLMResponse


@pytest.fixture
def container(tmp_path: Any) -> CoreContainer:
    db_path = tmp_path / "test.db"
    return CoreContainer(db_path=str(db_path))


@pytest.fixture
def project_and_task(container: CoreContainer) -> tuple[str, str]:
    project = container.orchestrator.create_project("obs-project")
    task = container.orchestrator.submit_task(
        project_id=project.id,
        task_type="analysis.worker.summarize",
        payload={"text": "hello world"},
    )
    return project.id, task.id


@pytest.fixture
def agent_id(container: CoreContainer, project_and_task: tuple[str, str]) -> str:
    from openchronicle.core.application.use_cases import register_agent

    project_id, _ = project_and_task
    agent = register_agent.execute(
        container.orchestrator,
        project_id=project_id,
        name="Worker",
        role="worker",
        provider="stub",
        model="stub-model",
    )
    return agent.id


@pytest.mark.asyncio
async def test_execution_record_emitted_on_success(
    container: CoreContainer, project_and_task: tuple[str, str], agent_id: str
) -> None:
    project_id, task_id = project_and_task

    # Run worker summarize (uses stub provider by default)
    task = container.storage.get_task(task_id)
    assert task is not None

    result = await container.orchestrator._run_worker_summarize(task, agent_id)
    assert isinstance(result, str)

    # Verify exactly one normalized execution record emitted
    events = container.storage.list_events(task_id)
    records = [e for e in events if e.type == "llm.execution_recorded"]
    assert len(records) == 1

    payload = records[0].payload

    # Outcome must be completed
    assert payload.get("outcome") == "completed"

    # Non-empty value assertions (audit-grade)
    assert payload.get("provider_requested") != "", "provider_requested must be non-empty"
    assert payload.get("provider_used") != "", "provider_used must be non-empty"
    assert payload.get("model_requested") != "", "model_requested must be non-empty"
    assert payload.get("model") != "", "model must be non-empty"
    assert payload.get("route_reference_id") not in (None, ""), "route_reference_id must be present and non-empty"

    # Equality constraints: on success, requested should match used (stub provider)
    assert payload.get("provider_requested") == payload.get(
        "provider_used"
    ), "provider_requested must match provider_used on success"
    # Note: model_requested and model may differ if routing selected one model but adapter used another
    # For stub provider, they should match
    assert payload.get("model_requested") != "", "model_requested must be populated from routing decision"


@pytest.mark.asyncio
async def test_execution_record_emitted_on_refusal(
    container: CoreContainer, project_and_task: tuple[str, str], agent_id: str
) -> None:
    project_id, task_id = project_and_task

    # Use a fake LLM adapter that consistently refuses
    class RefusingLLM(LLMPort):
        async def complete_async(
            self,
            messages: list[dict[str, Any]],
            *,
            model: str,
            max_output_tokens: int | None = None,
            temperature: float | None = None,
            provider: str | None = None,
        ) -> LLMResponse:
            raise LLMProviderError(
                "content blocked",
                status_code=400,
                error_code="content_policy_violation",
            )

    container.orchestrator.llm = RefusingLLM()

    task = container.storage.get_task(task_id)
    assert task is not None

    with pytest.raises(Exception):
        await container.orchestrator._run_worker_summarize(task, agent_id)

    # Verify exactly one normalized execution record emitted
    events = container.storage.list_events(task_id)
    records = [e for e in events if e.type == "llm.execution_recorded"]
    assert len(records) == 1

    payload = records[0].payload

    # Refusal should be classified as "refused" by error classifier
    assert payload.get("outcome") == "refused", "content_policy_violation should be classified as refusal"

    # Error code must match what we raised
    assert payload.get("error_code") == "content_policy_violation", "error_code must be preserved"

    # Non-empty value assertions (audit-grade)
    assert payload.get("provider_requested") != "", "provider_requested must be non-empty"
    assert payload.get("provider_used") != "", "provider_used must be non-empty"
    assert payload.get("model_requested") != "", "model_requested must be non-empty"
    assert payload.get("model") != "", "model must be non-empty (attempted model)"
    assert payload.get("route_reference_id") not in (
        None,
        "",
    ), "route_reference_id must be present and non-empty on failure/refusal"


@pytest.mark.asyncio
async def test_execution_id_correlates_events_on_success(
    container: CoreContainer, project_and_task: tuple[str, str], agent_id: str
) -> None:
    """Execution_id should be consistent across all events for a single LLM attempt."""
    project_id, task_id = project_and_task

    # Run worker summarize
    task = container.storage.get_task(task_id)
    assert task is not None

    result = await container.orchestrator._run_worker_summarize(task, agent_id)
    assert isinstance(result, str)

    # Get all LLM events
    events = container.storage.list_events(task_id)

    # Find llm.requested event
    requested_events = [e for e in events if e.type == "llm.requested"]
    assert len(requested_events) > 0, "llm.requested should be emitted"

    # Find llm.execution_recorded event
    recorded_events = [e for e in events if e.type == "llm.execution_recorded"]
    assert len(recorded_events) == 1, "llm.execution_recorded should be emitted once"

    # Extract execution_id from both
    req_exec_id = requested_events[0].payload.get("execution_id")
    rec_exec_id = recorded_events[0].payload.get("execution_id")

    # Both must exist and match
    assert req_exec_id not in (None, ""), "execution_id must be present in llm.requested"
    assert rec_exec_id not in (None, ""), "execution_id must be present in llm.execution_recorded"
    assert req_exec_id == rec_exec_id, "execution_id must be identical across all events for same attempt"


@pytest.mark.asyncio
async def test_execution_id_correlates_events_on_refusal(
    container: CoreContainer, project_and_task: tuple[str, str], agent_id: str
) -> None:
    """Execution_id should be consistent on terminal refusal."""
    project_id, task_id = project_and_task

    # Use a refusing LLM adapter
    class RefusingLLM(LLMPort):
        async def complete_async(
            self,
            messages: list[dict[str, Any]],
            *,
            model: str,
            max_output_tokens: int | None = None,
            temperature: float | None = None,
            provider: str | None = None,
        ) -> LLMResponse:
            raise LLMProviderError(
                "content blocked",
                status_code=400,
                error_code="content_policy_violation",
            )

    container.orchestrator.llm = RefusingLLM()

    task = container.storage.get_task(task_id)
    assert task is not None

    with pytest.raises(Exception):
        await container.orchestrator._run_worker_summarize(task, agent_id)

    # Get all LLM events
    events = container.storage.list_events(task_id)

    # Find llm.requested and llm.refused events
    requested_events = [e for e in events if e.type == "llm.requested"]
    refused_events = [e for e in events if e.type == "llm.refused"]
    recorded_events = [e for e in events if e.type == "llm.execution_recorded"]

    assert len(requested_events) > 0, "llm.requested should be emitted"
    assert len(refused_events) > 0, "llm.refused should be emitted on terminal refusal"
    assert len(recorded_events) > 0, "llm.execution_recorded should be emitted on terminal refusal"

    # Extract execution_id from all events
    req_exec_id = requested_events[0].payload.get("execution_id")
    ref_exec_id = refused_events[0].payload.get("execution_id")
    rec_exec_id = recorded_events[0].payload.get("execution_id")

    # All must exist and match
    assert req_exec_id not in (None, ""), "execution_id must be present in llm.requested"
    assert ref_exec_id not in (None, ""), "execution_id must be present in llm.refused"
    assert rec_exec_id not in (None, ""), "execution_id must be present in llm.execution_recorded"
    assert req_exec_id == ref_exec_id == rec_exec_id, "execution_id must be identical across all events"
