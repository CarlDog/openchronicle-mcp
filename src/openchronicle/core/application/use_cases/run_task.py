from __future__ import annotations

from typing import Any

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.models.project import Task


def submit(
    orchestrator: OrchestratorService,
    project_id: str,
    task_type: str,
    payload: dict[str, Any],
    parent_task_id: str | None = None,
    agent_id: str | None = None,
) -> Task:
    return orchestrator.submit_task(
        project_id=project_id,
        task_type=task_type,
        payload=payload,
        parent_task_id=parent_task_id,
        agent_id=agent_id,
    )


async def execute(orchestrator: OrchestratorService, task_id: str, agent_id: str | None = None) -> Any:
    return await orchestrator.execute_task(task_id=task_id, agent_id=agent_id)
