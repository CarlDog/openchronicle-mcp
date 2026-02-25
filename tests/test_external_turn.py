"""Tests for the external_turn use case."""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import (
    create_conversation,
    external_turn,
)
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


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
        title="Test Conversation",
    )
    return convo.id


def test_conversation_not_found(store: SqliteStore, event_logger: EventLogger) -> None:
    with pytest.raises(NotFoundError, match="not found"):
        external_turn.execute(
            convo_store=store,
            storage=store,
            emit_event=event_logger.append,
            conversation_id="nonexistent",
            user_text="hello",
            assistant_text="hi",
        )


def test_empty_user_text(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    with pytest.raises(DomainValidationError, match="user_text"):
        external_turn.execute(
            convo_store=store,
            storage=store,
            emit_event=event_logger.append,
            conversation_id=conversation_id,
            user_text="",
            assistant_text="hi",
        )


def test_whitespace_user_text(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    with pytest.raises(DomainValidationError, match="user_text"):
        external_turn.execute(
            convo_store=store,
            storage=store,
            emit_event=event_logger.append,
            conversation_id=conversation_id,
            user_text="   ",
            assistant_text="hi",
        )


def test_empty_assistant_text(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    with pytest.raises(DomainValidationError, match="assistant_text"):
        external_turn.execute(
            convo_store=store,
            storage=store,
            emit_event=event_logger.append,
            conversation_id=conversation_id,
            user_text="hello",
            assistant_text="",
        )


def test_happy_path(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    turn = external_turn.execute(
        convo_store=store,
        storage=store,
        emit_event=event_logger.append,
        conversation_id=conversation_id,
        user_text="What is 2+2?",
        assistant_text="4",
    )

    assert turn.conversation_id == conversation_id
    assert turn.turn_index == 1
    assert turn.user_text == "What is 2+2?"
    assert turn.assistant_text == "4"
    assert turn.provider == "external"
    assert turn.model == ""
    assert turn.routing_reasons == ["external"]


def test_custom_provider_and_model(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    turn = external_turn.execute(
        convo_store=store,
        storage=store,
        emit_event=event_logger.append,
        conversation_id=conversation_id,
        user_text="hello",
        assistant_text="hi",
        provider="claude-code",
        model="claude-opus-4-6",
    )

    assert turn.provider == "claude-code"
    assert turn.model == "claude-opus-4-6"


def test_event_emitted(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    external_turn.execute(
        convo_store=store,
        storage=store,
        emit_event=event_logger.append,
        conversation_id=conversation_id,
        user_text="hello",
        assistant_text="hi",
    )

    events = store.list_events(task_id=conversation_id)
    turn_recorded = [e for e in events if e.type == "convo.turn_recorded"]
    assert len(turn_recorded) == 1
    assert turn_recorded[0].payload["provider"] == "external"


def test_sequential_turn_index(store: SqliteStore, event_logger: EventLogger, conversation_id: str) -> None:
    turn1 = external_turn.execute(
        convo_store=store,
        storage=store,
        emit_event=event_logger.append,
        conversation_id=conversation_id,
        user_text="first",
        assistant_text="response 1",
    )
    turn2 = external_turn.execute(
        convo_store=store,
        storage=store,
        emit_event=event_logger.append,
        conversation_id=conversation_id,
        user_text="second",
        assistant_text="response 2",
    )

    assert turn1.turn_index == 1
    assert turn2.turn_index == 2
