"""Resume project use case - transitions orphaned tasks back to PENDING using event replay.

Resume is driven by event replay, treating the event log as the authoritative source
of truth. The task table is a projection that may be stale after a crash.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openchronicle.core.application.services.orchestrator import OrchestratorService
from openchronicle.core.application.use_cases.replay_project import ReplayService
from openchronicle.core.domain.models.project import Event, TaskStatus

_logger = logging.getLogger(__name__)


@dataclass
class ResumeSummary:
    """Summary of resume operation."""

    project_id: str
    orphaned_to_pending: int
    pending: int
    running: int
    completed: int
    failed: int


def execute(orchestrator: OrchestratorService, project_id: str) -> ResumeSummary:
    """
    Resume a project using event replay to identify interrupted tasks.

    Instead of relying on task table status, this uses ReplayService to derive
    the authoritative list of interrupted tasks from persisted events. An interrupted
    task is one that has a task.started event but no terminal event.

    For each interrupted task:
    1. Check if task.orphaned event already exists (idempotency)
    2. If not, emit task.orphaned event explaining the repair
    3. Transition task status to PENDING

    This operation is idempotent:
    - Calling resume multiple times produces same result
    - task.orphaned events are emitted at most once per task
    - Task table is updated only when needed

    Args:
        orchestrator: Orchestrator service with storage access
        project_id: Project ID to resume

    Returns:
        ResumeSummary with counts of tasks by status after resume
    """
    storage = orchestrator.storage

    # Use event replay to authoritatively identify interrupted tasks
    replay_service = ReplayService(storage)
    derived_state = replay_service.execute(project_id)

    # Get all tasks for status updates
    all_tasks = storage.list_tasks_by_project(project_id)
    task_by_id = {t.id: t for t in all_tasks}

    # Get existing orphan events for idempotency check
    all_events = storage.list_events(project_id=project_id)
    orphaned_task_ids = {e.task_id for e in all_events if e.type == "task.orphaned" and e.task_id is not None}

    # Emit orphan event for each interrupted task (if not already done)
    # Process in deterministic order (same as derived state)
    newly_orphaned = []
    for task_id in derived_state.interrupted_task_ids:
        if task_id not in orphaned_task_ids:
            # First time handling this task: emit orphan event
            task = task_by_id.get(task_id)
            if task:
                storage.append_event(
                    Event(
                        project_id=project_id,
                        task_id=task_id,
                        agent_id=task.agent_id,
                        type="task.orphaned",
                        payload={
                            "task_id": task_id,
                            "task_type": task.type,
                            "reason": "resume_by_replay",
                            "derived_from": "events",
                            "explanation": "Task has task.started event but no terminal event; was interrupted by crash",
                        },
                    )
                )

                # Transition to PENDING
                storage.update_task_status(task_id, TaskStatus.PENDING.value)
                newly_orphaned.append(task_id)

    # Count final status distribution (re-fetch to get updated statuses)
    tasks_after = storage.list_tasks_by_project(project_id)
    counts = {
        "pending": sum(1 for t in tasks_after if t.status == TaskStatus.PENDING),
        "running": sum(1 for t in tasks_after if t.status == TaskStatus.RUNNING),
        "completed": sum(1 for t in tasks_after if t.status == TaskStatus.COMPLETED),
        "failed": sum(1 for t in tasks_after if t.status == TaskStatus.FAILED),
    }

    # Emit project.resumed event with summary
    # Include replay-derived counts for transparency
    storage.append_event(
        Event(
            project_id=project_id,
            task_id=None,
            agent_id=None,
            type="project.resumed",
            payload={
                "project_id": project_id,
                "orphaned_to_pending": len(newly_orphaned),
                "newly_orphaned_task_ids": newly_orphaned,
                "pending": counts["pending"],
                "running": counts["running"],
                "completed": counts["completed"],
                "failed": counts["failed"],
                "total_tasks": len(tasks_after),
                "resume_method": "replay_by_events",
                "interrupted_count_from_replay": len(derived_state.interrupted_task_ids),
            },
        )
    )

    return ResumeSummary(
        project_id=project_id,
        orphaned_to_pending=len(newly_orphaned),
        pending=counts["pending"],
        running=counts["running"],
        completed=counts["completed"],
        failed=counts["failed"],
    )
