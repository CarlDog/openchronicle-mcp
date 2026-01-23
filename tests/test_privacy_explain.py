from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from openchronicle.core.application.use_cases import ask_conversation, create_conversation, explain_turn
from openchronicle.core.infrastructure.config.settings import PrivacyOutboundSettings
from openchronicle.core.infrastructure.llm.stub_adapter import StubLLMAdapter
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.privacy.rule_privacy import RulePrivacyGate
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


@pytest.mark.asyncio
async def test_privacy_explain_warn(tmp_path: Path) -> None:
    storage = SqliteStore(str(tmp_path / "privacy_explain.db"))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Privacy Explain",
    )

    llm = StubLLMAdapter()
    settings = PrivacyOutboundSettings(
        mode="warn",
        external_only=False,
        categories=["email"],
        redact_style="mask",
        log_events=True,
    )

    turn = await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        interaction_router=RuleInteractionRouter(),
        prompt_text="contact me at user@example.com",
        privacy_gate=RulePrivacyGate(),
        privacy_settings=settings,
    )

    explain = explain_turn.execute(storage=storage, conversation_id=conversation.id, turn_id=turn.id)
    privacy = cast(dict[str, Any], explain["privacy"])
    assert privacy["checked"] is True
    assert privacy["effective_mode"] == "warn"
    assert privacy["override_allow_pii"] is False
    assert privacy["categories"] == ["email"]
    counts = cast(dict[str, int], privacy["counts"])
    assert counts["email"] == 1


@pytest.mark.asyncio
async def test_privacy_explain_override(tmp_path: Path) -> None:
    storage = SqliteStore(str(tmp_path / "privacy_override.db"))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Privacy Override",
    )

    llm = StubLLMAdapter()
    settings = PrivacyOutboundSettings(
        mode="block",
        external_only=False,
        categories=["email"],
        redact_style="mask",
        log_events=True,
    )

    turn = await ask_conversation.execute(
        convo_store=storage,
        storage=storage,
        memory_store=storage,
        llm=llm,
        emit_event=event_logger.append,
        conversation_id=conversation.id,
        interaction_router=RuleInteractionRouter(),
        prompt_text="contact me at user@example.com",
        allow_pii=True,
        privacy_gate=RulePrivacyGate(),
        privacy_settings=settings,
    )

    explain = explain_turn.execute(storage=storage, conversation_id=conversation.id, turn_id=turn.id)
    privacy = cast(dict[str, Any], explain["privacy"])
    assert privacy["override_allow_pii"] is True
    assert privacy["checked"] is False
    assert privacy["applies"] is False
