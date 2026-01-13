"""Derived project state view built from event replay (READ-ONLY).

This module defines lightweight dataclasses for representing the current state
of a project as derived deterministically from persisted events.

No persistence; purely for observability and future crash-safe resume capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from openchronicle.core.application.observability.execution_index import (
    LLMCallSummary,
)
from openchronicle.core.domain.models.verification_status import VerificationStatus


@dataclass
class TaskAttempt:
    """Represents a single execution attempt of a task."""

    attempt_id: str
    started: bool = False
    terminal: bool = False
    status: str = "pending"  # pending, running, completed, failed, cancelled
    verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED

    def to_dict(self) -> dict:
        """Convert to dictionary for output, including verification status."""
        return {
            "attempt_id": self.attempt_id,
            "started": self.started,
            "terminal": self.terminal,
            "status": self.status,
            "verification_status": self.verification_status.value,
        }


@dataclass
class ProjectStateView:
    """
    Derived view of current project state reconstructed from events.

    Deterministic and read-only; reflects the task lifecycle and LLM executions
    visible in the persisted event log.
    """

    project_id: str
    task_counts: TaskCounts = field(default_factory=lambda: TaskCounts())
    interrupted_task_ids: list[str] = field(default_factory=list)
    last_event_at: datetime | None = None
    llm_executions: list[LLMCallSummary] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for CLI output."""
        return {
            "project_id": self.project_id,
            "task_counts": self.task_counts.to_dict(),
            "interrupted_task_ids": self.interrupted_task_ids,
            "last_event_at": self.last_event_at.isoformat() if self.last_event_at else None,
            "llm_executions_count": len(self.llm_executions),
        }


@dataclass
class TaskCounts:
    """Count of tasks by derived status."""

    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        """Total tasks."""
        return self.pending + self.running + self.completed + self.failed

    def to_dict(self) -> dict:
        """Convert to dictionary for CLI output."""
        return {
            "pending": self.pending,
            "running": self.running,
            "completed": self.completed,
            "failed": self.failed,
            "total": self.total,
        }
