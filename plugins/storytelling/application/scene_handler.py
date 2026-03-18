"""Scene generation handler — assembles context, calls LLM, optionally persists."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..application.context_assembler import StoryContext, assemble_story_context
from ..domain.modes import EngagementMode, build_system_prompt

logger = logging.getLogger(__name__)


@dataclass
class SceneResult:
    """Result from a scene generation call."""

    scene_text: str
    mode: str
    canon: bool
    player_character: str | None
    location: str | None
    characters_used: int
    scene_id: str | None  # Set if saved


async def generate_scene(
    *,
    memory_search: Any,
    memory_save: Any,
    llm_complete: Any,
    user_prompt: str,
    mode: EngagementMode = EngagementMode.DIRECTOR,
    canon: bool = True,
    player_character: str | None = None,
    location: str | None = None,
    save_scene: bool = False,
    max_output_tokens: int = 2048,
    temperature: float = 0.8,
) -> SceneResult:
    """Generate a scene using storytelling context.

    1. Assemble context from tagged memories
    2. Build system prompt for the engagement mode
    3. Call LLM via handler context
    4. Optionally persist the scene as a memory item

    Args:
        memory_search: Handler context's memory_search closure.
        memory_save: Handler context's memory_save closure.
        llm_complete: Handler context's llm_complete closure.
        user_prompt: The user's scene direction/prompt.
        mode: Engagement mode (participant, director, audience).
        canon: Whether this scene is canon (True) or sandbox (False).
        player_character: Character name for participant mode.
        location: Location hint for context retrieval.
        save_scene: Whether to persist the generated scene as a memory.
        max_output_tokens: LLM max output tokens.
        temperature: LLM temperature (higher = more creative).
    """
    # 1. Assemble context
    story_ctx: StoryContext = assemble_story_context(
        memory_search,
        user_prompt,
        player_character=player_character,
        location_hint=location,
    )

    # 2. Build system prompt
    system_prompt = build_system_prompt(
        mode,
        instructions=story_ctx.instructions,
        style_guide=story_ctx.style_guide,
        characters=story_ctx.characters,
        locations=story_ctx.locations,
        scenes=story_ctx.scenes,
        worldbuilding=story_ctx.worldbuilding,
        player_character=player_character,
        canon=canon,
    )

    # 3. Call LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    logger.info(
        "Generating scene: mode=%s, canon=%s, context_items=%d, prompt_len=%d",
        mode.value,
        canon,
        story_ctx.total_items,
        len(user_prompt),
    )

    response = await llm_complete(
        messages,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )

    scene_text = response.content

    # 4. Optionally save the scene
    scene_id: str | None = None
    if save_scene:
        canon_tag = "canon" if canon else "sandbox"
        saved = memory_save(
            content=f"[Scene] {user_prompt[:80]}\nMode: {mode.value} | Canon: {canon}\n\n{scene_text}",
            tags=["story", "scene", canon_tag],
        )
        scene_id = saved.id
        logger.info("Scene saved as memory %s (tags: story, scene, %s)", scene_id, canon_tag)

    return SceneResult(
        scene_text=scene_text,
        mode=mode.value,
        canon=canon,
        player_character=player_character,
        location=location,
        characters_used=len(story_ctx.characters),
        scene_id=scene_id,
    )
