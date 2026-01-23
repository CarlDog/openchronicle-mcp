from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class InteractionHint:
    mode_hint: str
    nsfw_score: float
    requires_nsfw_capable_model: bool
    reason_codes: list[str] = field(default_factory=list)
