"""Submit a task for execution without executing it immediately."""

from __future__ import annotations

from typing import Any

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.project import Task


class InvalidTaskTypeError(ValueError):
    pass


class InvalidPluginPayloadError(ValueError):
    pass


class UnknownHandlerError(ValueError):
    pass


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
    if "." in task_type and task_type not in {"plugin.invoke", "convo.ask"}:
        raise InvalidTaskTypeError(f"Invalid task type: {task_type}")

    normalized_payload = payload

    if task_type == "plugin.invoke":
        handler_name = payload.get("handler") if isinstance(payload, dict) else None
        input_payload = payload.get("input") if isinstance(payload, dict) else None
        if not isinstance(handler_name, str) or not handler_name:
            raise InvalidPluginPayloadError("Missing or invalid payload.handler")
        if not isinstance(input_payload, dict):
            raise InvalidPluginPayloadError("Missing or invalid payload.input (must be JSON object)")

        handler = orchestrator.handler_registry.get(handler_name)
        if handler is None:
            raise UnknownHandlerError(f"Unknown handler: {handler_name}")

        normalized_payload = {"handler": handler_name, "input": input_payload}
    elif task_type != "convo.ask":
        handler = orchestrator.handler_registry.get(task_type)
        if handler is None:
            registered_types = orchestrator.handler_registry.list_task_types()
            raise DomainValidationError(
                f"Unknown task type: {task_type}. Registered task types: {', '.join(sorted(registered_types)) or 'none'}"
            )

    # Use orchestrator's submit_task which handles persistence + events
    return orchestrator.submit_task(
        project_id=project_id,
        task_type=task_type,
        payload=normalized_payload,
        parent_task_id=parent_task_id,
        agent_id=agent_id,
    )
