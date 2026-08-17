"""Handler-level coverage for the MCP tools the 2026-08-15 review found untested.

Six of 18 tools had no test exercising their registered handler (only
their use cases were covered): project_get / project_update /
project_delete / project_delete_bulk / memory_update / memory_embed —
and memory_embed was untested at every interface layer despite its
ok/partial/failed outcome mapping being where a real 2026-05 bug lived.

This file also carries three structural guards:

- an UNCONDITIONAL ``import mcp`` — the other MCP test files
  ``importorskip("mcp")``, so a failed resolve of the load-bearing
  ``mcp>=1.0,<2`` pin would silently skip the whole MCP surface while
  CI stayed green. Here it fails collection instead.
- every registered tool is a coroutine (the 2026-07-02 event-loop
  regression guard, previously pinned only incidentally for tools that
  happened to have handler tests).
- ``confirm`` keeps no default on BOTH project delete tools (the
  memory_delete twin was pinned; these were not).
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import UTC, datetime
from unittest.mock import patch

import mcp  # noqa: F401 — unconditional: a missing mcp extra must FAIL, not skip
import mcp.server.fastmcp  # noqa: F401 — removed in mcp 2.0; the <2 pin is load-bearing
import pytest

from openchronicle.core.application.services.embedding_service import EmbeddingService
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.mcp.config import MCPConfig
from openchronicle.interfaces.mcp.server import create_server
from openchronicle.interfaces.mcp.tools import memory as memory_tools
from openchronicle.interfaces.mcp.tools import project as project_tools
from tests.helpers.mcp_tools import mock_container, mock_ctx, tool_fn

_NOW = datetime(2026, 3, 1, tzinfo=UTC)


def _project(**overrides: object) -> Project:
    defaults: dict[str, object] = {"id": "proj-1", "name": "test", "metadata": {}, "created_at": _NOW}
    defaults.update(overrides)
    return Project(**defaults)  # type: ignore[arg-type]


def _memory(**overrides: object) -> MemoryItem:
    defaults: dict[str, object] = {
        "id": "mem-1",
        "content": "hello",
        "tags": ["t"],
        "pinned": False,
        "project_id": "proj-1",
        "source": "test",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return MemoryItem(**defaults)  # type: ignore[arg-type]


# ── structural guards ────────────────────────────────────────────────


def test_every_registered_tool_is_a_coroutine() -> None:
    """A sync tool runs inline on FastMCP's event loop — the 2026-07-02
    regression. Guarded structurally for all 18, not just the tools that
    happen to have handler tests invoking them via asyncio.run.
    """
    server = create_server(mock_container(), MCPConfig())
    not_async = [name for name, tool in server._tool_manager._tools.items() if not inspect.iscoroutinefunction(tool.fn)]
    assert not_async == []


def test_project_delete_tools_keep_confirm_required() -> None:
    """Reintroducing `confirm: bool = False` would turn omission back
    into a success-shaped preview (the mnemosyne bug). The memory_delete
    twin is pinned in test_memory_crud_parity; these two were not.
    """
    for name in ("project_delete", "project_delete_bulk"):
        fn = tool_fn(project_tools.register, name)
        param = inspect.signature(fn).parameters["confirm"]
        assert param.default is inspect.Parameter.empty, f"{name}.confirm grew a default"


# ── project handler gaps ─────────────────────────────────────────────


class TestProjectGet:
    def test_missing_project_raises_not_found(self) -> None:
        container = mock_container()
        container.storage.get_project.return_value = None
        fn = tool_fn(project_tools.register, "project_get")
        with pytest.raises(NotFoundError, match="Project not found"):
            asyncio.run(fn(project_id="nope", ctx=mock_ctx(container)))

    def test_returns_serialized_project(self) -> None:
        container = mock_container()
        container.storage.get_project.return_value = _project()
        fn = tool_fn(project_tools.register, "project_get")
        result = asyncio.run(fn(project_id="proj-1", ctx=mock_ctx(container)))
        assert result["id"] == "proj-1"
        assert result["name"] == "test"


class TestProjectUpdate:
    def test_threads_fields_to_use_case(self) -> None:
        container = mock_container()
        fn = tool_fn(project_tools.register, "project_update")
        with patch.object(project_tools.update_project, "execute", return_value=_project(name="renamed")) as mock_exec:
            result = asyncio.run(fn(project_id="proj-1", ctx=mock_ctx(container), name="renamed", metadata={"k": 1}))
        kwargs = mock_exec.call_args.kwargs
        assert kwargs["project_id"] == "proj-1"
        assert kwargs["name"] == "renamed"
        assert kwargs["metadata"] == {"k": 1}
        assert result["name"] == "renamed"


class TestProjectDelete:
    def test_preview_and_confirm_thread_through(self) -> None:
        container = mock_container()
        fn = tool_fn(project_tools.register, "project_delete")
        payload = {"status": "preview", "deleted": False, "project_id": "proj-1"}
        with patch.object(project_tools.delete_project, "execute", return_value=payload) as mock_exec:
            result = asyncio.run(fn(project_id="proj-1", ctx=mock_ctx(container), confirm=False))
        assert mock_exec.call_args.kwargs["confirm"] is False
        assert result == payload


class TestProjectDeleteBulk:
    def test_ids_and_confirm_thread_through(self) -> None:
        container = mock_container()
        fn = tool_fn(project_tools.register, "project_delete_bulk")
        payload = {"status": "ok", "deleted": True, "missing": ["ghost"]}
        with patch.object(project_tools.delete_projects, "execute", return_value=payload) as mock_exec:
            result = asyncio.run(fn(project_ids=["a", "ghost"], ctx=mock_ctx(container), confirm=True))
        assert mock_exec.call_args.kwargs["project_ids"] == ["a", "ghost"]
        assert mock_exec.call_args.kwargs["confirm"] is True
        assert result["missing"] == ["ghost"]


# ── memory handler gaps ──────────────────────────────────────────────


class TestMemoryUpdate:
    def test_threads_fields_and_serializes(self) -> None:
        container = mock_container()
        fn = tool_fn(memory_tools.register, "memory_update")
        with patch.object(memory_tools.update_memory, "execute", return_value=_memory(content="edited")) as mock_exec:
            result = asyncio.run(fn(memory_id="mem-1", ctx=mock_ctx(container), content="edited"))
        assert mock_exec.call_args.kwargs["memory_id"] == "mem-1"
        assert mock_exec.call_args.kwargs["content"] == "edited"
        assert result["content"] == "edited"


class _FlakyAdapter(StubEmbeddingAdapter):
    """Stub adapter that fails on content containing 'poison'."""

    def embed(self, text: str) -> list[float]:
        if "poison" in text:
            raise RuntimeError("provider exploded")
        return super().embed(text)


class TestMemoryEmbed:
    """The ok/partial/failed mapping lives per-surface; the 2026-05 bug
    ('status=ok with generated=0') lived exactly here, guarded only at
    the service layer until now.
    """

    @staticmethod
    def _store_with(contents: list[str]) -> SqliteStore:
        store = SqliteStore(db_path=":memory:")
        store.init_schema()
        store.add_project(_project())
        for i, content in enumerate(contents):
            store.add_memory(_memory(id=f"mem-{i}", content=content))
        return store

    def _run(self, service: EmbeddingService | None, store: SqliteStore | None = None) -> dict[str, object]:
        container = mock_container(embedding_service=service)
        if store is not None:
            container.storage = store
        fn = tool_fn(memory_tools.register, "memory_embed")
        result: dict[str, object] = asyncio.run(fn(ctx=mock_ctx(container)))
        return result

    def test_not_configured_when_service_absent(self) -> None:
        result = self._run(None)
        assert result["status"] == "not_configured"

    def test_ok_when_all_generate(self) -> None:
        store = self._store_with(["alpha", "beta"])
        service = EmbeddingService(port=StubEmbeddingAdapter(dims=8), store=store)
        result = self._run(service, store)
        assert result["status"] == "ok"
        assert result["generated"] == 2
        assert result["failed"] == 0
        assert result["embedded"] == 2  # embedding_status() merged in

    def test_partial_when_some_fail(self) -> None:
        store = self._store_with(["alpha", "poison pill"])
        service = EmbeddingService(port=_FlakyAdapter(dims=8), store=store)
        result = self._run(service, store)
        assert result["status"] == "partial"
        assert result["generated"] == 1
        assert result["failed"] == 1

    def test_failed_when_nothing_generates(self) -> None:
        store = self._store_with(["poison one", "poison two"])
        service = EmbeddingService(port=_FlakyAdapter(dims=8), store=store)
        result = self._run(service, store)
        assert result["status"] == "failed"
        assert result["generated"] == 0
        assert result["failed"] == 2


class TestProjectUpdateValidation:
    def test_both_fields_none_raises_domain_validation(self) -> None:
        """Previously fell through to the store's bare ValueError — the
        memory twin validated in its use case; the project twin didn't.
        """
        from openchronicle.core.domain.exceptions import ValidationError

        container = mock_container()
        fn = tool_fn(project_tools.register, "project_update")
        with pytest.raises(ValidationError, match="at least one"):
            asyncio.run(fn(project_id="proj-1", ctx=mock_ctx(container)))


class TestAddMemoryFkTranslation:
    def test_unknown_project_id_raises_not_found(self) -> None:
        """A wrong project_id used to surface as a raw 'FOREIGN KEY
        constraint failed' (REST 500). The store translates it now.
        """
        store = SqliteStore(db_path=":memory:")
        store.init_schema()
        with pytest.raises(NotFoundError, match="Project not found"):
            store.add_memory(_memory(project_id="no-such-project"))
