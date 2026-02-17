"""Discord interface integration tests against real infrastructure.

These tests exercise the Discord bot's glue code — session management,
conversation resolution, and the streaming turn pipeline — against a real
CoreContainer with real SQLite and a real LLM provider.

Gate: OC_INTEGRATION_TESTS=1.
Config: auto-detected by ``conftest.py`` (config dir, provider).

Usage:
    export OC_INTEGRATION_TESTS=1
    pytest tests/integration/test_discord_integration.py -v
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

discord_lib = pytest.importorskip("discord", reason="discord.py not installed")

from openchronicle.core.application.runtime.container import CoreContainer  # noqa: E402
from openchronicle.core.application.use_cases import add_memory  # noqa: E402
from openchronicle.core.domain.models.memory_item import MemoryItem  # noqa: E402
from openchronicle.core.domain.services.verification import VerificationService  # noqa: E402
from openchronicle.interfaces.discord.bot import DiscordBot  # noqa: E402
from openchronicle.interfaces.discord.config import DiscordConfig  # noqa: E402

# Skip entire module unless integration test env var is set
pytestmark = [
    pytest.mark.skipif(
        os.getenv("OC_INTEGRATION_TESTS") != "1",
        reason="Integration tests skipped unless OC_INTEGRATION_TESTS=1",
    ),
    pytest.mark.integration,
]


# ---------------------------------------------------------------------------
# Module-level shared state for cross-test references
# Tests are ordered by name (td01, td02, ...) and later tests may reference
# state stored by earlier tests to avoid redundant API calls.
# ---------------------------------------------------------------------------
_shared: dict[str, Any] = {}


@pytest.fixture(scope="module")
def tmp_db_dir() -> Any:
    """Temp directory for the test database, cleaned up after the module."""
    with tempfile.TemporaryDirectory(prefix="oc_discord_integ_") as d:
        yield d


@pytest.fixture(scope="module")
def container(tmp_db_dir: str) -> Any:
    """Module-scoped container — config/provider set by conftest."""
    db_path = str(Path(tmp_db_dir) / "test_discord.db")
    c = CoreContainer(db_path=db_path)
    yield c
    c.storage._conn.close()


@pytest.fixture(scope="module")
def bot(container: CoreContainer, tmp_db_dir: str) -> DiscordBot:
    """Real CoreContainer, patched Bot.__init__ (no Discord connection)."""
    config = DiscordConfig(
        token="test-key",
        guild_ids=[],
        channel_allowlist=[],
        session_store_path=str(Path(tmp_db_dir) / "sessions.json"),
    )

    with patch("discord.ext.commands.Bot.__init__", return_value=None):
        b = DiscordBot(container, config)
        mock_user = MagicMock()
        mock_user.id = 99999
        b._connection = MagicMock()
        b._connection.user = mock_user

    return b


# ---------------------------------------------------------------------------
# TD01: First message creates conversation
# ---------------------------------------------------------------------------


async def test_td01_first_message_creates_conversation(bot: DiscordBot) -> None:
    """Resolve a new user → conversation created, process_turn → real LLM reply."""
    conversation_id = await bot._resolve_conversation("user-A")
    _shared["user_a_convo_id"] = conversation_id

    # Conversation exists in DB
    convo = bot.container.storage.get_conversation(conversation_id)
    assert convo is not None, "Conversation should exist in DB"

    # Session mapping stored
    assert bot.sessions.get_conversation_id("user-A") == conversation_id

    # Process a real turn
    response = await bot._process_turn(conversation_id, "What is 2+2? Reply with just the number.")
    _shared["td01_response"] = response

    assert response.strip() != "", "Response should be non-empty"
    assert "4" in response, f"Expected '4' in response, got: {response!r}"

    # Turn persisted with real provider/model
    turns = bot.container.storage.list_turns(conversation_id)
    assert len(turns) == 1
    assert turns[0].provider != "stub", f"Provider should not be stub, got: {turns[0].provider!r}"
    assert turns[0].model != "", "Model should be a real model name"


# ---------------------------------------------------------------------------
# TD02: Second message reuses conversation
# ---------------------------------------------------------------------------


async def test_td02_second_message_reuses_conversation(bot: DiscordBot) -> None:
    """Same user resolves to same conversation; second turn persisted."""
    original_id = _shared.get("user_a_convo_id")
    if original_id is None:
        pytest.skip("TD01 did not run")

    conversation_id = await bot._resolve_conversation("user-A")
    assert conversation_id == original_id, "Should reuse existing conversation"

    response = await bot._process_turn(conversation_id, "What did I just ask you?")
    assert response.strip() != ""

    turns = bot.container.storage.list_turns(conversation_id)
    assert len(turns) == 2, f"Expected 2 turns, got: {len(turns)}"
    assert turns[0].conversation_id == turns[1].conversation_id == original_id


# ---------------------------------------------------------------------------
# TD03: Multi-user isolation
# ---------------------------------------------------------------------------


async def test_td03_multi_user_isolation(bot: DiscordBot) -> None:
    """Different user gets a separate conversation."""
    user_a_id = _shared.get("user_a_convo_id")
    if user_a_id is None:
        pytest.skip("TD01 did not run")

    conversation_id = await bot._resolve_conversation("user-B")
    _shared["user_b_convo_id"] = conversation_id

    assert conversation_id != user_a_id, "User B should get a different conversation"

    response = await bot._process_turn(conversation_id, "Say hello.")
    assert response.strip() != ""

    # User B: 1 turn; User A: still 2 turns
    turns_b = bot.container.storage.list_turns(conversation_id)
    turns_a = bot.container.storage.list_turns(user_a_id)
    assert len(turns_b) == 1, f"User B expected 1 turn, got: {len(turns_b)}"
    assert len(turns_a) == 2, f"User A expected 2 turns, got: {len(turns_a)}"


# ---------------------------------------------------------------------------
# TD04: /newconvo creates fresh conversation
# ---------------------------------------------------------------------------


async def test_td04_newconvo_creates_fresh_conversation(bot: DiscordBot) -> None:
    """Clearing session and resolving again gives a new conversation ID."""
    original_id = _shared.get("user_a_convo_id")
    if original_id is None:
        pytest.skip("TD01 did not run")

    # Simulate /newconvo: clear session mapping
    bot.sessions.clear("user-A")

    new_conversation_id = await bot._resolve_conversation("user-A")
    _shared["user_a_new_convo_id"] = new_conversation_id

    assert new_conversation_id != original_id, "Should be a brand new conversation"

    # Old conversation and turns still exist
    old_convo = bot.container.storage.get_conversation(original_id)
    assert old_convo is not None, "Old conversation should still exist"
    old_turns = bot.container.storage.list_turns(original_id)
    assert len(old_turns) == 2, "Old conversation turns should be preserved"


# ---------------------------------------------------------------------------
# TD05: Memory save and recall via Discord path
# ---------------------------------------------------------------------------


async def test_td05_memory_save_and_recall(bot: DiscordBot) -> None:
    """Save memory with source='discord', then verify recall in next turn."""
    convo_id = _shared.get("user_a_new_convo_id")
    if convo_id is None:
        pytest.skip("TD04 did not run")

    conversation = bot.container.storage.get_conversation(convo_id)
    assert conversation is not None

    # Save memory the same way commands.py does
    add_memory.execute(
        store=bot.container.storage,
        emit_event=bot.container.event_logger.append,
        item=MemoryItem(
            content="The user's favorite color is chartreuse",
            conversation_id=convo_id,
            project_id=conversation.project_id,
            source="discord",
        ),
    )

    # Ask about it in next turn — memory should be retrieved
    response = await bot._process_turn(convo_id, "What is my favorite color?")
    assert "chartreuse" in response.lower(), f"Expected 'chartreuse' in response, got: {response!r}"

    # Verify memory.retrieved event was emitted
    events = bot.container.storage.list_events(task_id=convo_id)
    memory_events = [e for e in events if e.type == "memory.retrieved"]
    assert len(memory_events) > 0, "Expected memory.retrieved event"
    assert memory_events[-1].payload["relevant_count"] >= 1


# ---------------------------------------------------------------------------
# TD06: Stale session auto-recovers
# ---------------------------------------------------------------------------


async def test_td06_stale_session_auto_recovers(bot: DiscordBot) -> None:
    """Session pointing to deleted conversation auto-creates a new one."""
    # Set session to reference a nonexistent conversation
    bot.sessions.set_conversation_id("user-C", "nonexistent-convo-id-12345")

    conversation_id = await bot._resolve_conversation("user-C")

    # Should have auto-created a new conversation (not the stale ID)
    assert conversation_id != "nonexistent-convo-id-12345"

    # New conversation exists in DB
    convo = bot.container.storage.get_conversation(conversation_id)
    assert convo is not None, "Auto-recovered conversation should exist"

    # Session mapping updated
    assert bot.sessions.get_conversation_id("user-C") == conversation_id


# ---------------------------------------------------------------------------
# TD07: Event chain intact for Discord turns
# ---------------------------------------------------------------------------


async def test_td07_event_chain_intact(bot: DiscordBot) -> None:
    """Verify hash chain integrity on a Discord-originated conversation."""
    convo_id = _shared.get("user_a_convo_id")
    if convo_id is None:
        pytest.skip("TD01 did not run")

    verifier = VerificationService(bot.container.storage)
    result = verifier.verify_task_chain(convo_id)

    assert result.success is True, f"Hash chain verification failed: {result.error_message}"
    assert result.total_events > 0, "Should have events to verify"
    assert (
        result.verified_events == result.total_events
    ), f"Verified {result.verified_events}/{result.total_events} events"

    # Verify expected event types are present for a conversation with turns
    events = bot.container.storage.list_events(task_id=convo_id)
    event_types = {e.type for e in events}
    expected = {"llm.routed", "convo.turn_completed", "memory.retrieved"}
    missing = expected - event_types
    assert not missing, f"Missing event types: {missing}. Got: {event_types}"
