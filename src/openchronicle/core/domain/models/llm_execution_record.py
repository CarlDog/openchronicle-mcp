from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openchronicle.core.domain.models.project import _utc_now


@dataclass
class LLMExecutionRecord:
    """
    Normalized record of a single LLM execution attempt for observability.

    Domain model only: no infrastructure imports or behavior.
    """

    task_id: str
    execution_id: str
    route_reference_id: str | None = None
    provider_requested: str = ""
    provider_used: str = ""
    model_requested: str = ""
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    outcome: str = ""  # "completed" | "failed" | "refused"
    error_code: str | None = None
    created_at: datetime = field(default_factory=_utc_now)

    def to_payload(self) -> dict[str, Any]:
        """Serialize to event payload dict for consistent emission."""
        return {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "route_reference_id": self.route_reference_id,
            "provider_requested": self.provider_requested,
            "provider_used": self.provider_used,
            "model_requested": self.model_requested,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "outcome": self.outcome,
            "error_code": self.error_code,
            "created_at": self.created_at.isoformat(),
        }
