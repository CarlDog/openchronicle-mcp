from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import (
    ask_conversation,
    create_conversation,
    list_conversations,
    show_conversation,
)
from openchronicle.core.domain.models.conversation import Conversation
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


@pytest.mark.asyncio
async def test_conversation_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")
    monkeypatch.setenv("OC_LLM_FAST_POOL", "")
    monkeypatch.setenv("OC_LLM_QUALITY_POOL", "")

    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Test Conversation",
    )

    stored_conversation = storage.get_conversation(conversation.id)
    assert stored_conversation is not None
    assert stored_conversation.id == conversation.id
    assert stored_conversation.title == "Test Conversation"

    llm = StubLLMAdapter()
    interaction_router = RuleInteractionRouter()

    turn1 = await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        prompt_text="Hello",
        interaction_router=interaction_router,
        last_n=10,
    )

    turn2 = await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        prompt_text="How are you?",
        interaction_router=interaction_router,
        last_n=10,
    )

    assert turn1.turn_index == 1
    assert turn2.turn_index == 2

    assert turn1.provider == "stub"
    assert turn1.model == "stub-model"
    assert turn2.provider == "stub"
    assert turn2.model == "stub-model"

    _, turns = show_conversation.execute(convo_store=storage, conversation_id=conversation.id)
    assert [t.turn_index for t in turns] == [1, 2]
    assert turns[0].user_text == "Hello"
    assert turns[1].user_text == "How are you?"


def test_list_conversations_ordering(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()

    project = Project(name="conversation", metadata={"type": "conversation"})
    storage.add_project(project)

    convo_old = Conversation(
        id="convo-old",
        project_id=project.id,
        title="Old",
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    convo_new = Conversation(
        id="convo-new",
        project_id=project.id,
        title="New",
        created_at=datetime(2021, 1, 1, tzinfo=UTC),
    )
    convo_tie_a = Conversation(
        id="convo-aaa",
        project_id=project.id,
        title="Tie A",
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
    )
    convo_tie_b = Conversation(
        id="convo-zzz",
        project_id=project.id,
        title="Tie B",
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
    )

    storage.add_conversation(convo_old)
    storage.add_conversation(convo_new)
    storage.add_conversation(convo_tie_a)
    storage.add_conversation(convo_tie_b)

    ordered = storage.list_conversations()
    assert [c.id for c in ordered[:2]] == ["convo-zzz", "convo-aaa"]
    assert ordered[2].id == "convo-new"
    assert ordered[3].id == "convo-old"

    via_use_case = list_conversations.execute(convo_store=storage)
    assert [c.id for c in via_use_case] == [c.id for c in ordered]
