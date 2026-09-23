"""Entry point for ``python -m openchronicle.interfaces.mcp``.

Starts the MCP server with stdio transport using default configuration.
"""

from __future__ import annotations

import logging
import sys


def main() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("mcp SDK is not installed. Install with: pip install -e '.[mcp]'", file=sys.stderr)
        sys.exit(1)

    from openchronicle.core.infrastructure.wiring.container import CoreContainer
    from openchronicle.interfaces.mcp.config import MCPConfig
    from openchronicle.interfaces.mcp.server import create_server

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    container = CoreContainer()
    config = MCPConfig.from_env()
    server = create_server(container, config)
    # The server's own lifespan logs at DEBUG (it runs per request over
    # stateless HTTP), so the one startup line lives here. logging writes
    # to stderr, which keeps stdout clean for the stdio protocol.
    logging.getLogger(__name__).info("OpenChronicle MCP server starting (%s transport)", config.transport)
    server.run(transport=config.transport)


if __name__ == "__main__":
    main()
