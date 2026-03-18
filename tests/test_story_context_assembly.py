"""Tests for storytelling context assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from plugins.storytelling.application.context_assembler import StoryContext, assemble_story_context
from plugins.storytelling.domain.modes import EngagementMode, build_system_prompt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeMemoryItem:
    """Minimal stand-in for MemoryItem in tests."""

    id: str
    content: str
    tags: list[str]
    pinned: bool = False


def _make_search(items: list[FakeMemoryItem]) -> Any:
    """Create a mock memory_search that filters by tags."""

    def search(query: str, top_k: int = 8, tags: list[str] | None = None) -> list[FakeMemoryItem]:
        results = items
        if tags:
            results = [i for i in results if all(t in i.tags for t in tags)]
        return results[:top_k]

    return search


# ---------------------------------------------------------------------------
# Context assembly tests
# ---------------------------------------------------------------------------


class TestStoryContextAssembly:
    def test_assembles_all_tiers(self) -> None:
        """Context assembler pulls from all 6 content tiers."""
        items = [
            FakeMemoryItem("i1", "Follow the style guide.", ["story", "instructions"]),
            FakeMemoryItem("sg1", "Use present tense.", ["story", "style-guide"]),
            FakeMemoryItem("c1", "[Character] Carl Ashcombe\nAge: 42", ["story", "character", "primary"]),
            FakeMemoryItem("l1", "[Location] The Lighthouse\nA coastal beacon.", ["story", "location"]),
            FakeMemoryItem("sc1", "[Scene] Opening\nCarl arrives.", ["story", "scene", "canon"]),
            FakeMemoryItem("w1", "The town was founded in 1842.", ["story", "worldbuilding"]),
        ]
        ctx = assemble_story_context(_make_search(items), "Carl explores the lighthouse")
        assert len(ctx.instructions) == 1
        assert len(ctx.style_guide) == 1
        assert len(ctx.characters) == 1
        assert len(ctx.locations) == 1
        assert len(ctx.scenes) == 1
        assert len(ctx.worldbuilding) == 1
        assert ctx.total_items == 6

    def test_deduplicates_across_tiers(self) -> None:
        """Items that match multiple queries are only included once."""
        # An item tagged both instructions and style-guide would match both queries
        dual_tag = FakeMemoryItem("d1", "Dual-tagged item", ["story", "instructions", "style-guide"])
        ctx = assemble_story_context(_make_search([dual_tag]), "test")
        # Should only appear in instructions (first tier to claim it)
        assert ctx.total_items == 1
        assert len(ctx.instructions) == 1
        assert len(ctx.style_guide) == 0

    def test_empty_project_returns_empty_context(self) -> None:
        """Empty project produces empty context with no errors."""
        ctx = assemble_story_context(_make_search([]), "test prompt")
        assert ctx.total_items == 0
        assert ctx.instructions == []
        assert ctx.characters == []

    def test_player_character_boosts_search(self) -> None:
        """When player_character is set, search query includes character name."""
        calls: list[dict[str, Any]] = []

        def tracking_search(query: str, top_k: int = 8, tags: list[str] | None = None) -> list[FakeMemoryItem]:
            calls.append({"query": query, "tags": tags})
            return []

        assemble_story_context(tracking_search, "explore the cave", player_character="Carl")
        # The character search should include "Carl" in the query
        char_calls = [c for c in calls if c["tags"] and "character" in c["tags"]]
        assert len(char_calls) == 1
        assert "Carl" in char_calls[0]["query"]

    def test_location_hint_used_for_location_search(self) -> None:
        """When location_hint is set, location search uses it instead of prompt."""
        calls: list[dict[str, Any]] = []

        def tracking_search(query: str, top_k: int = 8, tags: list[str] | None = None) -> list[FakeMemoryItem]:
            calls.append({"query": query, "tags": tags})
            return []

        assemble_story_context(tracking_search, "tell a story", location_hint="The Lighthouse")
        loc_calls = [c for c in calls if c["tags"] and "location" in c["tags"]]
        assert len(loc_calls) == 1
        assert "The Lighthouse" in loc_calls[0]["query"]

    def test_respects_max_characters_limit(self) -> None:
        """Only max_characters items are included for characters."""
        items = [FakeMemoryItem(f"c{i}", f"Character {i}", ["story", "character"]) for i in range(20)]
        ctx = assemble_story_context(_make_search(items), "test", max_characters=5)
        assert len(ctx.characters) == 5

    def test_respects_max_scenes_limit(self) -> None:
        """Only max_scenes items are included for scenes."""
        items = [FakeMemoryItem(f"s{i}", f"Scene {i}", ["story", "scene"]) for i in range(10)]
        ctx = assemble_story_context(_make_search(items), "test", max_scenes=3)
        assert len(ctx.scenes) == 3

    def test_total_items_property(self) -> None:
        """StoryContext.total_items counts across all tiers."""
        ctx = StoryContext(
            instructions=["a"],
            style_guide=["b", "c"],
            characters=["d"],
            locations=[],
            scenes=["e"],
            worldbuilding=[],
        )
        assert ctx.total_items == 5


# ---------------------------------------------------------------------------
# Engagement mode tests
# ---------------------------------------------------------------------------


class TestEngagementModes:
    def test_participant_mode_names_character(self) -> None:
        """Participant mode includes player character name in directive."""
        prompt = build_system_prompt(
            EngagementMode.PARTICIPANT,
            instructions=[],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
            player_character="Carl Ashcombe",
        )
        assert "Carl Ashcombe" in prompt
        assert "Stay in character" in prompt

    def test_participant_mode_no_character(self) -> None:
        """Participant mode without character uses generic directive."""
        prompt = build_system_prompt(
            EngagementMode.PARTICIPANT,
            instructions=[],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
            player_character=None,
        )
        assert "which character" in prompt.lower()

    def test_director_mode_directive(self) -> None:
        """Director mode tells AI to perform all characters."""
        prompt = build_system_prompt(
            EngagementMode.DIRECTOR,
            instructions=[],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
        )
        assert "director" in prompt.lower()
        assert "ALL characters" in prompt

    def test_audience_mode_directive(self) -> None:
        """Audience mode tells AI to narrate."""
        prompt = build_system_prompt(
            EngagementMode.AUDIENCE,
            instructions=[],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
        )
        assert "narrator" in prompt.lower()

    def test_canon_directive(self) -> None:
        """Canon mode includes continuity directive."""
        prompt = build_system_prompt(
            EngagementMode.DIRECTOR,
            instructions=[],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
            canon=True,
        )
        assert "CANON MODE" in prompt
        assert "consistency" in prompt.lower()

    def test_sandbox_directive(self) -> None:
        """Sandbox mode includes non-canon directive."""
        prompt = build_system_prompt(
            EngagementMode.DIRECTOR,
            instructions=[],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
            canon=False,
        )
        assert "SANDBOX MODE" in prompt
        assert "non-canon" in prompt.lower()

    def test_system_prompt_includes_instructions(self) -> None:
        """System prompt includes project instructions block."""
        prompt = build_system_prompt(
            EngagementMode.DIRECTOR,
            instructions=["Always write in British English."],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
        )
        assert "PROJECT INSTRUCTIONS" in prompt
        assert "British English" in prompt

    def test_system_prompt_includes_style_guide(self) -> None:
        """System prompt includes style guide block."""
        prompt = build_system_prompt(
            EngagementMode.DIRECTOR,
            instructions=[],
            style_guide=["Use present tense.", "Avoid passive voice."],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
        )
        assert "STYLE GUIDE" in prompt
        assert "present tense" in prompt
        assert "passive voice" in prompt

    def test_system_prompt_omits_empty_blocks(self) -> None:
        """Empty content blocks are not included in the prompt."""
        prompt = build_system_prompt(
            EngagementMode.DIRECTOR,
            instructions=[],
            style_guide=[],
            characters=[],
            locations=[],
            scenes=[],
            worldbuilding=[],
        )
        assert "CHARACTERS" not in prompt
        assert "LOCATIONS" not in prompt
        assert "RECENT SCENES" not in prompt
        assert "WORLD-BUILDING" not in prompt

    def test_system_prompt_includes_characters(self) -> None:
        """System prompt includes character block when characters present."""
        prompt = build_system_prompt(
            EngagementMode.DIRECTOR,
            instructions=[],
            style_guide=[],
            characters=["[Character] Carl Ashcombe\nAge: 42\nBookstore owner"],
            locations=[],
            scenes=[],
            worldbuilding=[],
        )
        assert "CHARACTERS" in prompt
        assert "Carl Ashcombe" in prompt


class TestEngagementModeEnum:
    def test_all_modes_have_values(self) -> None:
        """All engagement modes have string values."""
        assert EngagementMode.PARTICIPANT.value == "participant"
        assert EngagementMode.DIRECTOR.value == "director"
        assert EngagementMode.AUDIENCE.value == "audience"

    def test_mode_from_string(self) -> None:
        """Engagement mode can be constructed from string value."""
        assert EngagementMode("participant") == EngagementMode.PARTICIPANT
        assert EngagementMode("director") == EngagementMode.DIRECTOR
        assert EngagementMode("audience") == EngagementMode.AUDIENCE

    def test_invalid_mode_raises(self) -> None:
        """Invalid mode string raises ValueError."""
        with pytest.raises(ValueError):
            EngagementMode("invalid_mode")
