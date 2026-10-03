"""MCP tools refuse arguments they do not declare (QUAL-11).

FastMCP's generated argument model ignores extra keys. Before this check,
`memory_search(limit=3)` returned the default 8 results with no error,
because that tool counts with `top_k` while its sibling `memory_list` uses
`limit`. A misspelled optional parameter is the worst case: the call
succeeds and does something other than what was asked.

These tests drive a real client<->server session, so they exercise the
dispatch path a client actually hits.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.config import MCPConfig
from openchronicle.interfaces.mcp.server import create_server

_MISSING_ID = "00000000-0000-0000-0000-000000000000"


@asynccontextmanager
async def _session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncIterator[Any]:
    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "unknown-args.db"))
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    monkeypatch.setenv("OC_BACKUP_DIR", str(tmp_path / "backups"))
    container = CoreContainer()
    try:
        # Backup tools on, so the check is proven on every tool OC can register.
        server = create_server(container, MCPConfig.from_env(), backup_tools_enabled=True)
        async with create_connected_server_and_client_session(server._mcp_server) as session:  # noqa: SLF001
            await session.initialize()
            yield session
    finally:
        container.close()


def _error_text(result: CallToolResult) -> str:
    assert result.isError, f"expected an error result, got: {result.content}"
    return "\n".join(b.text for b in result.content if b.type == "text")


def _placeholder(schema: dict[str, Any]) -> Any:
    """A schema-valid value for a required parameter.

    The values never reach a handler (the refusal comes first); they are
    supplied so the error cannot be the missing-required-field one.
    """
    kind = schema.get("type")
    if kind == "boolean":
        return True
    if kind == "integer":
        return 1
    if kind == "array":
        return [_MISSING_ID]
    return _MISSING_ID


def _misspell(name: str) -> str:
    """A plausible typo: drop the last character (`top_k` -> `top_`)."""
    return name[:-1] if len(name) > 3 else name + "x"


@pytest.mark.anyio
async def test_every_tool_refuses_a_misspelled_optional_parameter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Walks the live registry, so a tool added later is covered without
    editing this test. A tool with no optional parameter gets a stray key.
    """
    async with _session(monkeypatch, tmp_path) as session:
        tools = (await session.list_tools()).tools
        # 18 always-on tools plus the 5 opt-in backup tools.
        assert len(tools) == 23, sorted(t.name for t in tools)

        for tool in tools:
            props: dict[str, Any] = tool.inputSchema.get("properties", {})
            required = set(tool.inputSchema.get("required", []))
            args = {name: _placeholder(props[name]) for name in required}
            optional = [name for name in props if name not in required]
            bad_key = _misspell(optional[0]) if optional else "unexpected_argument"
            assert bad_key not in props
            args[bad_key] = 1

            text = _error_text(await session.call_tool(tool.name, args))

            assert text.startswith(f"Error executing tool {tool.name}: INVALID_ARGUMENT: unknown argument "), text
            assert f"'{bad_key}'" in text, "the error must name the refused key"
            assert "Valid arguments: " in text
            for name in props:
                assert name in text, f"{tool.name}: the error must list valid argument {name!r}"


@pytest.mark.anyio
async def test_limit_on_memory_search_points_at_top_k(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The reported trap, both directions: each sibling's count name is
    refused on the other with a pointer to the right one.
    """
    async with _session(monkeypatch, tmp_path) as session:
        search = _error_text(await session.call_tool("memory_search", {"query": "x", "limit": 3}))
        listing = _error_text(await session.call_tool("memory_list", {"top_k": 3}))

    assert "unknown argument 'limit' (did you mean 'top_k'?)" in search
    assert "unknown argument 'top_k' (did you mean 'limit'?)" in listing


@pytest.mark.anyio
async def test_close_spelling_gets_a_suggestion(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async with _session(monkeypatch, tmp_path) as session:
        text = _error_text(await session.call_tool("memory_search", {"query": "x", "project": _MISSING_ID}))

    assert "unknown argument 'project' (did you mean 'project_id'?)" in text


@pytest.mark.anyio
async def test_every_unknown_key_is_named_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async with _session(monkeypatch, tmp_path) as session:
        text = _error_text(await session.call_tool("health", {"zeta": 1, "alpha": 2}))

    assert "unknown arguments 'alpha', 'zeta'." in text
    assert "Valid arguments: (none)." in text


@pytest.mark.anyio
async def test_the_context_parameter_is_not_a_client_argument(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`ctx` is injected by FastMCP, not part of the schema; a client that
    sends it is refused rather than allowed to collide with the injection.
    """
    async with _session(monkeypatch, tmp_path) as session:
        text = _error_text(await session.call_tool("project_list", {"ctx": {}}))

    assert "unknown argument 'ctx'" in text


@pytest.mark.anyio
async def test_a_refused_call_has_no_side_effect(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The refusal comes before the handler: a write with a typo writes
    nothing, so the caller can fix the call and retry without a duplicate.
    """
    async with _session(monkeypatch, tmp_path) as session:
        refused = await session.call_tool("project_create", {"name": "typo", "metdata": {"a": 1}})
        listed = await session.call_tool("project_list", {})

    assert refused.isError
    assert "did you mean 'metadata'?" in _error_text(refused)
    assert not listed.isError
    assert listed.structuredContent == {"result": []}


@pytest.mark.anyio
async def test_declared_arguments_still_work(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async with _session(monkeypatch, tmp_path) as session:
        created = await session.call_tool("project_create", {"name": "ok"})
        project_id = json.loads(created.content[0].text)["id"]
        for i in range(5):
            saved = await session.call_tool("memory_save", {"project_id": project_id, "content": f"alpha {i}"})
            assert not saved.isError
        result = await session.call_tool("memory_search", {"query": "alpha", "project_id": project_id, "top_k": 2})

    assert not result.isError
    assert result.structuredContent is not None
    assert len(result.structuredContent["result"]) == 2


@pytest.mark.anyio
async def test_unknown_tool_is_still_reported_as_unknown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The argument check only applies to tools that exist; dispatch keeps
    FastMCP's own unknown-tool message (pinned in test_mcp_error_shape).
    """
    async with _session(monkeypatch, tmp_path) as session:
        text = _error_text(await session.call_tool("no_such_tool", {"limit": 1}))

    assert text == "Unknown tool: no_such_tool"
