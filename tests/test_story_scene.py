"""Tests for storytelling scene handler and CLI."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from plugins.storytelling.application.scene_handler import generate_scene
from plugins.storytelling.domain.modes import EngagementMode

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


@dataclass
class FakeLLMResponse:
    """Minimal stand-in for LLMResponse in tests."""

    content: str
    provider: str = "stub"
    model: str = "stub-model"
    finish_reason: str = "stop"


def _make_search(items: list[FakeMemoryItem] | None = None) -> Any:
    """Create a mock memory_search."""
    items = items or []

    def search(query: str, top_k: int = 8, tags: list[str] | None = None) -> list[FakeMemoryItem]:
        results = items
        if tags:
            results = [i for i in results if all(t in i.tags for t in tags)]
        return results[:top_k]

    return search


def _make_save() -> MagicMock:
    """Create a mock memory_save that returns a FakeMemoryItem."""
    mock = MagicMock()
    mock.return_value = FakeMemoryItem(id="saved-scene-001", content="", tags=[])
    return mock


async def _make_llm(response_text: str = "The scene unfolds...") -> Any:
    """Create a mock llm_complete."""

    async def llm_complete(
        messages: list[dict[str, Any]],
        max_output_tokens: int | None = None,
        temperature: float | None = None,
    ) -> FakeLLMResponse:
        return FakeLLMResponse(content=response_text)

    return llm_complete


# ---------------------------------------------------------------------------
# Scene handler tests
# ---------------------------------------------------------------------------


class TestSceneHandler:
    @pytest.mark.asyncio
    async def test_generates_scene_text(self) -> None:
        """Scene handler returns generated text from LLM."""
        result = await generate_scene(
            memory_search=_make_search(),
            memory_save=_make_save(),
            llm_complete=await _make_llm("Carl opened the bookshop door."),
            user_prompt="Carl arrives at Ex Libris",
            mode=EngagementMode.DIRECTOR,
        )
        assert result.scene_text == "Carl opened the bookshop door."
        assert result.mode == "director"
        assert result.canon is True
        assert result.scene_id is None  # Not saved by default

    @pytest.mark.asyncio
    async def test_saves_scene_when_requested(self) -> None:
        """Scene handler saves scene as memory when save_scene=True."""
        save_mock = _make_save()
        result = await generate_scene(
            memory_search=_make_search(),
            memory_save=save_mock,
            llm_complete=await _make_llm("A saved scene."),
            user_prompt="Test scene",
            save_scene=True,
        )
        assert result.scene_id == "saved-scene-001"
        save_mock.assert_called_once()
        call_kwargs = save_mock.call_args
        assert "story" in call_kwargs.kwargs["tags"]
        assert "scene" in call_kwargs.kwargs["tags"]
        assert "canon" in call_kwargs.kwargs["tags"]

    @pytest.mark.asyncio
    async def test_sandbox_scene_tagged_correctly(self) -> None:
        """Sandbox scenes are tagged with 'sandbox' not 'canon'."""
        save_mock = _make_save()
        await generate_scene(
            memory_search=_make_search(),
            memory_save=save_mock,
            llm_complete=await _make_llm("A sandbox scene."),
            user_prompt="What if scenario",
            canon=False,
            save_scene=True,
        )
        call_kwargs = save_mock.call_args
        assert "sandbox" in call_kwargs.kwargs["tags"]
        assert "canon" not in call_kwargs.kwargs["tags"]

    @pytest.mark.asyncio
    async def test_participant_mode_with_character(self) -> None:
        """Participant mode passes player character through to result."""
        result = await generate_scene(
            memory_search=_make_search(),
            memory_save=_make_save(),
            llm_complete=await _make_llm("Carl says hello."),
            user_prompt="Greet Karen",
            mode=EngagementMode.PARTICIPANT,
            player_character="Carl Ashcombe",
        )
        assert result.mode == "participant"
        assert result.player_character == "Carl Ashcombe"

    @pytest.mark.asyncio
    async def test_context_items_counted(self) -> None:
        """characters_used reflects how many characters were assembled."""
        items = [
            FakeMemoryItem("c1", "Character 1", ["story", "character"]),
            FakeMemoryItem("c2", "Character 2", ["story", "character"]),
            FakeMemoryItem("i1", "Instructions", ["story", "instructions"]),
        ]
        result = await generate_scene(
            memory_search=_make_search(items),
            memory_save=_make_save(),
            llm_complete=await _make_llm("Scene with characters."),
            user_prompt="A scene with multiple characters",
        )
        assert result.characters_used == 2

    @pytest.mark.asyncio
    async def test_llm_receives_system_and_user_messages(self) -> None:
        """LLM receives exactly one system message and one user message."""
        received_messages: list[list[dict[str, Any]]] = []

        async def capturing_llm(
            messages: list[dict[str, Any]],
            max_output_tokens: int | None = None,
            temperature: float | None = None,
        ) -> FakeLLMResponse:
            received_messages.append(messages)
            return FakeLLMResponse(content="Response")

        await generate_scene(
            memory_search=_make_search(),
            memory_save=_make_save(),
            llm_complete=capturing_llm,
            user_prompt="Test prompt",
        )
        assert len(received_messages) == 1
        msgs = received_messages[0]
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "Test prompt"

    @pytest.mark.asyncio
    async def test_llm_temperature_forwarded(self) -> None:
        """Temperature parameter is forwarded to LLM."""
        received_temps: list[float | None] = []

        async def capturing_llm(
            messages: list[dict[str, Any]],
            max_output_tokens: int | None = None,
            temperature: float | None = None,
        ) -> FakeLLMResponse:
            received_temps.append(temperature)
            return FakeLLMResponse(content="Response")

        await generate_scene(
            memory_search=_make_search(),
            memory_save=_make_save(),
            llm_complete=capturing_llm,
            user_prompt="Test",
            temperature=0.9,
        )
        assert received_temps == [0.9]


# ---------------------------------------------------------------------------
# Plugin handler tests
# ---------------------------------------------------------------------------


class TestStoryScenePluginHandler:
    @pytest.mark.asyncio
    async def test_handler_dispatches_to_generate_scene(self) -> None:
        """story.scene handler calls generate_scene with correct params."""
        from openchronicle.core.domain.models.project import Task
        from plugins.storytelling.plugin import _story_scene_handler

        task = Task(
            id="t1",
            project_id="p1",
            type="plugin.invoke",
            payload={
                "prompt": "Carl explores the lighthouse",
                "mode": "director",
                "canon": True,
            },
        )
        context: dict[str, Any] = {
            "memory_search": _make_search(),
            "memory_save": _make_save(),
            "llm_complete": await _make_llm("Generated scene text"),
            "emit_event": MagicMock(),
            "agent_id": "agent-1",
        }
        result = await _story_scene_handler(task, context)
        assert result["scene_text"] == "Generated scene text"
        assert result["mode"] == "director"
        assert result["canon"] is True

    @pytest.mark.asyncio
    async def test_handler_rejects_invalid_mode(self) -> None:
        """story.scene handler rejects invalid engagement mode."""
        from openchronicle.core.domain.models.project import Task
        from plugins.storytelling.plugin import _story_scene_handler

        task = Task(
            id="t1",
            project_id="p1",
            type="plugin.invoke",
            payload={"prompt": "test", "mode": "invalid"},
        )
        context: dict[str, Any] = {
            "memory_search": _make_search(),
            "memory_save": _make_save(),
            "llm_complete": await _make_llm(),
            "emit_event": MagicMock(),
        }
        with pytest.raises(ValueError, match="Invalid mode"):
            await _story_scene_handler(task, context)

    @pytest.mark.asyncio
    async def test_handler_rejects_empty_prompt(self) -> None:
        """story.scene handler rejects empty prompt."""
        from openchronicle.core.domain.models.project import Task
        from plugins.storytelling.plugin import _story_scene_handler

        task = Task(
            id="t1",
            project_id="p1",
            type="plugin.invoke",
            payload={"prompt": "", "mode": "director"},
        )
        context: dict[str, Any] = {
            "memory_search": _make_search(),
            "memory_save": _make_save(),
            "llm_complete": await _make_llm(),
            "emit_event": MagicMock(),
        }
        with pytest.raises(ValueError, match="prompt is required"):
            await _story_scene_handler(task, context)

    @pytest.mark.asyncio
    async def test_handler_emits_events(self) -> None:
        """story.scene handler emits received and completed events."""
        from openchronicle.core.domain.models.project import Task
        from plugins.storytelling.plugin import _story_scene_handler

        emit_mock = MagicMock()
        task = Task(
            id="t1",
            project_id="p1",
            type="plugin.invoke",
            payload={"prompt": "test scene"},
        )
        context: dict[str, Any] = {
            "memory_search": _make_search(),
            "memory_save": _make_save(),
            "llm_complete": await _make_llm("Scene text"),
            "emit_event": emit_mock,
            "agent_id": "a1",
        }
        await _story_scene_handler(task, context)
        assert emit_mock.call_count == 2
        event_types = [call.args[0].type for call in emit_mock.call_args_list]
        assert "plugin.received_task" in event_types
        assert "plugin.completed_task" in event_types


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestStorySceneCLI:
    def test_scene_in_dispatch_table(self) -> None:
        """scene command is registered in CLI dispatch."""
        from plugins.storytelling.cli import run

        # Provide all args the handler reads before hitting project validation
        args = argparse.Namespace(
            story_command="scene",
            project_id="nonexistent",
            prompt=["test"],
            mode="director",
            sandbox=False,
            character=None,
            location=None,
            save=False,
            max_tokens=2048,
            temperature=0.8,
        )
        container = MagicMock()
        container.storage.get_project.return_value = None
        result = run(args, container)
        assert result == 1  # Project not found, but dispatch worked

    def test_scene_parser_registers(self) -> None:
        """scene subcommand is registered on the parser."""
        from plugins.storytelling.cli import setup_parser

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        setup_parser(sub)
        # Parse a valid scene command — prompt words come after all flags
        args = parser.parse_args(
            [
                "story",
                "scene",
                "--project-id",
                "test-id",
                "--mode",
                "director",
                "--",
                "Tell",
                "a",
                "story",
            ]
        )
        assert args.story_command == "scene"
        assert args.project_id == "test-id"
        assert args.mode == "director"
        assert args.prompt == ["Tell", "a", "story"]

    def test_scene_parser_sandbox_flag(self) -> None:
        """--sandbox flag sets sandbox=True."""
        from plugins.storytelling.cli import setup_parser

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        setup_parser(sub)
        args = parser.parse_args(
            [
                "story",
                "scene",
                "--project-id",
                "test-id",
                "--sandbox",
                "What if scenario",
            ]
        )
        assert args.sandbox is True

    def test_usage_includes_scene(self) -> None:
        """Usage message includes scene in command list."""
        from plugins.storytelling.cli import run

        args = argparse.Namespace(story_command=None)
        container = MagicMock()
        with patch("builtins.print") as mock_print:
            result = run(args, container)
        assert result == 1
        printed = mock_print.call_args[0][0]
        assert "scene" in printed
