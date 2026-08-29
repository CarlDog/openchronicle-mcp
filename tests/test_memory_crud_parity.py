"""Tests for memory CRUD parity — delete_memory use case, memory_get, memory_stats."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from openchronicle.core.application.use_cases import delete_memory, stats_memory
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore

_NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


def _sample_memory(**overrides: Any) -> MemoryItem:
    defaults: dict[str, Any] = {
        "id": "mem-1",
        "content": "User prefers Python",
        "tags": ["preference"],
        "pinned": False,
        "project_id": "proj-1",
        "source": "manual",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return MemoryItem(**defaults)


# ── delete_memory use case ───────────────────────────────────────


class TestDeleteMemoryUseCase:
    def test_preview_returns_metadata_without_deleting(self) -> None:
        store = MagicMock()
        store.get_memory.return_value = _sample_memory()

        result = delete_memory.execute(store=store, memory_id="mem-1", confirm=False)

        assert result["status"] == "preview"
        assert result["memory_id"] == "mem-1"
        assert result["content"] == "User prefers Python"
        assert result["tags"] == ["preference"]
        assert result["pinned"] is False
        store.delete_memory.assert_not_called()

    def test_preview_raises_not_found_for_missing(self) -> None:
        store = MagicMock()
        store.get_memory.return_value = None

        with pytest.raises(NotFoundError, match="Memory not found"):
            delete_memory.execute(store=store, memory_id="no-such-id", confirm=False)

        store.delete_memory.assert_not_called()

    def test_confirm_deletes(self) -> None:
        store = MagicMock()

        result = delete_memory.execute(store=store, memory_id="mem-1", confirm=True)

        assert result["status"] == "ok"
        assert result["memory_id"] == "mem-1"
        store.delete_memory.assert_called_once_with("mem-1")
        # The optimized confirm path skips the extra get to preserve the
        # pre-refactor atomic-delete posture.
        store.get_memory.assert_not_called()

    def test_confirm_propagates_not_found_from_store(self) -> None:
        store = MagicMock()
        store.delete_memory.side_effect = NotFoundError("Memory not found: no-such-id", code="MEMORY_NOT_FOUND")

        with pytest.raises(NotFoundError, match="Memory not found"):
            delete_memory.execute(store=store, memory_id="no-such-id", confirm=True)

        store.delete_memory.assert_called_once_with("no-such-id")


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
        result = asyncio.run(tool_fn(memory_id="mem-1", ctx=ctx))

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
            asyncio.run(tool_fn(memory_id="no-such", ctx=ctx))


# ── MCP memory_delete ────────────────────────────────────────────


class TestMCPMemoryDelete:
    def _build_tool(self) -> tuple[MagicMock, MagicMock, Any]:
        pytest.importorskip("mcp")
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}
        mcp = FastMCP("test")
        register(mcp)
        return container, ctx, mcp._tool_manager._tools["memory_delete"].fn

    def test_omitting_confirm_is_an_error_not_a_preview(self) -> None:
        """A client that predates `confirm` must fail loudly.

        This is the regression guard for the mnemosyne-mcp bug: when
        omitting `confirm` returned a preview, a void-returning wrapper
        reported success while the memory stayed put.
        """
        _container, ctx, tool_fn = self._build_tool()

        with pytest.raises(TypeError, match="confirm"):
            asyncio.run(tool_fn(memory_id="mem-1", ctx=ctx))

    def test_explicit_false_returns_self_announcing_preview(self) -> None:
        container, ctx, tool_fn = self._build_tool()
        container.storage.get_memory.return_value = _sample_memory()

        result = asyncio.run(tool_fn(memory_id="mem-1", ctx=ctx, confirm=False))

        assert result["status"] == "preview"
        assert result["memory_id"] == "mem-1"
        assert result["deleted"] is False
        assert result["next_step"]
        container.storage.delete_memory.assert_not_called()

    def test_confirm_true_deletes(self) -> None:
        container, ctx, tool_fn = self._build_tool()

        result = asyncio.run(tool_fn(memory_id="mem-1", ctx=ctx, confirm=True))

        assert result["status"] == "ok"
        assert result["memory_id"] == "mem-1"
        assert result["deleted"] is True
        container.storage.delete_memory.assert_called_once_with("mem-1")


# ── MCP memory_stats ─────────────────────────────────────────────


class TestMCPMemoryStats:
    def test_returns_correct_counts(self) -> None:
        mcp_mod = pytest.importorskip("mcp")  # noqa: F841
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        container.storage.count_memory.return_value = 3
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
        result = asyncio.run(tool_fn(ctx=ctx))

        assert result["total"] == 3
        assert result["pinned"] == 1
        assert result["by_tag"]["decision"] == 2
        assert result["by_tag"]["context"] == 2
        assert result["by_source"]["mcp"] == 2
        assert result["by_source"]["api"] == 1

    def test_scoping_is_pushed_to_the_store(self) -> None:
        """Both the count and the histogram source must be project-scoped.

        The old body pulled every row and filtered in Python, so a scoped
        stats call on a multi-project DB loaded every other project's rows
        only to discard them. `count_memory` answers the total in SQL.
        """
        mcp_mod = pytest.importorskip("mcp")  # noqa: F841
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        container = MagicMock()
        container.storage.count_memory.return_value = 1
        container.storage.list_memory.return_value = [_sample_memory(id="m1", project_id="proj-1")]
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        mcp = FastMCP("test")
        register(mcp)
        tool_fn = mcp._tool_manager._tools["memory_stats"].fn
        result = asyncio.run(tool_fn(ctx=ctx, project_id="proj-1"))

        assert result["total"] == 1
        container.storage.count_memory.assert_called_once_with(project_id="proj-1")
        assert container.storage.list_memory.call_args.kwargs["project_id"] == "proj-1"


class TestMemoryStatsParity:
    """MCP and REST must agree — the body used to be duplicated verbatim."""

    def _store(self, tmp_path: Path) -> SqliteStore:
        store = SqliteStore(str(tmp_path / "oc.db"))
        store.init_schema()
        store.add_project(Project(id="proj-1", name="one", metadata={}))
        store.add_project(Project(id="proj-2", name="two", metadata={}))
        store.add_memory(MemoryItem(content="a", tags=["decision"], pinned=True, project_id="proj-1", source="mcp"))
        store.add_memory(MemoryItem(content="b", tags=["context"], pinned=False, project_id="proj-1", source="api"))
        store.add_memory(MemoryItem(content="c", tags=["context"], pinned=False, project_id="proj-2", source="api"))
        return store

    def test_scoped_stats_exclude_other_projects(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        result = stats_memory.execute(store, "proj-1")
        assert result["total"] == 2
        assert result["pinned"] == 1
        assert result["by_source"] == {"mcp": 1, "api": 1}

    def test_unscoped_stats_cover_everything(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        result = stats_memory.execute(store, None)
        assert result["total"] == 3
        assert result["by_tag"]["context"] == 2

    def test_total_agrees_with_count_memory(self, tmp_path: Path) -> None:
        store = self._store(tmp_path)
        assert stats_memory.execute(store, "proj-1")["total"] == store.count_memory(project_id="proj-1")


# ── memory_stats: bounded by_tag histogram (mcp-feedback 2026-08-28) ──


def _tag_heavy_store(tmp_path: Path) -> SqliteStore:
    from openchronicle.core.domain.models.memory_item import MemoryItem
    from openchronicle.core.domain.models.project import Project

    store = SqliteStore(str(tmp_path / "stats.db"))
    store.init_schema()
    store.add_project(Project(id="p", name="p"))
    # One dominant tag and a 40-tag long tail of count-1 entries.
    for i in range(40):
        store.add_memory(MemoryItem(id=f"m{i}", content=f"row {i}", tags=["common", f"unique-{i:02d}"], project_id="p"))
    return store


def test_stats_by_tag_is_capped_and_count_ordered(tmp_path: Path) -> None:
    """An unscoped stats call used to return the whole tail — ~700
    count-1 tags on the live corpus, ~95% of the payload. by_tag is now
    the top_tags most frequent, with the remainder rolled up."""
    from openchronicle.core.application.use_cases import stats_memory

    store = _tag_heavy_store(tmp_path)
    result = stats_memory.execute(store, top_tags=5)
    store.close()

    assert len(result["by_tag"]) == 5
    assert next(iter(result["by_tag"])) == "common", "count-ordered: the dominant tag leads"
    assert result["by_tag"]["common"] == 40
    assert result["other_tags"] == 36, "41 distinct tags minus the 5 shown"
    assert result["total"] == 40


def test_stats_omits_rollup_when_nothing_was_rolled_up(tmp_path: Path) -> None:
    from openchronicle.core.application.use_cases import stats_memory

    store = _tag_heavy_store(tmp_path)
    result = stats_memory.execute(store, top_tags=1000)
    store.close()

    assert len(result["by_tag"]) == 41
    assert "other_tags" not in result, "no rollup line when the map is complete"
