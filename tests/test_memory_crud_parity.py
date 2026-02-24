"""Tests for memory CRUD parity — delete_memory use case, memory_get, memory_stats."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from openchronicle.core.application.use_cases import delete_memory
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event

_NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


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


# ── delete_memory use case ───────────────────────────────────────


class TestDeleteMemoryUseCase:
    def test_emits_memory_deleted_event(self) -> None:
        store = MagicMock()
        store.get_memory.return_value = _sample_memory()
        store.delete_memory.return_value = True
        events: list[Event] = []

        delete_memory.execute(store=store, emit_event=events.append, memory_id="mem-1")

        store.delete_memory.assert_called_once_with("mem-1")
        assert len(events) == 1
        assert events[0].type == "memory.deleted"
        assert events[0].payload["memory_id"] == "mem-1"
        assert events[0].project_id == "proj-1"

    def test_raises_value_error_for_nonexistent(self) -> None:
        store = MagicMock()
        store.get_memory.return_value = None

        with pytest.raises(NotFoundError, match="Memory not found"):
            delete_memory.execute(store=store, emit_event=MagicMock(), memory_id="no-such-id")

        store.delete_memory.assert_not_called()

    def test_captures_project_id_before_delete(self) -> None:
        """project_id is captured from memory before deletion."""
        store = MagicMock()
        store.get_memory.return_value = _sample_memory(project_id="proj-42")
        store.delete_memory.return_value = True
        events: list[Event] = []

        delete_memory.execute(store=store, emit_event=events.append, memory_id="mem-1")

        assert events[0].project_id == "proj-42"

    def test_handles_none_project_id(self) -> None:
        store = MagicMock()
        store.get_memory.return_value = _sample_memory(project_id=None)
        store.delete_memory.return_value = True
        events: list[Event] = []

        delete_memory.execute(store=store, emit_event=events.append, memory_id="mem-1")

        assert events[0].project_id == ""


# ── MCP memory_get ───────────────────────────────────────────────


class TestMCPMemoryGet:
    def test_returns_memory_dict(self) -> None:
        mcp_mod = pytest.importorskip("mcp")  # noqa: F841
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        container.storage.get_memory.return_value = _sample_memory()
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        mcp = FastMCP("test")
        register(mcp)
        tool_fn = mcp._tool_manager._tools["memory_get"].fn
        result = tool_fn(memory_id="mem-1", ctx=ctx)

        assert result["id"] == "mem-1"
        assert result["content"] == "User prefers Python"

    def test_raises_for_nonexistent(self) -> None:
        mcp_mod = pytest.importorskip("mcp")  # noqa: F841
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        container.storage.get_memory.return_value = None
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        mcp = FastMCP("test")
        register(mcp)
        tool_fn = mcp._tool_manager._tools["memory_get"].fn

        with pytest.raises(NotFoundError, match="Memory not found"):
            tool_fn(memory_id="no-such", ctx=ctx)


# ── MCP memory_delete ────────────────────────────────────────────


class TestMCPMemoryDelete:
    def test_deletes_and_returns_ok(self) -> None:
        mcp_mod = pytest.importorskip("mcp")  # noqa: F841
        from unittest.mock import patch

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        mcp = FastMCP("test")
        register(mcp)

        with patch("openchronicle.interfaces.mcp.tools.memory.delete_memory.execute"):
            tool_fn = mcp._tool_manager._tools["memory_delete"].fn
            result = tool_fn(memory_id="mem-1", ctx=ctx)

        assert result["status"] == "ok"
        assert result["memory_id"] == "mem-1"


# ── MCP memory_stats ─────────────────────────────────────────────


class TestMCPMemoryStats:
    def test_returns_correct_counts(self) -> None:
        mcp_mod = pytest.importorskip("mcp")  # noqa: F841
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        container.storage.list_memory.return_value = [
            _sample_memory(id="m1", pinned=True, tags=["decision"], source="mcp"),
            _sample_memory(id="m2", pinned=False, tags=["decision", "context"], source="api"),
            _sample_memory(id="m3", pinned=False, tags=["context"], source="mcp"),
        ]
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        mcp = FastMCP("test")
        register(mcp)
        tool_fn = mcp._tool_manager._tools["memory_stats"].fn
        result = tool_fn(ctx=ctx)

        assert result["total"] == 3
        assert result["pinned"] == 1
        assert result["by_tag"]["decision"] == 2
        assert result["by_tag"]["context"] == 2
        assert result["by_source"]["mcp"] == 2
        assert result["by_source"]["api"] == 1

    def test_filters_by_project_id(self) -> None:
        mcp_mod = pytest.importorskip("mcp")  # noqa: F841
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        container.storage.list_memory.return_value = [
            _sample_memory(id="m1", project_id="proj-1"),
            _sample_memory(id="m2", project_id="proj-2"),
        ]
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        mcp = FastMCP("test")
        register(mcp)
        tool_fn = mcp._tool_manager._tools["memory_stats"].fn
        result = tool_fn(ctx=ctx, project_id="proj-1")

        assert result["total"] == 1
