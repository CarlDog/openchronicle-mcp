from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.application.use_cases import add_memory, ask_conversation, create_conversation, pin_memory
from openchronicle.core.domain.models.conversation import Conversation
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMResponse
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.core.infrastructure.routing.rule_router import RuleInteractionRouter


class CaptureLLM(LLMPort):
    def __init__(self) -> None:
        self.last_messages: list[dict[str, Any]] = []

    async def complete_async(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        max_output_tokens: int | None = None,  # noqa: ARG002
        temperature: float | None = None,  # noqa: ARG002
        provider: str | None = None,
    ) -> LLMResponse:
        self.last_messages = messages
        return LLMResponse(content="ok", provider=provider or "stub", model=model)

    def complete(
        self,
        messages: list[dict[str, Any]],  # noqa: ARG002
        *,
        model: str,  # noqa: ARG002
        max_output_tokens: int | None = None,  # noqa: ARG002
        temperature: float | None = None,  # noqa: ARG002
        provider: str | None = None,  # noqa: ARG002
    ) -> LLMResponse:
        raise NotImplementedError


def test_memory_add_list_pin_search(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    project = Project(name="memory-project", metadata={})
    storage.add_project(project)

    item = MemoryItem(
        id="mem-1",
        content="alpha beta",
        tags=["alpha", "beta"],
        pinned=True,
        project_id=project.id,
    )

    add_memory.execute(store=storage, emit_event=event_logger.append, item=item)

    fetched = storage.get_memory(item.id)
    assert fetched is not None
    assert fetched.tags == ["alpha", "beta"]
    assert fetched.pinned is True

    pinned_old = MemoryItem(
        id="mem-pinned-old",
        content="old pinned",
        tags=[],
        pinned=True,
        project_id=project.id,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    pinned_new = MemoryItem(
        id="mem-pinned-new",
        content="new pinned",
        tags=[],
        pinned=True,
        project_id=project.id,
        created_at=datetime(2021, 1, 1, tzinfo=UTC),
    )
    storage.add_memory(pinned_old)
    storage.add_memory(pinned_new)

    pinned_only = storage.list_memory(pinned_only=True)
    pinned_ids = [m.id for m in pinned_only]
    assert pinned_ids.index("mem-pinned-new") < pinned_ids.index("mem-pinned-old")

    unpinned = MemoryItem(
        id="mem-unpinned",
        content="unpinned",
        tags=[],
        pinned=False,
        project_id=project.id,
    )
    storage.add_memory(unpinned)
    pin_memory.execute(store=storage, emit_event=event_logger.append, memory_id="mem-unpinned", pinned=True)
    updated = storage.get_memory("mem-unpinned")
    assert updated is not None
    assert updated.pinned is True

    storage.set_pinned("mem-1", False)
    storage.set_pinned("mem-pinned-old", False)
    storage.set_pinned("mem-pinned-new", False)
    storage.set_pinned("mem-unpinned", False)

    convo = Conversation(
        id="convo-search",
        project_id=project.id,
        title="Search",
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
    )
    storage.add_conversation(convo)

    pinned_ref = MemoryItem(
        id="mem-pin-ref",
        content="pinned reference",
        tags=["alpha"],
        pinned=True,
        project_id=project.id,
        conversation_id=convo.id,
    )
    match_high = MemoryItem(
        id="mem-match-high",
        content="alpha beta",
        tags=["alpha"],
        pinned=False,
        project_id=project.id,
        conversation_id=convo.id,
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
    )
    match_low = MemoryItem(
        id="mem-match-low",
        content="beta",
        tags=["beta"],
        pinned=False,
        project_id=project.id,
        conversation_id=convo.id,
        created_at=datetime(2022, 1, 1, tzinfo=UTC),
    )
    match_tie_a = MemoryItem(
        id="mem-tie-a",
        content="alpha",
        tags=["alpha"],
        pinned=False,
        project_id=project.id,
        conversation_id=convo.id,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
    )
    match_tie_b = MemoryItem(
        id="mem-tie-b",
        content="alpha",
        tags=["alpha"],
        pinned=False,
        project_id=project.id,
        conversation_id=convo.id,
        created_at=datetime(2023, 1, 1, tzinfo=UTC),
    )

    storage.add_memory(pinned_ref)
    storage.add_memory(match_high)
    storage.add_memory(match_low)
    storage.add_memory(match_tie_a)
    storage.add_memory(match_tie_b)

    results = storage.search_memory("alpha beta", top_k=5, conversation_id=convo.id, include_pinned=True)
    assert results[0].id == "mem-pin-ref"
    assert [m.id for m in results[1:5]] == [
        "mem-match-high",
        "mem-tie-b",
        "mem-tie-a",
        "mem-match-low",
    ]


@pytest.mark.asyncio
async def test_convo_ask_includes_memory(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)

    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Memory convo",
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

    llm = CaptureLLM()
    await ask_conversation.execute(
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

    system_messages = [m["content"] for m in llm.last_messages if m.get("role") == "system"]
    assert system_messages
    combined = "\n".join(system_messages)
    assert "mem-pinned" in combined
    assert "mem-relevant" in combined
