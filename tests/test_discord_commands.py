"""Tests for Discord slash commands.

Uses mocked discord.py interaction objects and mocked container to test
slash command → use case delegation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("discord", reason="discord.py not installed")

from openchronicle.interfaces.discord.commands import OpenChronicleCog  # noqa: E402


@dataclass
class FakeConversation:
    id: str = "convo-123"
    project_id: str = "proj-123"
    title: str = "Discord chat"
    mode: str = "general"


@dataclass
class FakeTurn:
    id: str = "turn-1"
    conversation_id: str = "convo-123"
    turn_index: int = 0
    user_text: str = "Hello"
    assistant_text: str = "Hi there!"
    provider: str = "stub"
    model: str = "stub-model"
    routing_reasons: list[str] = field(default_factory=lambda: ["quality"])
    memory_written_ids: list[str] = field(default_factory=list)


@dataclass
class FakeMemoryItem:
    id: str = "mem-1"
    content: str = "test"


def _make_bot(tmp_path: Any) -> MagicMock:
    bot = MagicMock()
    bot.container = MagicMock()
    bot.container.storage = MagicMock()
    bot.container.event_logger = MagicMock()
    bot.container.event_logger.append = MagicMock()

    from openchronicle.interfaces.discord.config import DiscordConfig
    from openchronicle.interfaces.discord.session import SessionManager

    bot.config = DiscordConfig(
        token="test-token",
        guild_ids=[],
        channel_allowlist=[],
        session_store_path=str(tmp_path / "sessions.json"),
    )
    bot.sessions = SessionManager(str(tmp_path / "sessions.json"))
    return bot


def _make_interaction(user_id: int = 12345) -> MagicMock:
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    return interaction


class TestNewConvo:
    @pytest.mark.asyncio
    async def test_clears_session(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.sessions.set_conversation_id("12345", "convo-old")

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()
        await cog.newconvo.callback(cog, interaction)

        assert bot.sessions.get_conversation_id("12345") is None
        interaction.response.send_message.assert_called_once()
        assert "New conversation" in interaction.response.send_message.call_args[0][0]


class TestRemember:
    @pytest.mark.asyncio
    async def test_no_conversation(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.remember.callback(cog, interaction, text="remember this")
        interaction.response.send_message.assert_called_once()
        assert "No active" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_saves_memory(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.sessions.set_conversation_id("12345", "convo-123")
        bot.container.storage.get_conversation.return_value = FakeConversation()

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        with patch(
            "openchronicle.interfaces.discord.commands.add_memory.execute",
            return_value=FakeMemoryItem(),
        ) as mock_add:
            await cog.remember.callback(cog, interaction, text="remember this")
            mock_add.assert_called_once()
            interaction.response.send_message.assert_called_once()
            assert "Remembered" in interaction.response.send_message.call_args[0][0]


class TestForget:
    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.container.storage.get_memory.return_value = None

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.forget.callback(cog, interaction, memory_id="nonexistent")
        interaction.response.send_message.assert_called_once()
        assert "not found" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_deletes_memory(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.container.storage.get_memory.return_value = FakeMemoryItem()

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.forget.callback(cog, interaction, memory_id="mem-1")
        bot.container.storage.delete_memory.assert_called_once_with("mem-1")
        assert "Deleted" in interaction.response.send_message.call_args[0][0]


class TestExplain:
    @pytest.mark.asyncio
    async def test_no_conversation(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.explain.callback(cog, interaction)
        assert "No active" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_shows_turn_details(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.sessions.set_conversation_id("12345", "convo-123")
        bot.container.storage.list_turns.return_value = [FakeTurn()]

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.explain.callback(cog, interaction)
        reply = interaction.response.send_message.call_args[0][0]
        assert "stub" in reply
        assert "stub-model" in reply


class TestMode:
    @pytest.mark.asyncio
    async def test_no_conversation(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        choice = MagicMock()
        choice.value = "fast"

        await cog.mode.callback(cog, interaction, mode=choice)
        assert "No active" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_sets_mode(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.sessions.set_conversation_id("12345", "convo-123")

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        choice = MagicMock()
        choice.value = "general"

        with patch(
            "openchronicle.interfaces.discord.commands.convo_mode.set_mode",
            return_value="general",
        ):
            await cog.mode.callback(cog, interaction, mode=choice)
            assert "general" in interaction.response.send_message.call_args[0][0]


class TestHistory:
    @pytest.mark.asyncio
    async def test_no_conversation(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.history.callback(cog, interaction, limit=5)
        assert "No active" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_shows_turns(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.sessions.set_conversation_id("12345", "convo-123")
        bot.container.storage.list_turns.return_value = [
            FakeTurn(turn_index=0, user_text="Hello", assistant_text="Hi!"),
            FakeTurn(turn_index=1, user_text="How?", assistant_text="Fine!"),
        ]

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.history.callback(cog, interaction, limit=5)
        reply = interaction.response.send_message.call_args[0][0]
        assert "Turn 0" in reply
        assert "Turn 1" in reply

    @pytest.mark.asyncio
    async def test_no_turns(self, tmp_path: Any) -> None:
        bot = _make_bot(tmp_path)
        bot.sessions.set_conversation_id("12345", "convo-123")
        bot.container.storage.list_turns.return_value = []

        cog = OpenChronicleCog(bot)
        interaction = _make_interaction()

        await cog.history.callback(cog, interaction, limit=5)
        assert "No turns" in interaction.response.send_message.call_args[0][0]
