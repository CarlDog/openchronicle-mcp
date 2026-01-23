from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import ask_conversation, create_conversation, remember_turn
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


@pytest.mark.asyncio
async def test_remember_turn_links_memory_and_emits_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        title="Remember",
    )

    llm = StubLLMAdapter()
    await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        interaction_router=RuleInteractionRouter(),
        prompt_text="Hello",
        last_n=5,
    )

    item = remember_turn.execute(
        storage=storage,
        convo_store=storage,
        memory_store=storage,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        turn_index=1,
        which="assistant",
        tags=["summary"],
        pinned=True,
        source="turn",
    )

    stored_item = storage.get_memory(item.id)
    assert stored_item is not None

    turn = storage.get_turn_by_index(conversation.id, 1)
    assert turn is not None
    assert item.id in turn.memory_written_ids

    storage.link_memory_to_turn(turn.id, item.id)
    turn_again = storage.get_turn_by_index(conversation.id, 1)
    assert turn_again is not None
    assert turn_again.memory_written_ids.count(item.id) == 1

    events = storage.list_events(task_id=conversation.id)
    linked_events = [e for e in events if e.type == "convo.turn_memory_linked"]
    assert linked_events
    payload = linked_events[-1].payload
    assert payload.get("turn_id") == turn.id
    assert payload.get("turn_index") == turn.turn_index
    assert payload.get("memory_id") == item.id
    assert payload.get("which") == "assistant"
