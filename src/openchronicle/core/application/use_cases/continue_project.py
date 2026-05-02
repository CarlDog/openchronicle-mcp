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
    - Lists all tasks for the project (storage returns them in
      deterministic insertion order; see SqliteStore.list_tasks_by_project)
    - Filters tasks with PENDING status, preserving that order
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

    # Filter pending tasks. Storage already returns them in (created_at,
    # rowid) order — re-sorting here by (created_at, id) would re-introduce
    # the random-UUID tiebreaker that broke this on Windows where coarse
    # clock resolution causes timestamp ties.
    pending_tasks = [t for t in tasks if t.status == TaskStatus.PENDING]

    succeeded = 0
    failed = 0
    task_ids = []

    # Execute each pending task
    for task in pending_tasks:
        task_ids.append(task.id)
        try:
            await run_task.execute(orchestrator, task.id, agent_id=task.agent_id)
            succeeded += 1
        except Exception:
            _logger.exception("Task %s failed", task.id)
            failed += 1

    return ContinueSummary(
        project_id=project_id,
        pending_tasks=len(pending_tasks),
        succeeded=succeeded,
        failed=failed,
        task_ids=task_ids,
    )
