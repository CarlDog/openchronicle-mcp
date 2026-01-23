from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from openchronicle.core.application.use_cases import ask_conversation, create_conversation, export_convo, remember_turn
from openchronicle.core.domain.models.project import Event
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


@pytest.mark.asyncio
async def test_export_convo_includes_memory_written_ids_and_explain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        title="Export",
    )

    llm = StubLLMAdapter()
    turn = await ask_conversation.execute(
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

    remembered = remember_turn.execute(
        storage=storage,
        convo_store=storage,
        memory_store=storage,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        turn_index=turn.turn_index,
        which="assistant",
        tags=["export"],
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

    export_basic = export_convo.execute(
        storage=storage,
        convo_store=storage,
        conversation_id=conversation.id,
        include_explain=False,
        include_verify=False,
    )
    export_basic_again = export_convo.execute(
        storage=storage,
        convo_store=storage,
        conversation_id=conversation.id,
        include_explain=False,
        include_verify=False,
    )

    assert export_basic == export_basic_again
    assert export_basic["format_version"] == "1"
    assert set(export_basic.keys()) == {"format_version", "conversation", "turns"}
    conversation_dict = cast(dict[str, object], export_basic["conversation"])
    assert conversation_dict["mode"] == "general"
    turns_basic = cast(list[dict[str, object]], export_basic["turns"])
    assert len(turns_basic) == 1
    assert "explain" not in turns_basic[0]
    assert remembered.id in cast(list[str], turns_basic[0]["memory_written_ids"])

    export_with_explain = export_convo.execute(
        storage=storage,
        convo_store=storage,
        conversation_id=conversation.id,
        include_explain=True,
        include_verify=True,
    )
    export_with_explain_again = export_convo.execute(
        storage=storage,
        convo_store=storage,
        conversation_id=conversation.id,
        include_explain=True,
        include_verify=True,
    )

    assert export_with_explain == export_with_explain_again
    assert export_with_explain["format_version"] == "1"
    verification = cast(dict[str, object], export_with_explain["verification"])
    assert set(verification.keys()) == {"ok", "failure_event_id", "expected_hash", "actual_hash"}
    assert verification["ok"] is True
    turns_explain = cast(list[dict[str, object]], export_with_explain["turns"])
    assert len(turns_explain) == 1
    explain = cast(dict[str, object], turns_explain[0]["explain"])
    assert explain["turn_id"] == turns_explain[0]["id"]
    assert remembered.id in cast(list[str], explain["memory_written_ids"])
