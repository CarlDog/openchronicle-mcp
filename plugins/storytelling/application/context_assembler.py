"""Storytelling context assembler — queries tagged memories and builds context blocks.

Uses the handler context's ``memory_search`` closure (pre-bound to project_id)
to retrieve content by type, then assembles into structured blocks for the
system prompt builder.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class StoryContext:
    """Assembled storytelling context ready for prompt building."""

    instructions: list[str] = field(default_factory=list)
    style_guide: list[str] = field(default_factory=list)
    characters: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    scenes: list[str] = field(default_factory=list)
    worldbuilding: list[str] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return (
            len(self.instructions)
            + len(self.style_guide)
            + len(self.characters)
            + len(self.locations)
            + len(self.scenes)
            + len(self.worldbuilding)
        )


MemorySearchFn = Any  # Callable[[str, int, list[str] | None], list[MemoryItem]]


def assemble_story_context(
    memory_search: MemorySearchFn,
    user_prompt: str,
    *,
    player_character: str | None = None,
    location_hint: str | None = None,
    max_characters: int = 10,
    max_locations: int = 5,
    max_scenes: int = 3,
    max_style_guide: int = 30,
) -> StoryContext:
    """Query tagged memories and assemble storytelling context.

    Priority tiers (all included when available):
    1. Project instructions — always included (``tags=["story", "instructions"]``)
    2. Style guide sections — always included (``tags=["story", "style-guide"]``)
    3. Characters — searched by user prompt (``tags=["story", "character"]``)
    4. Locations — searched by hint or prompt (``tags=["story", "location"]``)
    5. Recent scenes — searched by prompt (``tags=["story", "scene"]``)
    6. World-building — searched by prompt (``tags=["story", "worldbuilding"]``)

    Args:
        memory_search: Handler context's memory_search closure (pre-bound to project_id).
        user_prompt: The user's scene prompt (used for relevance-based retrieval).
        player_character: Character name for participant mode (boosts that character).
        location_hint: Explicit location name (boosts that location).
        max_characters: Maximum character profiles to include.
        max_locations: Maximum location descriptions to include.
        max_scenes: Maximum recent scenes to include.
        max_style_guide: Maximum style guide sections to include.
    """
    ctx = StoryContext()
    seen_ids: set[str] = set()

    # 1. Instructions — always include all
    instructions = memory_search("instructions", top_k=10, tags=["story", "instructions"])
    for item in instructions:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            ctx.instructions.append(item.content)

    # 2. Style guide — always include all (up to limit)
    style = memory_search("style guide", top_k=max_style_guide, tags=["story", "style-guide"])
    for item in style:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            ctx.style_guide.append(item.content)

    # 3. Characters — search by prompt + player character boost
    search_query = user_prompt
    if player_character:
        search_query = f"{player_character} {user_prompt}"
    characters = memory_search(search_query, top_k=max_characters, tags=["story", "character"])
    for item in characters:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            ctx.characters.append(item.content)

    # 4. Locations — search by hint or prompt
    loc_query = location_hint if location_hint else user_prompt
    locations = memory_search(loc_query, top_k=max_locations, tags=["story", "location"])
    for item in locations:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            ctx.locations.append(item.content)

    # 5. Recent scenes — search by prompt for continuity
    scenes = memory_search(user_prompt, top_k=max_scenes, tags=["story", "scene"])
    for item in scenes:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            ctx.scenes.append(item.content)

    # 6. World-building — search by prompt for relevant lore
    worldbuilding = memory_search(user_prompt, top_k=5, tags=["story", "worldbuilding"])
    for item in worldbuilding:
        if item.id not in seen_ids:
            seen_ids.add(item.id)
            ctx.worldbuilding.append(item.content)

    logger.info(
        "Story context assembled: %d instructions, %d style, %d chars, %d locations, %d scenes, %d worldbuilding",
        len(ctx.instructions),
        len(ctx.style_guide),
        len(ctx.characters),
        len(ctx.locations),
        len(ctx.scenes),
        len(ctx.worldbuilding),
    )

    return ctx
