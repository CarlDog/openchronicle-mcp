"""Model for smoke test execution results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openchronicle.core.domain.models.failure_category import FailureCategory
from openchronicle.core.domain.time_utils import utc_now


@dataclass
class SmokeResult:
    """Result of a single smoke test execution.

    Captures all relevant details about a minimal end-to-end LLM call
    including IDs, provider/model selection, and outcomes.
    """

    project_id: str
    task_id: str
    attempt_id: str
    execution_id: str
    provider_requested: str | None = None  # Requested provider (from --provider flag or None)
    provider_used: str = ""  # Actually used provider (from routing)
    model_requested: str | None = None  # Requested model (from --model flag or None)
    model_used: str = ""  # Actually used model (from routing)
    prompt_text: str = ""  # The prompt that was sent
    outcome: str = ""  # "completed", "blocked", "failed", "refused"
    error_code: str | None = None  # Error code if failed/blocked
    error_message: str | None = None  # Human-readable error message
    failure_category: FailureCategory | None = None  # Failure classification (PROVIDER_ERROR, BUDGET_BLOCKED, etc.)
    prompt_tokens: int | None = None  # Input tokens
    completion_tokens: int | None = None  # Output tokens
    total_tokens: int | None = None  # Total tokens
    latency_ms: int | None = None  # LLM call latency
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON output."""
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "attempt_id": self.attempt_id,
            "execution_id": self.execution_id,
            "provider_requested": self.provider_requested,
            "provider_used": self.provider_used,
            "model_requested": self.model_requested,
            "model_used": self.model_used,
            "outcome": self.outcome,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "failure_category": self.failure_category,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "created_at": self.created_at.isoformat(),
        }
