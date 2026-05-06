"""MCP server configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

# Default allowed Host header values for the streamable-HTTP transport.
# FastMCP rejects requests whose Host header doesn't match this allowlist
# (defense against DNS rebinding). The `:*` wildcard matches any port.
# Operators with non-loopback bindings extend this via OC_MCP_ALLOWED_HOSTS.
_DEFAULT_ALLOWED_HOSTS: tuple[str, ...] = (
    "127.0.0.1:*",
    "localhost:*",
    "[::1]:*",
)


@dataclass(frozen=True)
class MCPConfig:
    """Immutable MCP server configuration.

    Three-layer precedence: env var > file config (core.json mcp section) > default.

    Env vars:
        OC_MCP_TRANSPORT — "stdio", "sse", or "streamable-http" (default: "stdio")
        OC_MCP_HOST — bind address for SSE/HTTP transport (default: "127.0.0.1")
        OC_MCP_PORT — port for SSE/HTTP transport (default: 8080)
        OC_MCP_ALLOWED_HOSTS — CSV of allowed Host header values for the
            streamable-HTTP transport. Each entry may use ``:*`` as a port
            wildcard (e.g. ``carldog-nas:*``). Default: localhost variants
            only — operators binding to a LAN-reachable interface MUST add
            their hostname here or all non-loopback requests will 421.
    """

    transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    host: str = "127.0.0.1"
    port: int = 8080
    server_name: str = "openchronicle"
    allowed_hosts: tuple[str, ...] = _DEFAULT_ALLOWED_HOSTS

    @classmethod
    def from_env(cls, file_config: dict[str, object] | None = None) -> MCPConfig:
        """Load config from environment variables with file_config fallback."""
        fc = file_config or {}

        transport = os.environ.get("OC_MCP_TRANSPORT", "").strip() or _str_or_default(fc.get("transport"), "stdio")
        if transport not in ("stdio", "sse", "streamable-http"):
            raise ValueError(f"Invalid MCP transport: {transport!r}. Must be 'stdio', 'sse', or 'streamable-http'.")

        host = os.environ.get("OC_MCP_HOST", "").strip() or _str_or_default(fc.get("host"), "127.0.0.1")

        port_env = os.environ.get("OC_MCP_PORT", "").strip()
        port_file = fc.get("port")
        if port_env:
            port = int(port_env)
        elif isinstance(port_file, int):
            port = port_file
        else:
            port = 8080

        server_name = _str_or_default(fc.get("server_name"), "openchronicle")

        allowed_hosts = _parse_allowed_hosts(
            os.environ.get("OC_MCP_ALLOWED_HOSTS"),
            fc.get("allowed_hosts"),
        )

        return cls(
            transport=cast(Literal["stdio", "sse", "streamable-http"], transport),
            host=host,
            port=port,
            server_name=server_name,
            allowed_hosts=allowed_hosts,
        )


def _parse_allowed_hosts(
    env_value: str | None,
    file_value: object,
) -> tuple[str, ...]:
    """Parse the OC_MCP_ALLOWED_HOSTS env var (CSV) with file fallback.

    Empty / unset → default (localhost variants only).
    Env var wins if set. File value (if a list of strings) is the second
    layer. Whitespace-trimmed; empty entries dropped.
    """
    if env_value is not None and env_value.strip():
        parsed = tuple(h.strip() for h in env_value.split(",") if h.strip())
        return parsed if parsed else _DEFAULT_ALLOWED_HOSTS

    if isinstance(file_value, list):
        parsed = tuple(str(h).strip() for h in file_value if str(h).strip())
        if parsed:
            return parsed

    return _DEFAULT_ALLOWED_HOSTS


def _str_or_default(value: object, default: str) -> str:
    """Return value as str if truthy, else default."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default
