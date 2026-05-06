"""Tests for MCP server configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

mcp_mod = pytest.importorskip("mcp")  # noqa: F841

from openchronicle.interfaces.mcp.config import MCPConfig  # noqa: E402


class TestMCPConfigDefaults:
    def test_defaults(self) -> None:
        config = MCPConfig()
        assert config.transport == "stdio"
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.server_name == "openchronicle"

    def test_from_env_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            # Remove any OC_MCP_ env vars that might exist
            for key in list(os.environ):
                if key.startswith("OC_MCP_"):
                    del os.environ[key]
            config = MCPConfig.from_env()
        assert config.transport == "stdio"
        assert config.host == "127.0.0.1"
        assert config.port == 8080


class TestMCPConfigEnvPrecedence:
    def test_env_overrides_file_config(self) -> None:
        file_config = {"transport": "sse", "host": "0.0.0.0", "port": 9090}
        with patch.dict(os.environ, {"OC_MCP_TRANSPORT": "stdio", "OC_MCP_HOST": "localhost", "OC_MCP_PORT": "7070"}):
            config = MCPConfig.from_env(file_config=file_config)
        assert config.transport == "stdio"
        assert config.host == "localhost"
        assert config.port == 7070

    def test_file_config_used_when_no_env(self) -> None:
        file_config = {"transport": "sse", "host": "0.0.0.0", "port": 9090}
        env = {k: v for k, v in os.environ.items() if not k.startswith("OC_MCP_")}
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env(file_config=file_config)
        assert config.transport == "sse"
        assert config.host == "0.0.0.0"
        assert config.port == 9090


class TestMCPConfigValidation:
    def test_invalid_transport_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid MCP transport"):
            MCPConfig.from_env(file_config={"transport": "websocket"})

    def test_valid_transports(self) -> None:
        for transport in ("stdio", "sse", "streamable-http"):
            config = MCPConfig.from_env(file_config={"transport": transport})
            assert config.transport == transport

    def test_server_name_from_file_config(self) -> None:
        config = MCPConfig.from_env(file_config={"server_name": "my-oc"})
        assert config.server_name == "my-oc"


class TestMCPConfigAllowedHosts:
    """OC_MCP_ALLOWED_HOSTS controls FastMCP's Host-header allowlist.

    Added 2026-05-06 after a post-cutover discovery: FastMCP's transport
    security defaults reject any non-loopback Host header with a 421,
    silently breaking every documented LAN client config. The new env
    var lets operators extend the allowlist without source changes.
    """

    def _clean_env(self) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if not k.startswith("OC_MCP_")}

    def test_default_allowed_hosts_is_localhost_only(self) -> None:
        with patch.dict(os.environ, self._clean_env(), clear=True):
            config = MCPConfig.from_env()
        assert config.allowed_hosts == ("127.0.0.1:*", "localhost:*", "[::1]:*")

    def test_env_var_csv_replaces_default(self) -> None:
        env = self._clean_env()
        env["OC_MCP_ALLOWED_HOSTS"] = "carldog-nas:*,carldog-nas.local:*"
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env()
        # Caller-supplied list fully replaces the default — operator's job
        # to include localhost variants if they want them.
        assert config.allowed_hosts == ("carldog-nas:*", "carldog-nas.local:*")

    def test_env_var_strips_whitespace_and_drops_empty(self) -> None:
        env = self._clean_env()
        env["OC_MCP_ALLOWED_HOSTS"] = "  carldog-nas:*  , , localhost:* "
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env()
        assert config.allowed_hosts == ("carldog-nas:*", "localhost:*")

    def test_empty_env_var_falls_back_to_default(self) -> None:
        env = self._clean_env()
        env["OC_MCP_ALLOWED_HOSTS"] = ""
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env()
        assert config.allowed_hosts == ("127.0.0.1:*", "localhost:*", "[::1]:*")

    def test_file_config_used_when_no_env(self) -> None:
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env(
                file_config={"allowed_hosts": ["carldog-nas:*", "tailscale-host:*"]},
            )
        assert config.allowed_hosts == ("carldog-nas:*", "tailscale-host:*")

    def test_env_var_overrides_file_config(self) -> None:
        env = self._clean_env()
        env["OC_MCP_ALLOWED_HOSTS"] = "from-env:*"
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env(
                file_config={"allowed_hosts": ["from-file:*"]},
            )
        assert config.allowed_hosts == ("from-env:*",)

    def test_file_config_invalid_shape_falls_back_to_default(self) -> None:
        # If someone puts a string instead of a list in core.json, don't
        # crash — fall through to the default.
        env = self._clean_env()
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env(file_config={"allowed_hosts": "not-a-list"})
        assert config.allowed_hosts == ("127.0.0.1:*", "localhost:*", "[::1]:*")
