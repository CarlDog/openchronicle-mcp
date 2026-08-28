"""The client-visible MCP error envelope, captured on mcp 1.29.0.

Companion to `test_mcp_tool_schema_snapshot.py`. That one pins what a tool
ACCEPTS and RETURNS; this pins what a client sees when a call FAILS — the
other half of the surface, and the half with no coverage at all before
2026-08-28.

Why it matters for the `mcp<2` lift: error wrapping is FastMCP's own
convention, not the MCP spec's. The "Error executing tool {name}: "
prefix, the decision to stringify an exception into text content rather
than a structured payload, and the generated `{tool}Arguments` model name
in a pydantic failure are all library behaviour that a major version is
free to change. A migration that silently reshapes them breaks every
client that reads these strings, and nothing would have failed.

**Asserted: only what mcp/FastMCP owns, or what we own.** The pydantic
validation text is deliberately NOT pinned verbatim — it embeds the
pydantic version (`errors.pydantic.dev/2.13/...`) and pydantic's own value
formatting, so a Dependabot bump would break this test for a reason having
nothing to do with mcp. That is exactly the regenerate-reflexively rot the
schema snapshot's docstring warns about. We assert the generated model
name and the offending field name instead.

Verbatim 1.29.0 record, for diffing after the migration:

    unknown tool          Unknown tool: no_such_tool
    missing required arg  Error executing tool memory_get: 1 validation
                          error for memory_getArguments / memory_id /
                          Field required [type=missing, input_value={},
                          input_type=dict] / For further information
                          visit https://errors.pydantic.dev/2.13/v/missing
    NotFoundError         Error executing tool memory_get: Memory not
                          found: <id>
    ValidationError       Error executing tool memory_search: mode must be
                          one of ('hybrid', 'keyword', 'semantic'), got
                          'bogus'
    cross-field invariant Error executing tool memory_update: At least one
                          of content or tags must be provided
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

_PREFIX = "Error executing tool {name}: "


@asynccontextmanager
async def _session(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AsyncIterator[Any]:
    """A real client<->server session, so tools get a request Context.

    Calling `FastMCP.call_tool` directly is not equivalent: without a
    request context every tool fails with "Context is not available
    outside of a request", which masks the error under test.
    """
    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "errors.db"))
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    container = CoreContainer()
    try:
        server = create_server(container, MCPConfig.from_env())
        async with create_connected_server_and_client_session(server._mcp_server) as session:  # noqa: SLF001
            await session.initialize()
            yield session
    finally:
        container.close()


def _text(result: CallToolResult) -> str:
    assert result.isError, "expected an error result, got a success"
    blocks = [b.text for b in result.content if b.type == "text"]
    assert blocks, "an error result carried no text content for the model to read"
    return "\n".join(blocks)


@pytest.mark.anyio
async def test_unknown_tool_is_reported_without_the_executing_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The asymmetry IS the convention: a dispatch failure is not an
    execution failure, so it carries no "Error executing tool" prefix.
    """
    async with _session(monkeypatch, tmp_path) as session:
        result = await session.call_tool("no_such_tool", {})

    assert _text(result) == "Unknown tool: no_such_tool"


@pytest.mark.anyio
async def test_missing_required_argument_names_the_field_and_the_generated_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Schema validation happens before the handler runs.

    `memory_getArguments` is func_metadata's generated model name — the
    naming 2.x's metadata rewrite would most plausibly change. The
    pydantic version URL and value formatting are deliberately not
    asserted; they are pydantic's to change, not mcp's.
    """
    async with _session(monkeypatch, tmp_path) as session:
        result = await session.call_tool("memory_get", {})

    text = _text(result)
    assert text.startswith(_PREFIX.format(name="memory_get"))
    assert "validation error for memory_getArguments" in text
    assert "memory_id" in text, "the error must name the field the caller omitted"


@pytest.mark.anyio
async def test_not_found_passes_the_domain_message_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A NotFoundError raised in a handler reaches the client as prose.

    Note what does NOT survive: the exception carries a structured
    `.code` (MEMORY_NOT_FOUND), and FastMCP drops it. The REST surface
    maps that code to an HTTP status and an envelope field; MCP clients
    get the message only. Pinned as current behaviour, not endorsed —
    see the error_code follow-up in docs/V3_PLAN.md.
    """
    missing = "00000000-0000-0000-0000-000000000000"
    async with _session(monkeypatch, tmp_path) as session:
        result = await session.call_tool("memory_get", {"memory_id": missing})

    text = _text(result)
    assert text == _PREFIX.format(name="memory_get") + f"Memory not found: {missing}"


@pytest.mark.anyio
async def test_domain_validation_error_passes_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`mode` is typed `str`, so pydantic accepts it and the domain check
    is what rejects it. That ordering is the point: the message the caller
    sees is ours, and it enumerates the valid values.
    """
    async with _session(monkeypatch, tmp_path) as session:
        result = await session.call_tool("memory_search", {"query": "x", "mode": "bogus"})

    text = _text(result)
    assert text.startswith(_PREFIX.format(name="memory_search"))
    assert "mode must be one of" in text
    assert "'bogus'" in text, "the rejected value must be echoed back so the caller can fix the call"


@pytest.mark.anyio
async def test_cross_field_invariant_is_enforced_in_the_handler(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The case inputSchema structurally cannot cover.

    "at least one of content or tags" is an object-level rule, and MCP's
    inputSchema is per-field only — a pydantic/Zod object-level refine is
    dropped when the schema is generated. So this invariant can only be
    enforced in the handler, and only a live call proves it is. If a
    migration ever moved this class of check into schema generation, this
    test is what would notice.

    `test_memory_update.test_neither_content_nor_tags_raises` already
    covers the use case in isolation; what is unique here is that the
    rejection survives the MCP path intact — isError set, message not
    swallowed or reshaped by the transport.
    """
    async with _session(monkeypatch, tmp_path) as session:
        created = await session.call_tool("project_create", {"name": "errors"})
        project_id = json.loads(created.content[0].text)["id"]
        saved = await session.call_tool("memory_save", {"project_id": project_id, "content": "hello"})
        memory_id = json.loads(saved.content[0].text)["id"]

        result = await session.call_tool("memory_update", {"memory_id": memory_id})

    text = _text(result)
    assert text.startswith(_PREFIX.format(name="memory_update"))
    assert "At least one of content or tags must be provided" in text
