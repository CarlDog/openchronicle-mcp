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
    assert payload.get("outcome") == "completed"
    assert payload.get("provider_requested") == payload.get("provider_used")
    assert payload.get("model") is not None
    # Verify model_requested is populated
    assert payload.get("model_requested") is not None
    # Verify route_reference_id is populated on success
    assert payload.get("route_reference_id") is not None


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
    assert payload.get("outcome") in ("failed", "refused")
    assert payload.get("error_code") is not None
    assert payload.get("provider_requested") is not None
    assert payload.get("provider_used") is not None
    # Verify model_requested is populated
    assert payload.get("model_requested") is not None
    # Verify route_reference_id is populated on failure/refusal
    assert payload.get("route_reference_id") is not None
