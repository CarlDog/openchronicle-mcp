"""The MCP tool signatures are under semver. This is what enforces it.

`docs/api/STABILITY.md` has bound since the v3.0.0 tag (2026-08-28): a
breaking change to an MCP tool signature is a MAJOR event. Nothing checked
that. This snapshots all 18 registered schemas so a change has to be
deliberate — the diff appears in review, and the committed fixture is the
record of what the promise currently covers.

Two uses:

1. **Semver guard.** An accidental signature change fails here rather than
   reaching a client.
2. **Migration proof.** The `mcp<2` pin has to lift eventually. The only
   way to show that migration was schema-invisible is to compare against a
   snapshot taken before it — this one, captured on mcp 1.29.0.

**Descriptions are deliberately excluded.** They are the LLM-facing
contract and worth getting right, but they are documentation, not
signature: a reworded docstring is not a semver event, and a snapshot that
fails on every prose edit gets regenerated reflexively until it guards
nothing. What is captured is names, parameters, types, defaults and
required-ness.

Regenerate ONLY for an intended change, and say why in the commit:

    python -m tests.helpers.regen_tool_schemas
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.config import MCPConfig
from openchronicle.interfaces.mcp.server import create_server

_FIXTURE = Path(__file__).parent / "fixtures" / "mcp_tool_schemas.json"


def _strip_descriptions(node: Any) -> Any:
    """Drop description fields and sort keys, so the diff is signature-only."""
    if isinstance(node, dict):
        return {k: _strip_descriptions(v) for k, v in sorted(node.items()) if k != "description"}
    if isinstance(node, list):
        return [_strip_descriptions(v) for v in node]
    return node


async def _live_schemas(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    # Point the store at a temp DB: building the server constructs the real
    # container, and this test must never touch an operator's database.
    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "schema.db"))
    monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
    server = create_server(CoreContainer(), MCPConfig.from_env())
    tools = await server.list_tools()
    return {t.name: _strip_descriptions(t.inputSchema) for t in tools}


@pytest.mark.anyio
async def test_tool_schemas_match_the_committed_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    live = await _live_schemas(monkeypatch, tmp_path)
    expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))

    added = sorted(set(live) - set(expected))
    removed = sorted(set(expected) - set(live))
    assert not added, f"new MCP tool(s) {added} — regenerate the snapshot and note it as a MINOR addition"
    assert not removed, f"MCP tool(s) {removed} REMOVED — that is a MAJOR event under STABILITY.md"

    changed = [name for name in sorted(live) if live[name] != expected[name]]
    assert not changed, (
        f"MCP tool signature(s) changed: {changed}. Under STABILITY.md this is a semver event — "
        f"tightening a parameter or reshaping a schema is MAJOR, a new optional parameter is MINOR. "
        f"If intended, regenerate the fixture and say which it is in the commit message."
    )


@pytest.mark.anyio
async def test_snapshot_covers_every_registered_tool(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Guard the guard: an empty or partial fixture would pass vacuously.

    The same failure mode `scan_repository()` had — a comparison against
    nothing succeeds. The count is asserted against the live server, so the
    fixture cannot silently shrink.
    """
    live = await _live_schemas(monkeypatch, tmp_path)
    expected = json.loads(_FIXTURE.read_text(encoding="utf-8"))

    assert len(live) == 18, f"expected 18 registered tools, found {len(live)}"
    assert len(expected) == len(live), "fixture and live server disagree on tool count"
    assert all(s.get("properties") is not None for s in expected.values()), (
        "a fixture entry has no properties block — likely a truncated regeneration"
    )
