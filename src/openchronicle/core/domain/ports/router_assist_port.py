from __future__ import annotations

from abc import ABC, abstractmethod

from openchronicle.core.domain.models.conversation import Turn
from openchronicle.core.domain.models.router_hint import RouterHint


class RouterAssistPort(ABC):
    @abstractmethod
    def analyze(self, *, user_text: str, recent_turns: list[Turn] | None = None) -> RouterHint: ...
