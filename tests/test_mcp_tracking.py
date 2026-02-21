"""Tests for MCP tool usage tracking — decorator + storage + tool_stats."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

mcp_mod = pytest.importorskip("mcp")  # noqa: F841

from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore  # noqa: E402
from openchronicle.interfaces.mcp.tracking import track_tool  # noqa: E402

# ── Helpers ───────────────────────────────────────────────────────


def _make_container(storage: Any = None, *, tracking_enabled: bool = True) -> MagicMock:
    container = MagicMock()
    container.storage = storage or MagicMock()
    ts = MagicMock()
    ts.enabled = True
    ts.mcp_tracking_enabled = tracking_enabled
    container.telemetry_settings = ts
    return container


def _make_ctx(container: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"container": container}
    return ctx


# ── Decorator: sync ──────────────────────────────────────────────


class TestTrackToolSync:
    def test_records_success(self) -> None:
        container = _make_container()
        ctx = _make_ctx(container)

        @track_tool
        def my_tool(ctx: Any) -> str:
            return "ok"

        result = my_tool(ctx=ctx)
        assert result == "ok"
        container.storage.insert_mcp_tool_usage.assert_called_once()
        call_kwargs = container.storage.insert_mcp_tool_usage.call_args[1]
        assert call_kwargs["tool_name"] == "my_tool"
        assert call_kwargs["success"] is True
        assert call_kwargs["latency_ms"] >= 0
        assert call_kwargs["error_type"] is None

    def test_records_failure(self) -> None:
        container = _make_container()
        ctx = _make_ctx(container)

        @track_tool
        def failing_tool(ctx: Any) -> str:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            failing_tool(ctx=ctx)

        call_kwargs = container.storage.insert_mcp_tool_usage.call_args[1]
        assert call_kwargs["success"] is False
        assert call_kwargs["error_type"] == "ValueError"
        assert "boom" in (call_kwargs["error_message"] or "")

    def test_preserves_return_value(self) -> None:
        container = _make_container()
        ctx = _make_ctx(container)

        @track_tool
        def data_tool(ctx: Any) -> list[int]:
            return [1, 2, 3]

        assert data_tool(ctx=ctx) == [1, 2, 3]

    def test_no_ctx_is_noop(self) -> None:
        @track_tool
        def no_ctx_tool() -> str:
            return "fine"

        assert no_ctx_tool() == "fine"
        # No crash, no persistence attempt

    def test_tracking_disabled_skips_persist(self) -> None:
        container = _make_container(tracking_enabled=False)
        ctx = _make_ctx(container)

        @track_tool
        def some_tool(ctx: Any) -> str:
            return "ok"

        some_tool(ctx=ctx)
        container.storage.insert_mcp_tool_usage.assert_not_called()

    def test_persistence_failure_swallowed(self) -> None:
        container = _make_container()
        container.storage.insert_mcp_tool_usage.side_effect = RuntimeError("db gone")
        ctx = _make_ctx(container)

        @track_tool
        def safe_tool(ctx: Any) -> str:
            return "still works"

        assert safe_tool(ctx=ctx) == "still works"


# ── Decorator: async ─────────────────────────────────────────────


class TestTrackToolAsync:
    @pytest.mark.asyncio
    async def test_records_success(self) -> None:
        container = _make_container()
        ctx = _make_ctx(container)

        @track_tool
        async def async_tool(ctx: Any) -> str:
            return "async ok"

        result = await async_tool(ctx=ctx)
        assert result == "async ok"
        call_kwargs = container.storage.insert_mcp_tool_usage.call_args[1]
        assert call_kwargs["tool_name"] == "async_tool"
        assert call_kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_records_failure(self) -> None:
        container = _make_container()
        ctx = _make_ctx(container)

        @track_tool
        async def async_fail(ctx: Any) -> str:
            raise TypeError("async boom")

        with pytest.raises(TypeError, match="async boom"):
            await async_fail(ctx=ctx)

        call_kwargs = container.storage.insert_mcp_tool_usage.call_args[1]
        assert call_kwargs["success"] is False
        assert call_kwargs["error_type"] == "TypeError"


# ── Storage: SQLite roundtrip ────────────────────────────────────


class TestStorageMCPToolUsage:
    def _store(self, tmp_path: Any) -> SqliteStore:
        store = SqliteStore(str(tmp_path / "test.db"))
        store.init_schema()
        return store

    def test_insert_and_query(self, tmp_path: Any) -> None:
        store = self._store(tmp_path)
        now = datetime.now(UTC).isoformat()
        store.insert_mcp_tool_usage(
            id=uuid.uuid4().hex,
            tool_name="memory_search",
            started_at=now,
            latency_ms=42,
            success=True,
            error_type=None,
            error_message=None,
            created_at=now,
        )
        stats = store.get_mcp_tool_stats()
        assert len(stats) == 1
        assert stats[0]["tool_name"] == "memory_search"
        assert stats[0]["call_count"] == 1
        assert stats[0]["avg_latency_ms"] == 42
        assert stats[0]["error_count"] == 0

    def test_groups_by_tool_name(self, tmp_path: Any) -> None:
        store = self._store(tmp_path)
        now = datetime.now(UTC).isoformat()
        for tool in ["memory_search", "memory_search", "health"]:
            store.insert_mcp_tool_usage(
                id=uuid.uuid4().hex,
                tool_name=tool,
                started_at=now,
                latency_ms=10,
                success=True,
                error_type=None,
                error_message=None,
                created_at=now,
            )
        stats = store.get_mcp_tool_stats()
        assert len(stats) == 2
        by_name = {s["tool_name"]: s for s in stats}
        assert by_name["memory_search"]["call_count"] == 2
        assert by_name["health"]["call_count"] == 1

    def test_filter_by_tool_name(self, tmp_path: Any) -> None:
        store = self._store(tmp_path)
        now = datetime.now(UTC).isoformat()
        for tool in ["memory_search", "health"]:
            store.insert_mcp_tool_usage(
                id=uuid.uuid4().hex,
                tool_name=tool,
                started_at=now,
                latency_ms=10,
                success=True,
                error_type=None,
                error_message=None,
                created_at=now,
            )
        stats = store.get_mcp_tool_stats(tool_name="health")
        assert len(stats) == 1
        assert stats[0]["tool_name"] == "health"

    def test_filter_by_since(self, tmp_path: Any) -> None:
        store = self._store(tmp_path)
        old = "2020-01-01T00:00:00+00:00"
        recent = "2026-01-01T00:00:00+00:00"
        store.insert_mcp_tool_usage(
            id=uuid.uuid4().hex,
            tool_name="old_call",
            started_at=old,
            latency_ms=10,
            success=True,
            error_type=None,
            error_message=None,
            created_at=old,
        )
        store.insert_mcp_tool_usage(
            id=uuid.uuid4().hex,
            tool_name="new_call",
            started_at=recent,
            latency_ms=20,
            success=True,
            error_type=None,
            error_message=None,
            created_at=recent,
        )
        stats = store.get_mcp_tool_stats(since="2025-01-01T00:00:00+00:00")
        assert len(stats) == 1
        assert stats[0]["tool_name"] == "new_call"

    def test_empty_table(self, tmp_path: Any) -> None:
        store = self._store(tmp_path)
        assert store.get_mcp_tool_stats() == []


# ── Integration: tool_stats tool ─────────────────────────────────


class TestToolStatsTool:
    def test_returns_data(self, tmp_path: Any) -> None:
        store = SqliteStore(str(tmp_path / "test.db"))
        store.init_schema()
        now = datetime.now(UTC).isoformat()
        store.insert_mcp_tool_usage(
            id=uuid.uuid4().hex,
            tool_name="memory_save",
            started_at=now,
            latency_ms=15,
            success=True,
            error_type=None,
            error_message=None,
            created_at=now,
        )

        container = _make_container(storage=store)
        ctx = _make_ctx(container)

        from openchronicle.interfaces.mcp.tools.system import register

        mcp_server = MagicMock()
        registered: dict[str, Any] = {}
        mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
        register(mcp_server)

        result = registered["tool_stats"](ctx=ctx)
        assert len(result) == 1
        assert result[0]["tool_name"] == "memory_save"
        assert result[0]["call_count"] == 1
