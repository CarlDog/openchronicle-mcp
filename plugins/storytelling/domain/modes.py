"""Engagement modes and system prompt templates for storytelling scenes."""

from __future__ import annotations

from enum import Enum


class EngagementMode(Enum):
    """How the user engages with the story."""

    PARTICIPANT = "participant"
    DIRECTOR = "director"
    AUDIENCE = "audience"


def build_system_prompt(
    mode: EngagementMode,
    *,
    instructions: list[str],
    style_guide: list[str],
    characters: list[str],
    locations: list[str],
    scenes: list[str],
    worldbuilding: list[str],
    player_character: str | None = None,
    canon: bool = True,
) -> str:
    """Assemble the full system prompt from mode + storytelling context.

    Blocks are included in priority order. Empty blocks are omitted.
    """
    parts: list[str] = []

    # 1. Mode directive
    parts.append(_mode_directive(mode, player_character))

    # 2. Canon/sandbox directive
    parts.append(_canon_directive(canon))

    # 3. Project instructions (always included)
    if instructions:
        parts.append("=== PROJECT INSTRUCTIONS ===")
        parts.extend(instructions)

    # 4. Style guide (always included)
    if style_guide:
        parts.append("=== STYLE GUIDE ===")
        parts.extend(style_guide)

    # 5. Characters
    if characters:
        parts.append("=== CHARACTERS ===")
        parts.extend(characters)

    # 6. Locations
    if locations:
        parts.append("=== LOCATIONS ===")
        parts.extend(locations)

    # 7. Recent scene history
    if scenes:
        parts.append("=== RECENT SCENES ===")
        parts.extend(scenes)

    # 8. World-building reference
    if worldbuilding:
        parts.append("=== WORLD-BUILDING ===")
        parts.extend(worldbuilding)

    return "\n\n".join(parts)


def _mode_directive(mode: EngagementMode, player_character: str | None = None) -> str:
    """Return the core system prompt for the given engagement mode."""
    if mode == EngagementMode.PARTICIPANT:
        if player_character:
            return (
                f"You are {player_character}. Stay in character at all times. "
                "Respond as this character would — use their voice, mannerisms, "
                "and knowledge. Other characters in the scene are performed by you "
                "as supporting cast, but your primary voice is this character."
            )
        return (
            "You are a character in this story. The user will tell you which "
            "character they are playing. Stay in character and respond naturally."
        )

    if mode == EngagementMode.DIRECTOR:
        return (
            "You are a scene director. The user will describe a scene setup or "
            "give direction. You perform ALL characters in the scene — give each "
            "their own voice, mannerisms, and dialogue. Narrate actions, "
            "describe the environment, and advance the scene based on the "
            "user's direction."
        )

    # AUDIENCE
    return (
        "You are a narrator telling a story. The user is your audience. "
        "Write vivid, immersive narrative prose. Perform all characters "
        "with distinct voices. Advance the plot naturally. The user may "
        "offer light guidance but is primarily here to enjoy the story."
    )


def _canon_directive(canon: bool) -> str:
    """Return the canon/sandbox directive."""
    if canon:
        return (
            "CANON MODE: All events in this scene are canon to the story's "
            "continuity. Maintain consistency with established characters, "
            "locations, and prior events. Do not contradict established facts."
        )
    return (
        "SANDBOX MODE: This scene is non-canon. You have creative freedom "
        "to explore what-if scenarios, alternate timelines, or experimental "
        "ideas without affecting the story's main continuity."
    )
