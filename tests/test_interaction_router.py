from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import ask_conversation, convo_mode, create_conversation
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


def test_interaction_router_reason_codes_privacy() -> None:
    router = RuleInteractionRouter(router_log_reasons=False)
    hint = router.analyze(user_text="roleplay explicit scene")
    assert hint.reason_codes == []

    verbose_router = RuleInteractionRouter(router_log_reasons=True)
    verbose_hint = verbose_router.analyze(user_text="roleplay explicit scene")
    assert set(verbose_hint.reason_codes).issubset(
        {"mode_persona_marker", "mode_story_marker", "nsfw_explicit_signal", "nsfw_ambiguous_signal"}
    )


@pytest.mark.asyncio
async def test_interaction_router_events_are_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")
    monkeypatch.setenv("OC_LLM_FAST_POOL", "")
    monkeypatch.setenv("OC_LLM_QUALITY_POOL", "")
    monkeypatch.setenv("OC_LLM_POOL_NSFW", "stub:stub-model")

    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Router",
    )

    llm = StubLLMAdapter()
    await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        interaction_router=RuleInteractionRouter(router_log_reasons=False),
        prompt_text="roleplay explicit scene",
        last_n=5,
    )

    events = storage.list_events(task_id=conversation.id)
    invoked = [e for e in events if e.type == "router.invoked"]
    applied = [e for e in events if e.type == "router.applied"]

    assert invoked
    assert applied

    invoked_payload = invoked[-1].payload
    assert "prompt_text" not in invoked_payload
    assert invoked_payload.get("reason_codes") == []


@pytest.mark.asyncio
async def test_interaction_router_missing_nsfw_pool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")
    monkeypatch.setenv("OC_LLM_FAST_POOL", "")
    monkeypatch.setenv("OC_LLM_QUALITY_POOL", "")
    monkeypatch.setenv("OC_CONFIG_DIR", "config")
    monkeypatch.delenv("OC_LLM_POOL_NSFW", raising=False)

    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Router",
    )
    convo_mode.set_mode(storage, conversation.id, mode="persona")

    llm = StubLLMAdapter()
    with pytest.raises(LLMProviderError) as exc:
        await ask_conversation.execute(
            convo_store=storage,
            storage=storage,
            memory_store=storage,
            llm=llm,
            emit_event=event_logger.append,
            conversation_id=conversation.id,
            interaction_router=RuleInteractionRouter(),
            prompt_text="roleplay explicit scene",
            last_n=5,
        )

    assert exc.value.error_code == "NSFW_POOL_NOT_CONFIGURED"
    assert "OC_CONFIG_DIR=config" in (exc.value.hint or "")
