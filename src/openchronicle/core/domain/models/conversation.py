from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str = ""
    title: str = ""
    mode: str = "general"
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class Turn:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    turn_index: int = 0
    user_text: str = ""
    assistant_text: str = ""
    provider: str = ""
    model: str = ""
    routing_reasons: list[str] = field(default_factory=list)
    memory_written_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utc_now)
