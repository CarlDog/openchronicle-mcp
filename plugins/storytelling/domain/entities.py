"""Domain entities for the storytelling plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContentType(Enum):
    """Types of narrative content that can be imported."""

    CHARACTER = "character"
    LOCATION = "location"
    STYLE_GUIDE = "style-guide"
    INSTRUCTIONS = "instructions"
    SCENE = "scene"
    WORLDBUILDING = "worldbuilding"
    PROJECT_META = "project-meta"


@dataclass(frozen=True)
class ParsedEntity:
    """A single parsed entity from an imported file."""

    name: str
    content_type: ContentType
    formatted_content: str
    tags: list[str] = field(default_factory=list)
    pinned: bool = False
