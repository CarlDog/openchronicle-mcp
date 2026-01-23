from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RouterHint:
    mode_hint: str
    nsfw_score: float
    nsfw_required: bool
    reason_codes: list[str] = field(default_factory=list)
