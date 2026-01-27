"""Submit a task for execution without executing it immediately."""

from __future__ import annotations

from typing import Any

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.models.project import Task


def execute(
    orchestrator: OrchestratorService,
    project_id: str,
    task_type: str,
    payload: dict[str, Any],
    agent_id: str | None = None,
    parent_task_id: str | None = None,
) -> Task:
    """
    Submit a task to the orchestrator without executing it.

    Args:
        orchestrator: The orchestrator service
        project_id: Project ID for the task
        task_type: Type of task to execute
        payload: Task payload
        agent_id: Optional agent ID
        parent_task_id: Optional parent task ID

    Returns:
        The created Task

    Raises:
        ValueError: If task_type is not registered
    """
    # Validate that the task type is registered
    handler = orchestrator.handler_registry.get(task_type)
    if handler is None:
        registered_types = orchestrator.handler_registry.list_task_types()
        raise ValueError(
            f"Unknown task type: {task_type}. Registered task types: {', '.join(sorted(registered_types)) or 'none'}"
        )

    # Use orchestrator's submit_task which handles persistence + events
    return orchestrator.submit_task(
        project_id=project_id,
        task_type=task_type,
        payload=payload,
        parent_task_id=parent_task_id,
        agent_id=agent_id,
    )
