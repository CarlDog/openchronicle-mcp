"""Replay service: derives project state deterministically from persisted events.

READ-ONLY service that reconstructs the current state of a project by processing
all events in deterministic order. No mutations, no new events, no task updates.

Enables future crash-safe resume but this batch only provides the view derivation.
"""

from __future__ import annotations

from openchronicle.core.application.observability.execution_index import (
    LLMExecutionIndex,
)
from openchronicle.core.application.replay.project_state import (
    ProjectStateView,
    TaskCounts,
)
from openchronicle.core.domain.models.verification_status import VerificationStatus
from openchronicle.core.domain.ports.storage_port import StoragePort


class ReplayService:
    """
    READ-ONLY service to derive project state from events.

    Does not mutate tasks, emit new events, or change execution behavior.
    """

    def __init__(self, storage: StoragePort) -> None:
        """Initialize with storage backend."""
        self.storage = storage

    def execute(self, project_id: str) -> ProjectStateView:
        """
        Derive project state from events deterministically.

        Args:
            project_id: Project identifier

        Returns:
            ProjectStateView with derived state (read-only)
        """
        # Load all events for this project in deterministic order
        events = self.storage.list_events(project_id=project_id)

        # Initialize view
        view = ProjectStateView(project_id=project_id)

        # Track task lifecycle state: task_id -> list[TaskAttempt]
        # Each task can have multiple attempts (e.g., after resume)
        from openchronicle.core.application.replay.project_state import TaskAttempt

        task_attempts: dict[str, list[TaskAttempt]] = {}

        # Build LLM execution index
        llm_index = LLMExecutionIndex()

        # Deterministic processing: events already ordered by created_at, id
        for event in events:
            task_id = event.task_id
            if not task_id:
                # Skip project-level events for task tracking
                if event.type in {
                    "llm.requested",
                    "llm.completed",
                    "llm.failed",
                    "llm.refused",
                    "llm.execution_recorded",
                }:
                    llm_index.ingest(event)
                view.last_event_at = event.created_at
                continue

            # Track task lifecycle from events with attempt_id awareness
            if event.type == "task.created":
                if task_id not in task_attempts:
                    task_attempts[task_id] = []

            elif event.type == "task.started":
                # Extract attempt_id from payload (if present)
                attempt_id = event.payload.get("attempt_id") if event.payload else None
                if not attempt_id:
                    # Fallback: use event.id as attempt_id for backward compatibility
                    attempt_id = event.id

                # Start new attempt
                if task_id not in task_attempts:
                    task_attempts[task_id] = []
                task_attempts[task_id].append(
                    TaskAttempt(attempt_id=attempt_id, started=True, terminal=False, status="running")
                )

            elif event.type == "task.completed":
                # Extract attempt_id from payload
                attempt_id = event.payload.get("attempt_id") if event.payload else None
                if task_id in task_attempts and task_attempts[task_id]:
                    # Mark latest attempt as completed
                    latest_attempt = task_attempts[task_id][-1]
                    if not attempt_id or latest_attempt.attempt_id == attempt_id:
                        latest_attempt.terminal = True
                        latest_attempt.status = "completed"

            elif event.type == "task.failed":
                # Extract attempt_id from payload
                attempt_id = event.payload.get("attempt_id") if event.payload else None
                if task_id in task_attempts and task_attempts[task_id]:
                    # Mark latest attempt as failed
                    latest_attempt = task_attempts[task_id][-1]
                    if not attempt_id or latest_attempt.attempt_id == attempt_id:
                        latest_attempt.terminal = True
                        latest_attempt.status = "failed"

            elif event.type == "task.cancelled":
                # Extract attempt_id from payload
                attempt_id = event.payload.get("attempt_id") if event.payload else None
                if task_id in task_attempts and task_attempts[task_id]:
                    # Mark latest attempt as cancelled
                    latest_attempt = task_attempts[task_id][-1]
                    if not attempt_id or latest_attempt.attempt_id == attempt_id:
                        latest_attempt.terminal = True
                        latest_attempt.status = "cancelled"

            elif event.type == "task.verified":
                # Extract attempt_id from payload
                attempt_id = event.payload.get("attempt_id") if event.payload else None
                if task_id in task_attempts and task_attempts[task_id]:
                    # Mark latest attempt as verified
                    latest_attempt = task_attempts[task_id][-1]
                    if not attempt_id or latest_attempt.attempt_id == attempt_id:
                        latest_attempt.verification_status = VerificationStatus.VERIFIED

            elif event.type == "task.verification_failed":
                # Extract attempt_id from payload
                attempt_id = event.payload.get("attempt_id") if event.payload else None
                if task_id in task_attempts and task_attempts[task_id]:
                    # Mark latest attempt's verification as failed
                    latest_attempt = task_attempts[task_id][-1]
                    if not attempt_id or latest_attempt.attempt_id == attempt_id:
                        latest_attempt.verification_status = VerificationStatus.FAILED

            # Ingest LLM events for correlation
            if event.type in {
                "llm.requested",
                "llm.completed",
                "llm.failed",
                "llm.refused",
                "llm.execution_recorded",
            }:
                llm_index.ingest(event)

            # Track last event timestamp
            view.last_event_at = event.created_at

        # Derive task counts from accumulated attempts
        counts = TaskCounts()
        interrupted_ids = []

        for task_id, attempts in task_attempts.items():
            if not attempts:
                # Task created but never started
                counts.pending += 1
                continue

            # Check latest attempt
            latest_attempt = attempts[-1]

            if latest_attempt.terminal:
                # Task reached completion/failure/cancellation in latest attempt
                if latest_attempt.status == "completed":
                    counts.completed += 1
                elif latest_attempt.status == "failed":
                    counts.failed += 1
                else:
                    # cancelled or other terminal state
                    counts.failed += 1
            elif latest_attempt.started:
                # Started but no terminal event = interrupted
                interrupted_ids.append(task_id)
                counts.running += 1
            else:
                # Created but never started
                counts.pending += 1

        view.task_counts = counts
        view.interrupted_task_ids = sorted(interrupted_ids)

        # Include LLM execution summaries
        view.llm_executions = llm_index.summaries()

        return view
