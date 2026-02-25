"""Continue project execution by running all pending tasks."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.use_cases import run_task
from openchronicle.core.domain.models.project import TaskStatus

_logger = logging.getLogger(__name__)


@dataclass
class ContinueSummary:
    """Summary of continue operation."""

    project_id: str
    pending_tasks: int
    succeeded: int
    failed: int
    task_ids: list[str]


async def execute(orchestrator: OrchestratorService, project_id: str) -> ContinueSummary:
    """
    Continue project execution by running all pending tasks.

    This operation:
    - Lists all tasks for the project
    - Filters tasks with PENDING status
    - Sorts deterministically by created_at, then id
    - Executes each task using the run_task use case
    - Returns summary of execution results

    Args:
        orchestrator: Orchestrator service with storage access
        project_id: Project ID to continue

    Returns:
        ContinueSummary with execution results
    """
    storage = orchestrator.storage
    tasks = storage.list_tasks_by_project(project_id)

    # Filter pending tasks
    pending_tasks = [t for t in tasks if t.status == TaskStatus.PENDING]

    # Sort deterministically by created_at, then id
    pending_sorted = sorted(pending_tasks, key=lambda t: (t.created_at, t.id))

    succeeded = 0
    failed = 0
    task_ids = []

    # Execute each pending task
    for task in pending_sorted:
        task_ids.append(task.id)
        try:
            await run_task.execute(orchestrator, task.id, agent_id=task.agent_id)
            succeeded += 1
        except Exception:
            _logger.exception("Task %s failed", task.id)
            failed += 1

    return ContinueSummary(
        project_id=project_id,
        pending_tasks=len(pending_sorted),
        succeeded=succeeded,
        failed=failed,
        task_ids=task_ids,
    )
