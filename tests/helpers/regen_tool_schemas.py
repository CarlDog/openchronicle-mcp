"""Regenerate the MCP tool-schema snapshot.

Run ONLY for an intended signature change, and say in the commit message
whether it is MINOR (a new optional parameter) or MAJOR (anything that
tightens or reshapes an existing one) under docs/api/STABILITY.md.

    ./.venv/Scripts/python.exe -m tests.helpers.regen_tool_schemas
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "mcp_tool_schemas.json"


async def _main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OC_DB_PATH"] = str(Path(tmp) / "schema.db")
        os.environ["OC_MAINTENANCE_DISABLED"] = "1"

        from openchronicle.core.infrastructure.wiring.container import CoreContainer
        from openchronicle.interfaces.mcp.config import MCPConfig
        from openchronicle.interfaces.mcp.server import create_server
        from tests.test_mcp_tool_schema_snapshot import _strip_descriptions

        server = create_server(CoreContainer(), MCPConfig.from_env())
        tools = await server.list_tools()
        snap = {t.name: _strip_descriptions(t.inputSchema) for t in sorted(tools, key=lambda x: x.name)}

    _FIXTURE.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(snap)} tool schemas to {_FIXTURE}")


if __name__ == "__main__":
    asyncio.run(_main())
