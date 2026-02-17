"""Tests for Discord bot message handling.

Uses mocked discord.py objects and mocked CoreContainer to test the
message → use case → reply pipeline without requiring a Discord connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

discord = pytest.importorskip("discord", reason="discord.py not installed")

from openchronicle.interfaces.discord.bot import DiscordBot  # noqa: E402
from openchronicle.interfaces.discord.config import DiscordConfig  # noqa: E402


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
    user_text: str = ""
    assistant_text: str = ""
    provider: str = "stub"
    model: str = "stub-model"
    routing_reasons: list[str] = field(default_factory=list)
    memory_written_ids: list[str] = field(default_factory=list)


@dataclass
class FakeChunk:
    text: str | None = None
    finish_reason: str | None = None


class FakePreparedContext:
    """Minimal PreparedContext for testing."""

    def __init__(self) -> None:
        self.route_decision = MagicMock()
        self.messages = [{"role": "system", "content": "You are helpful."}, {"role": "user", "content": "test"}]
        self.effective_prompt = "test prompt"
        self.max_output_tokens = 512
        self.temperature = 0.2


def _make_config(
    token: str = "test-token",
    guild_ids: list[int] | None = None,
    channel_allowlist: list[int] | None = None,
    session_store_path: str = "data/discord_sessions.json",
) -> DiscordConfig:
    return DiscordConfig(
        token=token,
        guild_ids=guild_ids or [],
        channel_allowlist=channel_allowlist or [],
        session_store_path=session_store_path,
    )


def _make_container() -> Any:
    container = MagicMock()
    container.storage = MagicMock()
    container.event_logger = MagicMock()
    container.event_logger.append = MagicMock()
    container.interaction_router = MagicMock()
    container.privacy_gate = None
    container.privacy_settings = None
    container.llm = MagicMock()
    return container


def _make_message(
    content: str = "Hello", author_id: int = 12345, channel_id: int = 999, is_bot: bool = False
) -> MagicMock:
    message = MagicMock()
    message.content = content
    message.author.id = author_id
    message.author.bot = is_bot
    message.channel.id = channel_id
    message.reply = AsyncMock()
    return message


class TestDiscordBotOnMessage:
    @pytest.fixture
    def bot(self, tmp_path: Any) -> DiscordBot:
        config = _make_config(session_store_path=str(tmp_path / "sessions.json"))
        container = _make_container()

        # Patch discord.Client.__init__ to avoid actual connection setup
        with patch("discord.ext.commands.Bot.__init__", return_value=None):
            b = DiscordBot(container, config)
            # discord.py's user property reads from _connection; mock it
            mock_user = MagicMock()
            mock_user.id = 99999
            b._connection = MagicMock()
            b._connection.user = mock_user
        return b

    @pytest.mark.asyncio
    async def test_ignores_bot_messages(self, bot: DiscordBot) -> None:
        msg = _make_message(is_bot=True)
        await bot.on_message(msg)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_own_messages(self, bot: DiscordBot) -> None:
        msg = _make_message()
        msg.author = bot.user
        await bot.on_message(msg)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_empty_messages(self, bot: DiscordBot) -> None:
        msg = _make_message(content="   ")
        await bot.on_message(msg)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_allowlist_blocks(self, bot: DiscordBot) -> None:
        bot.config = _make_config(
            channel_allowlist=[111, 222],
            session_store_path=bot.config.session_store_path,
        )
        msg = _make_message(channel_id=999)
        await bot.on_message(msg)
        msg.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_channel_allowlist_allows(self, bot: DiscordBot) -> None:
        bot.config = _make_config(
            channel_allowlist=[999],
            session_store_path=bot.config.session_store_path,
        )

        bot.container.storage.get_conversation.return_value = FakeConversation()  # type: ignore[attr-defined]

        async def fake_stream(*args: Any, **kwargs: Any) -> Any:
            yield FakeChunk(text="Hello!")

        with (
            patch.object(bot, "_process_turn", new_callable=AsyncMock, return_value="Hello!"),
        ):
            msg = _make_message(channel_id=999)
            await bot.on_message(msg)
            msg.reply.assert_called()

    @pytest.mark.asyncio
    async def test_creates_conversation_on_first_message(self, bot: DiscordBot) -> None:
        bot.container.storage.get_conversation.return_value = None  # type: ignore[attr-defined]

        fake_convo = FakeConversation()
        with (
            patch(
                "openchronicle.interfaces.discord.bot.create_conversation.execute",
                return_value=fake_convo,
            ) as mock_create,
            patch.object(bot, "_process_turn", new_callable=AsyncMock, return_value="Reply"),
        ):
            msg = _make_message()
            await bot.on_message(msg)
            mock_create.assert_called_once()
            msg.reply.assert_called_once_with("Reply", mention_author=False)

    @pytest.mark.asyncio
    async def test_error_sends_friendly_message(self, bot: DiscordBot) -> None:
        bot.container.storage.get_conversation.return_value = None  # type: ignore[attr-defined]

        with patch(
            "openchronicle.interfaces.discord.bot.create_conversation.execute",
            side_effect=RuntimeError("database locked"),
        ):
            msg = _make_message()
            await bot.on_message(msg)
            msg.reply.assert_called_once()
            reply_text = msg.reply.call_args[0][0]
            assert "database locked" in reply_text
            # Should not contain stack trace
            assert "Traceback" not in reply_text

    @pytest.mark.asyncio
    async def test_long_response_split(self, bot: DiscordBot) -> None:
        bot.container.storage.get_conversation.return_value = FakeConversation()  # type: ignore[attr-defined]

        long_text = "A" * 2000 + "\n\n" + "B" * 500

        with patch.object(bot, "_process_turn", new_callable=AsyncMock, return_value=long_text):
            msg = _make_message()
            await bot.on_message(msg)
            assert msg.reply.call_count >= 2


class TestDiscordBotProcessTurn:
    @pytest.fixture
    def bot(self, tmp_path: Any) -> DiscordBot:
        config = _make_config(session_store_path=str(tmp_path / "sessions.json"))
        container = _make_container()

        with patch("discord.ext.commands.Bot.__init__", return_value=None):
            b = DiscordBot(container, config)
            b._connection = MagicMock()
        return b

    @pytest.mark.asyncio
    async def test_process_turn_pipeline(self, bot: DiscordBot) -> None:
        """Verify prepare_ask → stream → finalize pipeline runs correctly."""
        ctx = FakePreparedContext()

        async def fake_stream(*args: Any, **kwargs: Any) -> Any:
            yield FakeChunk(text="Hello ")
            yield FakeChunk(text="world!")

        with (
            patch(
                "openchronicle.interfaces.discord.bot.ask_conversation.prepare_ask",
                new_callable=AsyncMock,
                return_value=ctx,
            ) as mock_prepare,
            patch(
                "openchronicle.core.application.services.llm_execution.stream_with_route",
                side_effect=fake_stream,
            ),
            patch(
                "openchronicle.interfaces.discord.bot.ask_conversation.finalize_turn",
                new_callable=AsyncMock,
                return_value=FakeTurn(assistant_text="Hello world!"),
            ) as mock_finalize,
        ):
            result = await bot._process_turn("convo-123", "test prompt")
            assert result == "Hello world!"
            mock_prepare.assert_called_once()
            mock_finalize.assert_called_once()
