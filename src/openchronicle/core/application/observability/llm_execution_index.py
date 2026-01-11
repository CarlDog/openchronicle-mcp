"""In-memory index for correlating and summarizing LLM execution events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openchronicle.core.domain.models.project import Event


@dataclass
class LLMCallSummary:
    """
    Summary of a single LLM call lifecycle (request → completion/failure).

    Built from correlated events with the same execution_id.
    """

    execution_id: str
    task_id: str | None = None
    route_reference_id: str | None = None
    provider_requested: str = ""
    provider_used: str = ""
    model_requested: str = ""
    model_used: str = ""
    outcome: str = ""  # "completed" | "failed" | "refused"
    error_code: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    latency_ms: int | None = None


class LLMExecutionIndex:
    """
    In-memory index that correlates LLM events by execution_id.

    Provides deterministic summaries of LLM call lifecycles for CLI/observability.
    Not for persistence; derived from event stream.
    """

    def __init__(self) -> None:
        """Initialize empty index."""
        self._executions: dict[str, dict[str, Any]] = {}

    def ingest(self, event: Event) -> None:
        """
        Ingest an event and update execution state if relevant.

        Only tracks LLM events that have execution_id.
        """
        execution_id = event.payload.get("execution_id")
        if not execution_id or event.type not in {
            "llm.requested",
            "llm.completed",
            "llm.failed",
            "llm.refused",
            "llm.execution_recorded",
        }:
            return

        if execution_id not in self._executions:
            self._executions[execution_id] = {
                "execution_id": execution_id,
                "task_id": event.task_id,
                "events": [],
            }

        self._executions[execution_id]["events"].append(event)

    def get(self, execution_id: str) -> LLMCallSummary | None:
        """Get summary for a specific execution_id, or None if not found."""
        if execution_id not in self._executions:
            return None

        events = self._executions[execution_id]["events"]
        return self._build_summary(execution_id, events)

    def summaries(self) -> list[LLMCallSummary]:
        """
        Return all summaries in deterministic order (created_at, then execution_id).

        Ensures consistent output across multiple runs.
        """
        summaries = []
        for execution_id, data in self._executions.items():
            events = data["events"]
            summary = self._build_summary(execution_id, events)
            if summary:
                summaries.append(summary)

        # Sort by started_at (if available), then by execution_id for determinism
        return sorted(summaries, key=lambda s: (s.started_at or datetime.min, s.execution_id))

    def _build_summary(self, execution_id: str, events: list[Event]) -> LLMCallSummary:
        """Build a single summary from correlated events."""
        summary = LLMCallSummary(execution_id=execution_id)

        # Scan events to extract fields
        for event in events:
            payload = event.payload

            # From llm.requested
            if event.type == "llm.requested":
                summary.task_id = event.task_id
                if summary.started_at is None:
                    summary.started_at = event.created_at

            # From llm.completed
            elif event.type == "llm.completed":
                if summary.finished_at is None:
                    summary.finished_at = event.created_at

            # From llm.failed
            elif event.type == "llm.failed":
                summary.outcome = "failed"
                if summary.finished_at is None:
                    summary.finished_at = event.created_at

            # From llm.refused
            elif event.type == "llm.refused":
                summary.outcome = "refused"
                if summary.finished_at is None:
                    summary.finished_at = event.created_at
                if "error_code" in payload:
                    summary.error_code = payload["error_code"]

            # From llm.execution_recorded (full record)
            elif event.type == "llm.execution_recorded":
                summary.route_reference_id = payload.get("route_reference_id")
                summary.provider_requested = payload.get("provider_requested") or ""
                summary.provider_used = payload.get("provider_used") or ""
                summary.model_requested = payload.get("model_requested") or ""
                summary.model_used = payload.get("model") or ""
                summary.outcome = payload.get("outcome") or summary.outcome
                if not summary.error_code:
                    summary.error_code = payload.get("error_code")

        # Compute latency if both timestamps available
        if summary.started_at and summary.finished_at:
            delta = summary.finished_at - summary.started_at
            summary.latency_ms = int(delta.total_seconds() * 1000)

        return summary
