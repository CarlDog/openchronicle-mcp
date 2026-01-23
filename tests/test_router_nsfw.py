from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.application.use_cases import ask_conversation, convo_mode, create_conversation
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


def test_rule_router_scoring() -> None:
    router = RuleInteractionRouter(
        router_enabled=True,
        router_log_reasons=True,
        nsfw_route_if_score_gte=0.7,
        nsfw_uncertain_if_score_gte=0.45,
        persona_uncertain_routes_to_nsfw=True,
    )

    explicit_hint = router.analyze(user_text="roleplay explicit sex scene")
    assert explicit_hint.mode_hint == "persona"
    assert explicit_hint.nsfw_score >= 0.7
    assert explicit_hint.requires_nsfw_capable_model is True
    assert "nsfw_explicit_signal" in explicit_hint.reason_codes

    ambiguous_hint = router.analyze(user_text="roleplay cuddle and touch")
    assert ambiguous_hint.mode_hint == "persona"
    assert 0.45 <= ambiguous_hint.nsfw_score < 0.7
    assert ambiguous_hint.requires_nsfw_capable_model is True

    clean_hint = router.analyze(user_text="hello there")
    assert clean_hint.requires_nsfw_capable_model is False


@pytest.mark.asyncio
async def test_router_nsfw_pool_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    convo_mode.set_mode(storage, conversation.id, mode="persona")

    llm = StubLLMAdapter()
    await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        interaction_router=RuleInteractionRouter(),
        prompt_text="roleplay explicit sex scene",
        last_n=5,
    )

    events = storage.list_events(task_id=conversation.id)
    invoked = [e for e in events if e.type == "router.invoked"]
    applied = [e for e in events if e.type == "router.applied"]
    routed = [e for e in events if e.type == "llm.routed"]

    assert invoked
    assert applied
    assert routed

    routed_payload = routed[-1].payload
    assert routed_payload.get("provider") == "stub"
    assert routed_payload.get("model") == "stub-model"


@pytest.mark.asyncio
async def test_router_nsfw_pool_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")
    monkeypatch.setenv("OC_LLM_FAST_POOL", "")
    monkeypatch.setenv("OC_LLM_QUALITY_POOL", "")
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
            prompt_text="roleplay explicit sex scene",
            last_n=5,
        )

    assert exc.value.error_code == "NSFW_POOL_NOT_CONFIGURED"
