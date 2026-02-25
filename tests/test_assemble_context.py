"""Tests for context_builder service and assemble_context use case."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from openchronicle.core.application.services.context_builder import (
    build_turn_messages,
    format_memory_messages,
    format_time_context,
)
from openchronicle.core.application.use_cases import (
    assemble_context,
    create_conversation,
    external_turn,
)
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

_NOW = datetime(2026, 2, 24, 12, 0, 0, tzinfo=UTC)


def _make_memory(
    id: str = "mem-1",
    content: str = "test memory",
    tags: list[str] | None = None,
    pinned: bool = False,
    source: str = "test",
) -> MemoryItem:
    return MemoryItem(
        id=id,
        content=content,
        tags=tags or [],
        pinned=pinned,
        source=source,
        created_at=_NOW,
    )


def _make_turn(
    turn_index: int = 0,
    user_text: str = "hello",
    assistant_text: str = "hi",
) -> Turn:
    return Turn(
        conversation_id="convo-1",
        turn_index=turn_index,
        user_text=user_text,
        assistant_text=assistant_text,
        created_at=_NOW,
    )


# ── context_builder tests ────────────────────────────────────────


class TestFormatMemoryMessages:
    def test_pinned_and_relevant(self) -> None:
        pinned = [_make_memory(id="p1", content="pinned content", pinned=True, tags=["convention"])]
        relevant = [_make_memory(id="r1", content="relevant content", tags=["decision"])]
        result = format_memory_messages(pinned, relevant, include_pinned=True)
        assert result is not None
        assert "Pinned memory:" in result
        assert "p1" in result
        assert "convention" in result
        assert "Relevant memory:" in result
        assert "r1" in result

    def test_empty_returns_none(self) -> None:
        result = format_memory_messages([], [], include_pinned=True)
        assert result is None

    def test_content_truncated_at_300_chars(self) -> None:
        long_content = "x" * 400
        mem = _make_memory(content=long_content)
        result = format_memory_messages([], [mem], include_pinned=False)
        assert result is not None
        assert "..." in result
        # Should contain first 300 chars, not all 400
        assert "x" * 300 in result
        assert "x" * 301 not in result

    def test_no_pinned_when_excluded(self) -> None:
        pinned = [_make_memory(id="p1", pinned=True)]
        relevant = [_make_memory(id="r1")]
        result = format_memory_messages(pinned, relevant, include_pinned=False)
        assert result is not None
        assert "Pinned memory:" not in result
        assert "Relevant memory:" in result


class TestFormatTimeContext:
    def test_correct_delta(self) -> None:
        convo = Conversation(id="c1", created_at=_NOW)
        msg, ref_time, delta = format_time_context([], convo)
        assert ref_time == _NOW
        assert delta >= 0
        assert "Current time:" in msg
        assert "Last interaction:" in msg
        assert "Seconds since last interaction:" in msg

    def test_uses_last_turn_when_available(self) -> None:
        convo = Conversation(id="c1", created_at=datetime(2020, 1, 1, tzinfo=UTC))
        turn = _make_turn()
        msg, ref_time, delta = format_time_context([turn], convo)
        assert ref_time == turn.created_at
        assert ref_time != convo.created_at


class TestBuildTurnMessages:
    def test_includes_all_turns_and_prompt(self) -> None:
        turns = [_make_turn(turn_index=0), _make_turn(turn_index=1, user_text="q2", assistant_text="a2")]
        messages = build_turn_messages(turns, "new prompt")
        assert len(messages) == 5  # 2 turns * 2 msgs + 1 prompt
        assert messages[0] == {"role": "user", "content": "hello"}
        assert messages[1] == {"role": "assistant", "content": "hi"}
        assert messages[-1] == {"role": "user", "content": "new prompt"}

    def test_empty_turns_just_prompt(self) -> None:
        messages = build_turn_messages([], "new prompt")
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "new prompt"}


# ── assemble_context use case tests ──────────────────────────────


@pytest.fixture()
def store(tmp_path: Path) -> SqliteStore:
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    return storage


@pytest.fixture()
def event_logger(store: SqliteStore) -> EventLogger:
    return EventLogger(store)


@pytest.fixture()
def conversation_id(store: SqliteStore, event_logger: EventLogger) -> str:
    convo = create_conversation.execute(
        storage=store,
        convo_store=store,
        emit_event=event_logger.append,
        title="Test Convo",
    )
    return convo.id


def test_conversation_not_found(store: SqliteStore) -> None:
    with pytest.raises(NotFoundError, match="not found"):
        assemble_context.execute(
            convo_store=store,
            memory_store=store,
            conversation_id="nonexistent",
            prompt_text="hello",
        )


def test_empty_prompt(store: SqliteStore, conversation_id: str) -> None:
    with pytest.raises(DomainValidationError, match="prompt"):
        assemble_context.execute(
            convo_store=store,
            memory_store=store,
            conversation_id=conversation_id,
            prompt_text="",
        )


def test_happy_path(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    result = assemble_context.execute(
        convo_store=store,
        memory_store=store,
        conversation_id=conversation_id,
        prompt_text="What is 2+2?",
    )

    assert result.conversation_id == conversation_id
    assert result.conversation_title == "Test Convo"

    # Messages: system + time + prompt (no memory)
    assert len(result.messages) >= 3
    assert result.messages[0]["role"] == "system"
    assert "helpful assistant" in result.messages[0]["content"]
    assert result.messages[-1]["role"] == "user"
    assert result.messages[-1]["content"] == "What is 2+2?"

    assert result.prior_turn_count == 0
    assert result.last_interaction_at is not None
    assert result.seconds_since_last_interaction is not None


def test_with_prior_turns(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    external_turn.execute(
        convo_store=store,
        storage=store,
        emit_event=event_logger.append,
        conversation_id=conversation_id,
        user_text="first question",
        assistant_text="first answer",
    )

    result = assemble_context.execute(
        convo_store=store,
        memory_store=store,
        conversation_id=conversation_id,
        prompt_text="follow-up",
    )

    assert result.prior_turn_count == 1
    # Messages should include the prior turn
    texts = [m["content"] for m in result.messages]
    assert "first question" in texts
    assert "first answer" in texts
    assert "follow-up" in texts


def test_no_pinned_memory_requested(store: SqliteStore, conversation_id: str) -> None:
    result = assemble_context.execute(
        convo_store=store,
        memory_store=store,
        conversation_id=conversation_id,
        prompt_text="hello",
        include_pinned_memory=False,
    )

    # Should still work, just no pinned memories
    assert result.messages[0]["role"] == "system"
    assert result.conversation_id == conversation_id
