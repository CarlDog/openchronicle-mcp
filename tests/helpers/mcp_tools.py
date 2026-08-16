"""Shared helpers for MCP tool handler tests.

Consolidates the FastMCP tool-extraction ritual and the mock-container
shape that were previously hand-rolled per test file (2026-08-15 review:
~15 ritual repeats across three files, in two divergent forms, and a
container builder still fabricating v2-era attributes).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock


def tool_fn(register: Any, name: str) -> Any:
    """Register tools on a throwaway FastMCP server and return one's fn."""
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("test")
    register(server)
    return server._tool_manager._tools[name].fn


def mock_container(**overrides: Any) -> Any:
    """Minimal mock of the v3 CoreContainer surface tools actually use.

    Only ``storage``, ``embedding_service``, and ``file_configs`` exist
    on the real container — no v2 ghosts (event_logger, llm,
    router_policy, ...).
    """
    container = MagicMock()
    container.file_configs = {}
    container.storage = MagicMock()
    container.embedding_service = None
    for key, value in overrides.items():
        setattr(container, key, value)
    return container


def mock_ctx(container: Any) -> Any:
    """A FastMCP Context double delivering ``container`` via lifespan."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"container": container}
    return ctx
