"""Tests for observability events — memory.search_completed, context.assembly_breakdown."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from openchronicle.core.domain.models.conversation import Conversation
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event

_NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


def _sample_conversation(**overrides: Any) -> Conversation:
    defaults: dict[str, Any] = {
        "id": "convo-1",
        "project_id": "proj-1",
        "title": "Test convo",
        "mode": "general",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return Conversation(**defaults)


def _sample_memory(**overrides: Any) -> MemoryItem:
    defaults: dict[str, Any] = {
        "id": "mem-1",
        "content": "User prefers Python",
        "tags": ["preference"],
        "pinned": False,
        "conversation_id": None,
        "project_id": "proj-1",
        "source": "manual",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return MemoryItem(**defaults)


def _mock_telemetry(*, perf: bool = True, memory: bool = True, self_report: bool = False) -> MagicMock:
    t = MagicMock()
    t.telemetry_enabled.return_value = True
    t.perf_enabled.return_value = perf
    t.memory_enabled.return_value = memory
    t.memory_self_report_enabled.return_value = self_report
    t.context_enabled.return_value = True
    t.usage_enabled.return_value = True
    return t


def _build_stores(memories: list[MemoryItem] | None = None) -> tuple[MagicMock, MagicMock]:
    """Build mock convo_store and memory_store for prepare_ask."""
    convo_store = MagicMock()
    convo_store.get_conversation.return_value = _sample_conversation()
    convo_store.list_turns.return_value = []

    memory_store = MagicMock()
    memory_store.list_memory.return_value = memories or []
    memory_store.search_memory.return_value = memories or [_sample_memory()]
    return convo_store, memory_store


def _mock_router() -> MagicMock:
    router = MagicMock()
    hint = MagicMock()
    hint.mode_hint = "general"
    hint.nsfw_score = 0.0
    hint.requires_nsfw_capable_model = False
    hint.reason_codes = []
    router.analyze.return_value = hint
    return router


def _mock_router_policy() -> MagicMock:
    policy = MagicMock()
    route = MagicMock()
    route.provider = "stub"
    route.model = "stub-model"
    route.mode = "fast"
    route.reasons = ["default"]
    route.predictor_hint = None
    route.predictor_source = None
    policy.route.return_value = route
    return policy


class TestMemorySearchCompletedEvent:
    @pytest.mark.asyncio
    async def test_emits_memory_search_completed(self) -> None:
        from openchronicle.core.application.use_cases.ask_conversation import prepare_ask

        convo_store, memory_store = _build_stores()
        events: list[Event] = []
        telemetry = _mock_telemetry(perf=True)

        await prepare_ask(
            convo_store=convo_store,
            memory_store=memory_store,
            emit_event=events.append,
            conversation_id="convo-1",
            prompt_text="test prompt",
            interaction_router=_mock_router(),
            router_policy=_mock_router_policy(),
            telemetry=telemetry,
        )

        search_events = [e for e in events if e.type == "memory.search_completed"]
        assert len(search_events) == 1
        payload = search_events[0].payload
        assert "latency_ms" in payload
        assert "result_count" in payload
        assert payload["result_count"] == 1  # from _build_stores default

    @pytest.mark.asyncio
    async def test_search_completed_latency_is_numeric(self) -> None:
        from openchronicle.core.application.use_cases.ask_conversation import prepare_ask

        convo_store, memory_store = _build_stores()
        events: list[Event] = []
        telemetry = _mock_telemetry(perf=True)

        await prepare_ask(
            convo_store=convo_store,
            memory_store=memory_store,
            emit_event=events.append,
            conversation_id="convo-1",
            prompt_text="test prompt",
            interaction_router=_mock_router(),
            router_policy=_mock_router_policy(),
            telemetry=telemetry,
        )

        search_events = [e for e in events if e.type == "memory.search_completed"]
        assert isinstance(search_events[0].payload["latency_ms"], float)


class TestContextAssemblyBreakdown:
    @pytest.mark.asyncio
    async def test_emits_assembly_breakdown(self) -> None:
        from openchronicle.core.application.use_cases.ask_conversation import prepare_ask

        convo_store, memory_store = _build_stores()
        events: list[Event] = []
        telemetry = _mock_telemetry(perf=True)

        await prepare_ask(
            convo_store=convo_store,
            memory_store=memory_store,
            emit_event=events.append,
            conversation_id="convo-1",
            prompt_text="test prompt",
            interaction_router=_mock_router(),
            router_policy=_mock_router_policy(),
            telemetry=telemetry,
        )

        breakdown_events = [e for e in events if e.type == "context.assembly_breakdown"]
        assert len(breakdown_events) == 1
        payload = breakdown_events[0].payload
        assert "memory_retrieval_ms" in payload
        assert "context_build_ms" in payload
        assert "total_ms" in payload

    @pytest.mark.asyncio
    async def test_no_breakdown_without_telemetry(self) -> None:
        from openchronicle.core.application.use_cases.ask_conversation import prepare_ask

        convo_store, memory_store = _build_stores()
        events: list[Event] = []

        await prepare_ask(
            convo_store=convo_store,
            memory_store=memory_store,
            emit_event=events.append,
            conversation_id="convo-1",
            prompt_text="test prompt",
            interaction_router=_mock_router(),
            router_policy=_mock_router_policy(),
            telemetry=None,
        )

        breakdown_events = [e for e in events if e.type == "context.assembly_breakdown"]
        assert len(breakdown_events) == 0

    @pytest.mark.asyncio
    async def test_no_breakdown_when_perf_disabled(self) -> None:
        from openchronicle.core.application.use_cases.ask_conversation import prepare_ask

        convo_store, memory_store = _build_stores()
        events: list[Event] = []
        telemetry = _mock_telemetry(perf=False)

        await prepare_ask(
            convo_store=convo_store,
            memory_store=memory_store,
            emit_event=events.append,
            conversation_id="convo-1",
            prompt_text="test prompt",
            interaction_router=_mock_router(),
            router_policy=_mock_router_policy(),
            telemetry=telemetry,
        )

        breakdown_events = [e for e in events if e.type == "context.assembly_breakdown"]
        assert len(breakdown_events) == 0
