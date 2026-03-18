"""Tests for storytelling plugin CLI commands."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock

from plugins.storytelling.cli import COMMAND, HELP, _extract_type_from_tags, run, setup_parser


class TestCLIProtocol:
    """Verify the plugin CLI protocol is correctly implemented."""

    def test_command_name(self) -> None:
        assert COMMAND == "story"

    def test_help_text(self) -> None:
        assert isinstance(HELP, str)
        assert len(HELP) > 0

    def test_setup_parser_registers_subcommands(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        setup_parser(sub)
        # Should not raise
        args = parser.parse_args(["story", "list", "--project-id", "test-id"])
        assert args.story_command == "list"
        assert args.project_id == "test-id"

    def test_setup_parser_import_subcommand(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        setup_parser(sub)
        args = parser.parse_args(["story", "import", "/some/path", "--project-id", "test-id"])
        assert args.story_command == "import"
        assert args.path == "/some/path"
        assert args.project_id == "test-id"

    def test_setup_parser_show_subcommand(self) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        setup_parser(sub)
        args = parser.parse_args(["story", "show", "mem-123"])
        assert args.story_command == "show"
        assert args.memory_id == "mem-123"


class TestRun:
    def test_unknown_subcommand_returns_1(self) -> None:
        args = argparse.Namespace(story_command=None)
        container = MagicMock()
        assert run(args, container) == 1

    def test_invalid_subcommand_returns_1(self) -> None:
        args = argparse.Namespace(story_command="nonexistent")
        container = MagicMock()
        assert run(args, container) == 1


class TestExtractTypeFromTags:
    def test_extracts_character(self) -> None:
        assert _extract_type_from_tags(["story", "character", "primary"]) == "character"

    def test_extracts_location(self) -> None:
        assert _extract_type_from_tags(["story", "location"]) == "location"

    def test_extracts_style_guide(self) -> None:
        assert _extract_type_from_tags(["story", "style-guide"]) == "style-guide"

    def test_unknown_returns_unknown(self) -> None:
        assert _extract_type_from_tags(["story"]) == "unknown"


class TestCmdStoryList:
    def test_list_filters_by_type(self) -> None:
        from plugins.storytelling.cli import _cmd_story_list

        container = MagicMock()
        container.storage.search_memory.return_value = []
        args = argparse.Namespace(project_id="test-id", type="character")
        result = _cmd_story_list(args, container)
        assert result == 0
        # Verify search was called with character tag
        call_kwargs = container.storage.search_memory.call_args
        assert "character" in call_kwargs.kwargs.get("tags", call_kwargs[1].get("tags", []))

    def test_list_shows_all_types(self) -> None:
        from plugins.storytelling.cli import _cmd_story_list

        container = MagicMock()
        container.storage.search_memory.return_value = []
        args = argparse.Namespace(project_id="test-id", type="all")
        result = _cmd_story_list(args, container)
        assert result == 0


class TestCmdStoryShow:
    def test_show_displays_content(self) -> None:
        from plugins.storytelling.cli import _cmd_story_show

        mock_item = MagicMock()
        mock_item.id = "test-id"
        mock_item.tags = ["story", "character"]
        mock_item.pinned = False
        mock_item.created_at = "2026-01-01T00:00:00"
        mock_item.content = "[Character] Test Character\nRole: Primary"

        container = MagicMock()
        container.storage.get_memory.return_value = mock_item
        args = argparse.Namespace(memory_id="test-id")
        result = _cmd_story_show(args, container)
        assert result == 0

    def test_show_not_found_returns_1(self) -> None:
        from plugins.storytelling.cli import _cmd_story_show

        container = MagicMock()
        container.storage.get_memory.return_value = None
        args = argparse.Namespace(memory_id="nonexistent")
        result = _cmd_story_show(args, container)
        assert result == 1
