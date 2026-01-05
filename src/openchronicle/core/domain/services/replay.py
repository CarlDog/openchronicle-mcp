"""Task replay service for replayability and verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.domain.services.verification import VerificationResult, VerificationService


class ReplayMode(str, Enum):
    """Replay execution modes."""

    VERIFY = "verify"  # Verify hash chain only
    REPLAY_EVENTS = "replay-events"  # Reconstruct output from stored events
    DRY_RUN = "dry-run"  # Re-run routing logic without model calls


@dataclass
class ReplayResult:
    """Result of task replay."""

    mode: str
    success: bool
    task_id: str
    reconstructed_output: Any = None
    verification_result: VerificationResult | None = None  # Direct VerificationResult for verify mode
    error_message: str | None = None


class ReplayService:
    """Replays task execution for verification and debugging."""

    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage
        self.verification_service = VerificationService(storage)

    def replay_task(self, task_id: str, mode: ReplayMode) -> ReplayResult:
        """
        Replay a task in the specified mode.

        Args:
            task_id: The task to replay
            mode: Replay mode (verify, replay-events, dry-run)

        Returns:
            ReplayResult with success status and mode-specific output
        """
        task = self.storage.get_task(task_id)
        if task is None:
            return ReplayResult(
                mode=mode.value,
                success=False,
                task_id=task_id,
                error_message=f"Task not found: {task_id}",
            )

        if mode == ReplayMode.VERIFY:
            return self._verify_mode(task_id)
        if mode == ReplayMode.REPLAY_EVENTS:
            return self._replay_events_mode(task_id)
        if mode == ReplayMode.DRY_RUN:
            return self._dry_run_mode(task_id)
        return ReplayResult(
            mode=mode.value,
            success=False,
            task_id=task_id,
            error_message=f"Unknown replay mode: {mode}",
        )

    def _verify_mode(self, task_id: str) -> ReplayResult:
        """Verify hash chain integrity."""
        verification = self.verification_service.verify_task_chain(task_id)

        return ReplayResult(
            mode=ReplayMode.VERIFY.value,
            success=verification.success,
            task_id=task_id,
            verification_result=verification,
            error_message=verification.error_message if not verification.success else None,
        )

    def _replay_events_mode(self, task_id: str) -> ReplayResult:
        """Reconstruct final output from stored task result or events (no re-execution)."""
        task = self.storage.get_task(task_id)
        if task is None:
            return ReplayResult(
                mode=ReplayMode.REPLAY_EVENTS.value,
                success=False,
                task_id=task_id,
                error_message=f"Task not found: {task_id}",
            )

        # Fast path: use stored result_json if available
        if task.result_json is not None:
            try:
                result = json.loads(task.result_json)
                return ReplayResult(
                    mode=ReplayMode.REPLAY_EVENTS.value,
                    success=True,
                    task_id=task_id,
                    reconstructed_output=result,
                )
            except json.JSONDecodeError:
                # Fall through to event reconstruction if JSON is invalid
                pass

        # Fallback: reconstruct from events
        events = self.storage.list_events(task_id)

        # Find the task_completed event
        completion_event = None
        for event in reversed(events):
            if event.type == "task_completed":
                completion_event = event
                break

        if completion_event is None:
            return ReplayResult(
                mode=ReplayMode.REPLAY_EVENTS.value,
                success=False,
                task_id=task_id,
                error_message="No task_completed event found",
            )

        # Extract result from completion event
        result = completion_event.payload.get("result")

        return ReplayResult(
            mode=ReplayMode.REPLAY_EVENTS.value,
            success=True,
            task_id=task_id,
            reconstructed_output=result,
        )

    def _dry_run_mode(self, task_id: str) -> ReplayResult:
        """
        Re-run routing and supervisor logic without actual model calls.

        This is a simplified implementation that traces the execution path.
        """
        task = self.storage.get_task(task_id)
        events = self.storage.list_events(task_id)
        spans = self.storage.list_spans(task_id)

        # Reconstruct execution trace
        execution_trace = {
            "task_type": task.type if task else "unknown",
            "events_count": len(events),
            "spans_count": len(spans),
            "event_types": [e.type for e in events],
            "span_names": [s.name for s in spans],
        }

        return ReplayResult(
            mode=ReplayMode.DRY_RUN.value,
            success=True,
            task_id=task_id,
            reconstructed_output=execution_trace,
        )
