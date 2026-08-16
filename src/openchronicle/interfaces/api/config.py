"""HTTP API server configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from openchronicle.interfaces.mcp.config import DEFAULT_ALLOWED_HOSTS, parse_allowed_hosts


@dataclass(frozen=True)
class HTTPConfig:
    """Immutable HTTP API server configuration.

    Three-layer precedence: env var > file config (core.json api section) > default.

    Env vars:
        OC_API_HOST — bind address (default: "127.0.0.1")
        OC_API_PORT — port number (default: 8000)
        OC_API_KEY  — required API key for authentication (no default — disabled if unset)
        OC_API_ALLOWED_HOSTS — CSV Host-header allowlist for the REST
            surface (same entry format as OC_MCP_ALLOWED_HOSTS, which is
            the fallback when this is unset — one stack env var protects
            both surfaces). Loopback hosts are always allowed on top.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    api_key: str | None = None
    allowed_hosts: tuple[str, ...] = DEFAULT_ALLOWED_HOSTS

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError(f"port must be in [1, 65535], got {self.port}")

    @classmethod
    def from_env(cls, file_config: dict[str, object] | None = None) -> HTTPConfig:
        """Load config from environment variables with file_config fallback."""
        fc = file_config or {}

        host = os.environ.get("OC_API_HOST", "").strip() or _str_or_default(fc.get("host"), "127.0.0.1")

        port_env = os.environ.get("OC_API_PORT", "").strip()
        port_file = fc.get("port")
        if port_env:
            port = int(port_env)
        elif isinstance(port_file, int):
            port = port_file
        else:
            port = 8000

        api_key = (os.environ.get("OC_API_KEY", "").strip() or _str_or_default(fc.get("api_key"), "")) or None

        allowed_hosts = parse_allowed_hosts(
            os.environ.get("OC_API_ALLOWED_HOSTS") or os.environ.get("OC_MCP_ALLOWED_HOSTS"),
            fc.get("allowed_hosts"),
        )

        return cls(host=host, port=port, api_key=api_key, allowed_hosts=allowed_hosts)


def _str_or_default(value: object, default: str) -> str:
    """Return value as str if truthy, else default."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default
