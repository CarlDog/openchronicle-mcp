"""Filtered OpenAPI spec for memory-focused LLM clients (Open WebUI, etc.).

Surfaces a curated subset of OC's HTTP API (~10 endpoints) instead of the
full ~41-endpoint surface. LLMs degrade meaningfully when given too many
tools to choose from — choice fatigue, wrong tool selection, or refusing
to call any tool. This endpoint is for chat-with-memory consumers that
only need memory CRUD + project scoping.

Mount as an OpenAPI tool server in Open WebUI:

    http://<oc-host>:18000/memory-tools/openapi.json

The ``/openapi.json`` suffix is required because Open WebUI does
path-based spec discovery and only accepts URLs ending in that name. The
``servers`` field is explicitly populated with the request's base URL so
tool paths (e.g. ``/api/v1/memory``) resolve to OC's host root regardless
of how Open WebUI computes the API base from the spec URL location.

For the full surface (operators, MCP clients, etc.), use ``/openapi.json``.

This is a tactical fix — see the strategic discussion about splitting OC's
"personalities" (memory backend vs storytelling vs admin/orchestration)
for the longer-term plan to trim the actual surface.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from starlette.requests import Request

router = APIRouter()


# Curated whitelist: path → set of lowercase HTTP methods to keep.
# Any method on a listed path that isn't in the set is filtered out.
# Any path not listed is omitted from the filtered spec entirely.
_MEMORY_TOOL_PATHS: dict[str, set[str]] = {
    # Memory CRUD — the core "remember / recall" surface
    "/api/v1/memory": {"get", "post"},
    "/api/v1/memory/search": {"get"},
    "/api/v1/memory/stats": {"get"},
    "/api/v1/memory/{memory_id}": {"get", "put", "delete"},
    "/api/v1/memory/{memory_id}/pin": {"put"},
    # Project scoping — memory endpoints take project_id; LLM needs to be
    # able to discover existing projects and create new ones if needed.
    "/api/v1/project": {"get", "post"},
}


@router.get(
    "/openapi.json",
    summary="Curated OpenAPI spec — memory tools only",
    description=(
        "Returns OpenChronicle's OpenAPI spec filtered down to memory + "
        "project endpoints (~10 tools instead of the full ~41). For LLM "
        "clients that import OpenAPI as a tool server. LLMs handle 6-15 "
        "tools well; 41 causes choice fatigue and incorrect tool selection."
    ),
    tags=["system"],
)
def openapi_memory(request: Request) -> dict[str, Any]:
    """Filter OC's OpenAPI spec to memory-related paths only."""
    full = request.app.openapi()
    filtered_paths: dict[str, Any] = {}
    for path, methods in full.get("paths", {}).items():
        if path not in _MEMORY_TOOL_PATHS:
            continue
        wanted = _MEMORY_TOOL_PATHS[path]
        kept = {m: methods[m] for m in methods if m.lower() in wanted}
        if kept:
            filtered_paths[path] = kept

    # Explicit servers entry: tool paths in the spec are absolute (e.g.
    # /api/v1/memory). Some OpenAPI clients (Open WebUI) compute their
    # base URL by stripping /openapi.json from the spec URL — which would
    # give them /memory-tools as the base, then prepend it to /api/v1/...
    # producing the wrong URL. The servers field overrides that — clients
    # spec-compliant enough to read it will hit OC's host root for all
    # tool calls.
    base_url = str(request.base_url).rstrip("/")

    # Preserve components (schemas, securitySchemes, etc.) so $ref's in the
    # kept paths resolve. Marginal bandwidth cost vs walking the refs to
    # narrow the schemas — cleanest path forward.
    return {
        **full,
        "paths": filtered_paths,
        "servers": [{"url": base_url, "description": "OpenChronicle API root"}],
        "info": {
            **full.get("info", {}),
            "title": "OpenChronicle — Memory Tools (curated)",
            "description": (
                "Curated subset of OpenChronicle's HTTP API exposing only "
                "memory + project scoping endpoints, designed for LLM tool-"
                "call clients (Open WebUI, etc.). For the full surface, use "
                "/openapi.json."
            ),
        },
    }
