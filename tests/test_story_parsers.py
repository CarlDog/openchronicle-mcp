"""Tests for storytelling plugin parsers."""

from __future__ import annotations

from pathlib import Path

from plugins.storytelling.domain.entities import ContentType
from plugins.storytelling.parsers import (
    classify_file,
    parse_character_file,
    parse_file,
    parse_location_file,
    parse_style_guide_file,
    should_skip_file,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "storytelling"


# ---------------------------------------------------------------------------
# File classification
# ---------------------------------------------------------------------------


class TestClassifyFile:
    def test_character_by_name(self) -> None:
        assert classify_file("GhostHunters - Primary Characters.txt") == ContentType.CHARACTER

    def test_profile_by_name(self) -> None:
        assert classify_file("Character Profiles.md") == ContentType.CHARACTER

    def test_location_by_name(self) -> None:
        assert classify_file("GhostHunters - Key Locations.txt") == ContentType.LOCATION

    def test_style_guide_by_name(self) -> None:
        assert classify_file("GhostHunters - Style Guide.txt") == ContentType.STYLE_GUIDE

    def test_instructions_by_name(self) -> None:
        assert classify_file("Project Instructions.txt") == ContentType.INSTRUCTIONS

    def test_directive_by_name(self) -> None:
        assert classify_file("Canon Tracking Directive.txt") == ContentType.INSTRUCTIONS

    def test_scene_by_name(self) -> None:
        assert classify_file("Chapter 3 - The Descent.txt") == ContentType.SCENE

    def test_unknown_falls_to_worldbuilding(self) -> None:
        assert classify_file("Bestiary.txt") == ContentType.WORLDBUILDING
        assert classify_file("Faction List.md") == ContentType.WORLDBUILDING

    def test_case_insensitive(self) -> None:
        assert classify_file("PRIMARY CHARACTERS.TXT") == ContentType.CHARACTER
        assert classify_file("key LOCATIONS.txt") == ContentType.LOCATION

    def test_canon_tracking_classifies_as_instructions(self) -> None:
        assert classify_file("Canon Tracking Directive.txt") == ContentType.INSTRUCTIONS


class TestShouldSkipFile:
    def test_skip_non_canon_firepit(self) -> None:
        assert should_skip_file("GhostHunters - Non-Canon Firepit.txt") is True

    def test_skip_case_insensitive(self) -> None:
        assert should_skip_file("NON-CANON FIREPIT.txt") is True

    def test_do_not_skip_normal_files(self) -> None:
        assert should_skip_file("Primary Characters.txt") is False


# ---------------------------------------------------------------------------
# Character parsing
# ---------------------------------------------------------------------------


class TestParseCharacterFile:
    def test_splits_bracketed_profiles(self) -> None:
        text = (FIXTURES_DIR / "characters_primary.txt").read_text(encoding="utf-8")
        entities = parse_character_file(text, "TestProject")
        assert len(entities) == 2
        assert entities[0].name == "Alice Mercer"
        assert entities[1].name == "Bruno"

    def test_primary_vs_npc_by_length(self) -> None:
        text = (FIXTURES_DIR / "characters_primary.txt").read_text(encoding="utf-8")
        entities = parse_character_file(text, "TestProject")
        # Both Alice and Bruno exceed the line threshold => primary
        assert "primary" in entities[0].tags
        assert "primary" in entities[1].tags

    def test_short_profile_classified_as_npc(self) -> None:
        text = "[CHARACTER PROFILE – TINY]\n\nName: Tiny\nRole: Extra"
        entities = parse_character_file(text, "TestProject")
        assert len(entities) == 1
        assert "npc" in entities[0].tags

    def test_tags_include_story_and_character(self) -> None:
        text = (FIXTURES_DIR / "characters_primary.txt").read_text(encoding="utf-8")
        entities = parse_character_file(text, "TestProject")
        for entity in entities:
            assert "story" in entity.tags
            assert "character" in entity.tags

    def test_content_format_includes_header(self) -> None:
        text = (FIXTURES_DIR / "characters_primary.txt").read_text(encoding="utf-8")
        entities = parse_character_file(text, "TestProject")
        assert entities[0].formatted_content.startswith("[Character] Alice Mercer")
        assert "Project: TestProject" in entities[0].formatted_content

    def test_parses_name_line_format(self) -> None:
        text = (FIXTURES_DIR / "characters_npc.txt").read_text(encoding="utf-8")
        entities = parse_character_file(text, "TestProject")
        assert len(entities) == 3
        assert entities[0].name == "Martha Greenfield"
        assert entities[1].name == "Deputy Cal Rourke"
        assert entities[2].name == "Dr. Faye Ashton"

    def test_npc_format_tags_as_npc(self) -> None:
        text = (FIXTURES_DIR / "characters_npc.txt").read_text(encoding="utf-8")
        entities = parse_character_file(text, "TestProject")
        for entity in entities:
            assert "npc" in entity.tags

    def test_nothing_pinned(self) -> None:
        text = (FIXTURES_DIR / "characters_primary.txt").read_text(encoding="utf-8")
        entities = parse_character_file(text, "TestProject")
        for entity in entities:
            assert entity.pinned is False


# ---------------------------------------------------------------------------
# Location parsing
# ---------------------------------------------------------------------------


class TestParseLocationFile:
    def test_splits_entries(self) -> None:
        text = (FIXTURES_DIR / "locations.txt").read_text(encoding="utf-8")
        entities = parse_location_file(text, "TestProject")
        # Should find: town overview + 3 numbered landmarks + 2 neighboring towns = 6
        assert len(entities) >= 5

    def test_extracts_landmark_names(self) -> None:
        text = (FIXTURES_DIR / "locations.txt").read_text(encoding="utf-8")
        entities = parse_location_file(text, "TestProject")
        names = [e.name for e in entities]
        assert "The Turning Page" in names
        assert "Widow's Arch Bridge" in names

    def test_tags_include_story_and_location(self) -> None:
        text = (FIXTURES_DIR / "locations.txt").read_text(encoding="utf-8")
        entities = parse_location_file(text, "TestProject")
        for entity in entities:
            assert "story" in entity.tags
            assert "location" in entity.tags

    def test_content_format_includes_header(self) -> None:
        text = (FIXTURES_DIR / "locations.txt").read_text(encoding="utf-8")
        entities = parse_location_file(text, "TestProject")
        for entity in entities:
            assert entity.formatted_content.startswith("[Location]")
            assert "Project: TestProject" in entity.formatted_content


# ---------------------------------------------------------------------------
# Style guide parsing
# ---------------------------------------------------------------------------


class TestParseStyleGuideFile:
    def test_splits_sections(self) -> None:
        text = (FIXTURES_DIR / "style_guide.txt").read_text(encoding="utf-8")
        entities = parse_style_guide_file(text, "TestProject")
        # 3 real sections + skipped VERSION CHANGELOG = 3
        assert len(entities) == 3

    def test_extracts_section_names(self) -> None:
        text = (FIXTURES_DIR / "style_guide.txt").read_text(encoding="utf-8")
        entities = parse_style_guide_file(text, "TestProject")
        names = [e.name for e in entities]
        assert "Core Principles" in names
        assert "Dialogue Rules" in names
        assert "Weather Clause" in names

    def test_skips_version_changelog(self) -> None:
        text = (FIXTURES_DIR / "style_guide.txt").read_text(encoding="utf-8")
        entities = parse_style_guide_file(text, "TestProject")
        names = [e.name for e in entities]
        assert "Version Changelog" not in names

    def test_tags_include_story_and_style_guide(self) -> None:
        text = (FIXTURES_DIR / "style_guide.txt").read_text(encoding="utf-8")
        entities = parse_style_guide_file(text, "TestProject")
        for entity in entities:
            assert "story" in entity.tags
            assert "style-guide" in entity.tags

    def test_content_format_includes_header(self) -> None:
        text = (FIXTURES_DIR / "style_guide.txt").read_text(encoding="utf-8")
        entities = parse_style_guide_file(text, "TestProject")
        for entity in entities:
            assert entity.formatted_content.startswith("[Style Guide]")
            assert "Project: TestProject" in entity.formatted_content


# ---------------------------------------------------------------------------
# Generic / dispatch
# ---------------------------------------------------------------------------


class TestParseFile:
    def test_dispatches_to_character_parser(self) -> None:
        text = (FIXTURES_DIR / "characters_primary.txt").read_text(encoding="utf-8")
        entities = parse_file(text, ContentType.CHARACTER, "TestProject", "characters.txt")
        assert len(entities) == 2
        assert all(e.content_type == ContentType.CHARACTER for e in entities)

    def test_dispatches_to_instructions_parser(self) -> None:
        text = (FIXTURES_DIR / "instructions.txt").read_text(encoding="utf-8")
        entities = parse_file(text, ContentType.INSTRUCTIONS, "TestProject", "instructions.txt")
        assert len(entities) == 1
        assert entities[0].content_type == ContentType.INSTRUCTIONS

    def test_generic_preserves_content(self) -> None:
        entities = parse_file(
            "Some world-building lore about ancient rites.",
            ContentType.WORLDBUILDING,
            "TestProject",
            "GhostHunters - Ancient Rites.txt",
        )
        assert len(entities) == 1
        assert entities[0].content_type == ContentType.WORLDBUILDING
        assert "Ancient Rites" in entities[0].name
        assert "ancient rites" in entities[0].formatted_content
