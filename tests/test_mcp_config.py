"""Tests for MCP server configuration."""

from __future__ import annotations

import logging
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

    @pytest.mark.parametrize("raw", ["0", "99999"])
    def test_out_of_range_env_port_falls_back(self, raw: str) -> None:
        """MCPConfig had no range check: OC_MCP_PORT=0 meant an ephemeral port
        on the standalone sse/streamable-http path (QUAL-23)."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("OC_MCP_")}
        env["OC_MCP_PORT"] = raw
        with patch.dict(os.environ, env, clear=True):
            assert MCPConfig.from_env().port == 8080
            assert MCPConfig.from_env(file_config={"port": 9090}).port == 9090

    def test_out_of_range_file_port_falls_back(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("OC_MCP_")}
        with patch.dict(os.environ, env, clear=True):
            assert MCPConfig.from_env(file_config={"port": 70000}).port == 8080

    def test_bad_port_warnings_name_oc_mcp_port_and_mcp_port(self, caplog: pytest.LogCaptureFixture) -> None:
        """The wiring: MCPConfig's warnings name its own env var and core.json
        key, not the API's (QUAL-23 review)."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("OC_MCP_")}
        env["OC_MCP_PORT"] = "99999"
        with patch.dict(os.environ, env, clear=True), caplog.at_level(logging.WARNING):
            assert MCPConfig.from_env(file_config={"port": 0}).port == 8080
        assert "Invalid core.json mcp.port 0 (must be 1-65535); using 8080" in caplog.text
        assert "Invalid OC_MCP_PORT='99999' (must be 1-65535); using 8080" in caplog.text

    def test_mounted_config_neither_reads_nor_warns_about_its_port(self, caplog: pytest.LogCaptureFixture) -> None:
        """Inside `oc serve` MCP listens on the API port, so its own port is
        not bound: no warning may claim it is "using 8080" (Copilot, #110)."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("OC_MCP_")}
        env["OC_MCP_PORT"] = "0"
        with patch.dict(os.environ, env, clear=True), caplog.at_level(logging.WARNING):
            config = MCPConfig.from_env(file_config={"port": 70000, "server_name": "x"}, binds_port=False)
        assert config.port == 8080
        assert config.server_name == "x"
        assert caplog.text == ""

    @pytest.mark.parametrize("value", [True, False])
    def test_boolean_port_in_file_config_falls_back_to_default(self, value: bool) -> None:
        """bool is an int subclass, so `"port": true` became port 1 and
        `"port": false` port 0 (an ephemeral port): MCPConfig had no range
        check before QUAL-23 to catch either. Both must fall back."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("OC_MCP_")}
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env(file_config={"port": value})
        assert config.port == 8080


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
        env["OC_MCP_ALLOWED_HOSTS"] = "test-host:*,test-host.local:*"
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env()
        # Caller-supplied list fully replaces the default — operator's job
        # to include localhost variants if they want them.
        assert config.allowed_hosts == ("test-host:*", "test-host.local:*")

    def test_env_var_strips_whitespace_and_drops_empty(self) -> None:
        env = self._clean_env()
        env["OC_MCP_ALLOWED_HOSTS"] = "  test-host:*  , , localhost:* "
        with patch.dict(os.environ, env, clear=True):
            config = MCPConfig.from_env()
        assert config.allowed_hosts == ("test-host:*", "localhost:*")

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
                file_config={"allowed_hosts": ["test-host:*", "tailscale-host:*"]},
            )
        assert config.allowed_hosts == ("test-host:*", "tailscale-host:*")

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
