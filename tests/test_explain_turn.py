from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from openchronicle.core.application.use_cases import (
    add_memory,
    ask_conversation,
    create_conversation,
    explain_turn,
    remember_turn,
)
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


@pytest.mark.asyncio
async def test_explain_turn_extracts_events(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        title="Explain",
    )

    pinned_item = MemoryItem(
        id="mem-pinned",
        content="Pinned note",
        tags=["pin"],
        pinned=True,
        conversation_id=conversation.id,
        project_id=conversation.project_id,
    )
    relevant_item = MemoryItem(
        id="mem-relevant",
        content="The keyword is lighthouse.",
        tags=["keyword"],
        pinned=False,
        conversation_id=conversation.id,
        project_id=conversation.project_id,
    )

    add_memory.execute(store=storage, emit_event=event_logger.append, item=pinned_item)
    add_memory.execute(store=storage, emit_event=event_logger.append, item=relevant_item)

    llm = StubLLMAdapter()
    turn = await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        interaction_router=RuleInteractionRouter(),
        prompt_text="Tell me about the lighthouse",
        last_n=5,
        top_k_memory=5,
        include_pinned_memory=True,
    )

    remembered = remember_turn.execute(
        storage=storage,
        convo_store=storage,
        memory_store=storage,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        turn_index=turn.turn_index,
        which="assistant",
        tags=["explain"],
        pinned=False,
        source="turn",
    )

    event_logger.append(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="convo.turn_completed",
            payload={
                "turn_id": turn.id,
                "turn_index": turn.turn_index,
                "provider": turn.provider,
                "model": turn.model,
            },
        )
    )

    explain = explain_turn.execute(storage=storage, conversation_id=conversation.id, turn_id=turn.id)
    explain_again = explain_turn.execute(storage=storage, conversation_id=conversation.id, turn_id=turn.id)

    assert explain == explain_again
    assert explain["turn_id"] == turn.id
    assert explain["provider"] is not None
    assert explain["model"] is not None
    memory = cast(dict[str, object], explain["memory"])
    llm_info = cast(dict[str, object], explain["llm"])
    assert "mem-pinned" in cast(list[str], memory["pinned_ids"])
    assert "mem-relevant" in cast(list[str], memory["relevant_ids"])
    assert remembered.id in cast(list[str], explain["memory_written_ids"])

    usage = cast(dict[str, object], llm_info["usage"])
    assert set(usage.keys()) == {"input_tokens", "output_tokens", "total_tokens"}
