from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from openchronicle.core.domain.time_utils import utc_now


@dataclass
class MemoryItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    pinned: bool = False
    conversation_id: str | None = None
    project_id: str | None = None
    source: str = "manual"
    updated_at: datetime | None = None
