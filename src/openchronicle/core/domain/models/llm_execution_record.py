from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from openchronicle.core.domain.models.project import _utc_now


@dataclass
class LLMExecutionRecord:
    """
    Normalized record of a single LLM execution attempt for observability.

    Domain model only: no infrastructure imports or behavior.
    """

    task_id: str
    route_reference_id: str | None = None
    provider_requested: str = ""
    provider_used: str = ""
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    outcome: str = ""  # "completed" | "failed" | "refused"
    error_code: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
