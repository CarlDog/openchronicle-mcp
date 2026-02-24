from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import (
    convo_mode,
    create_conversation,
)
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def test_conversation_mode_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Modes",
    )

    assert convo_mode.get_mode(storage, conversation.id) == "general"
    stored = storage.get_conversation(conversation.id)
    assert stored is not None
    assert stored.mode == "general"

    updated = convo_mode.set_mode(storage, conversation.id, mode="persona")
    assert updated == "persona"
    assert convo_mode.get_mode(storage, conversation.id) == "persona"
    stored_after = storage.get_conversation(conversation.id)
    assert stored_after is not None
    assert stored_after.mode == "persona"


def test_conversation_mode_rejects_invalid(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Modes",
    )

    with pytest.raises(DomainValidationError, match="Invalid conversation mode"):
        convo_mode.set_mode(storage, conversation.id, mode="invalid")
