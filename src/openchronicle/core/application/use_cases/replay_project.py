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

        # Track task lifecycle state: task_id -> {started: bool, terminal: bool, status: str}
        task_state: dict[str, dict[str, bool | str]] = {}

        # Build LLM execution index
        llm_index = LLMExecutionIndex()

        # Deterministic processing: events already ordered by created_at, id
        for event in events:
            # Track task lifecycle from events
            if event.type == "task.created":
                task_id = event.task_id
                if task_id:
                    task_state[task_id] = {
                        "started": False,
                        "terminal": False,
                        "status": "pending",
                    }

            elif event.type == "task.started":
                task_id = event.task_id
                if task_id:
                    if task_id not in task_state:
                        task_state[task_id] = {"started": False, "terminal": False, "status": "pending"}
                    task_state[task_id]["started"] = True
                    task_state[task_id]["status"] = "running"

            elif event.type == "task.completed":
                task_id = event.task_id
                if task_id:
                    if task_id not in task_state:
                        task_state[task_id] = {"started": False, "terminal": False, "status": "pending"}
                    task_state[task_id]["terminal"] = True
                    task_state[task_id]["status"] = "completed"

            elif event.type == "task.failed":
                task_id = event.task_id
                if task_id:
                    if task_id not in task_state:
                        task_state[task_id] = {"started": False, "terminal": False, "status": "pending"}
                    task_state[task_id]["terminal"] = True
                    task_state[task_id]["status"] = "failed"

            elif event.type == "task.cancelled":
                task_id = event.task_id
                if task_id:
                    if task_id not in task_state:
                        task_state[task_id] = {"started": False, "terminal": False, "status": "pending"}
                    task_state[task_id]["terminal"] = True
                    task_state[task_id]["status"] = "cancelled"

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

        # Derive task counts from accumulated state
        counts = TaskCounts()
        interrupted_ids = []

        for task_id, state in task_state.items():
            status = state["status"]
            if state["terminal"]:
                # Task reached completion/failure/cancellation
                if status == "completed":
                    counts.completed += 1
                elif status == "failed":
                    counts.failed += 1
                else:
                    # cancelled or other terminal state
                    counts.failed += 1
            elif state["started"]:
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
