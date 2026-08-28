from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from openchronicle.core.domain.time_utils import utc_now

MAX_CONTENT_CHARS = 100_000
"""Upper bound on ``MemoryItem.content``, in characters (not bytes).

One constant, because this was four hardcoded literals in two driver
files and nothing in between: MCP hand-rolled the check twice, the REST
routes declared it twice via Pydantic, and the use cases had no check at
all — so the same store accepted a 200KB memory through `oc memory add`
while rejecting it over MCP and HTTP. The enforcement now lives in the
use cases; the drivers keep their declarations as fast-fail decoration
referencing this value, so raising or lowering the cap is one edit.
"""


@dataclass
class MemoryItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    pinned: bool = False
    project_id: str | None = None
    source: str = "manual"
    updated_at: datetime | None = None
