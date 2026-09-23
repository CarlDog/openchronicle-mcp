"""Host-allowlist middleware tests — DNS-rebinding defense on the REST surface.

Regression context (2026-08-15 review): the rc2 DNS-rebinding fix covered
only the mounted /mcp app (FastMCP TransportSecuritySettings); the REST
surface had no Host validation at all, so with auth disabled a rebinding
page could read memories and call bulk-delete. These tests pin the REST
guard, its always-allowed loopback set, and the env fallback that lets one
stack variable protect both surfaces.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from openchronicle.core.infrastructure.observability.prometheus_recorder import PrometheusMetricsRecorder
from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig
from openchronicle.interfaces.api.middleware.host_allowlist import host_allowed
from openchronicle.interfaces.mcp.config import DEFAULT_ALLOWED_HOSTS


def _client(config: HTTPConfig | None = None, base_url: str = "http://testserver") -> TestClient:
    container = MagicMock()
    container.file_configs = {}
    app = create_app(container, config or HTTPConfig())
    return TestClient(app, base_url=base_url)


class TestHostAllowed:
    def test_exact_match(self) -> None:
        assert host_allowed("nas:18000", ("nas:18000",))

    def test_port_wildcard(self) -> None:
        assert host_allowed("nas:18000", ("nas:*",))

    def test_bare_host_matches_wildcard(self) -> None:
        """Browsers omit default ports from Host; ':*' must cover that."""
        assert host_allowed("nas", ("nas:*",))

    def test_unlisted_host_rejected(self) -> None:
        assert not host_allowed("evil.example:18000", ("nas:*",))

    def test_missing_host_rejected(self) -> None:
        assert not host_allowed(None, ("nas:*",))
        assert not host_allowed("", ("nas:*",))

    def test_wildcard_is_not_a_prefix_match(self) -> None:
        """'nas:*' must not match 'nas.evil.example' — only 'nas[:port]'."""
        assert not host_allowed("nas.evil.example:80", ("nas:*",))


class TestRestSurface:
    def test_default_config_allows_test_client(self) -> None:
        with _client() as client:
            assert client.get("/health").status_code == 200

    def test_unlisted_host_gets_421(self) -> None:
        with _client(base_url="http://evil.example:8000") as client:
            resp = client.get("/api/v1/health")
        assert resp.status_code == 421
        assert resp.json()["code"] == "INVALID_HOST"

    def test_configured_host_is_allowed(self) -> None:
        cfg = HTTPConfig(allowed_hosts=("evil.example:*",))
        with _client(cfg, base_url="http://evil.example:8000") as client:
            assert client.get("/health").status_code == 200

    def test_loopback_always_allowed_alongside_operator_allowlist(self) -> None:
        """An operator allowlist REPLACES the localhost defaults on the MCP
        side; the REST guard must keep loopback working regardless — the
        Docker HEALTHCHECK probes /health as localhost from inside the
        container no matter what the stack env says.
        """
        cfg = HTTPConfig(allowed_hosts=("nas:*",))
        with _client(cfg, base_url="http://localhost:8000") as client:
            assert client.get("/health").status_code == 200

    def test_mcp_path_is_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """/mcp belongs to FastMCP's own transport security. A host that the
        MCP allowlist accepts but the REST allowlist does not must still
        reach the mount (anything but our 421-with-code envelope).
        """
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", "specialhost:*")
        cfg = HTTPConfig()  # REST allowlist: loopback defaults only
        with _client(cfg, base_url="http://specialhost:8000") as client:
            rest = client.get("/api/v1/health")
            mcp = client.get("/mcp/")
        assert rest.status_code == 421  # REST guard active for this host
        assert mcp.status_code != 421  # /mcp passed through to FastMCP


class TestHTTPConfigAllowedHosts:
    def test_api_var_wins_over_mcp_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_API_ALLOWED_HOSTS", "api-host:*")
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", "mcp-host:*")
        assert HTTPConfig.from_env().allowed_hosts == ("api-host:*",)

    def test_falls_back_to_mcp_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One Portainer stack variable protects both surfaces."""
        monkeypatch.delenv("OC_API_ALLOWED_HOSTS", raising=False)
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", "mcp-host:*")
        assert HTTPConfig.from_env().allowed_hosts == ("mcp-host:*",)

    def test_default_is_loopback_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OC_API_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("OC_MCP_ALLOWED_HOSTS", raising=False)
        assert HTTPConfig.from_env().allowed_hosts == DEFAULT_ALLOWED_HOSTS

    def test_empty_string_env_treated_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Compose injects "" via ${VAR:-}; that must not clear the fallback
        chain (same convention as the MCP-side allowlist parsing).
        """
        monkeypatch.setenv("OC_API_ALLOWED_HOSTS", "")
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", "mcp-host:*")
        assert HTTPConfig.from_env().allowed_hosts == ("mcp-host:*",)


class TestNasComposeAllowlist:
    """Exercise the Host-header behavior of the NAS compose env values."""

    @pytest.mark.parametrize(
        ("api_override", "collector_status"),
        [(None, 421), ("your-nas:*,oc:*", 200)],
        ids=("api-falls-back-to-mcp", "explicit-api-adds-collector"),
    )
    def test_rendered_compose_hosts_reach_runtime(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        api_override: str | None,
        collector_status: int,
    ) -> None:
        """Render compose without a daemon, then use its actual container env."""
        docker = shutil.which("docker")
        if docker is None:
            pytest.skip("Docker Compose CLI is unavailable")

        docker_config = tmp_path / "docker-config"
        docker_config.mkdir()
        # Docker Desktop keeps its bundled Compose plugin beside the CLI,
        # but a clean DOCKER_CONFIG hides that discovery path on Windows.
        plugin_dir = Path(docker).parent.parent / "cli-plugins"
        if plugin_dir.is_dir():
            (docker_config / "config.json").write_text(
                json.dumps({"cliPluginsExtraDirs": [str(plugin_dir)]}), encoding="utf-8"
            )
        env = {
            "PATH": os.environ.get("PATH", ""),
            "DOCKER_CONFIG": str(docker_config),
            "OC_TAG": "v3.3.0",
            "OC_MCP_ALLOWED_HOSTS": "your-nas:*",
            "OC_METRICS_ENABLED": "true",
        }
        for name in ("SystemRoot", "WINDIR", "PATHEXT"):
            if value := os.environ.get(name):
                env[name] = value
        if api_override is not None:
            env["OC_API_ALLOWED_HOSTS"] = api_override

        version = subprocess.run([docker, "compose", "version"], capture_output=True, text=True, env=env, timeout=10)
        if version.returncode != 0:
            pytest.skip("Docker Compose CLI is unavailable")

        compose_path = Path(__file__).parents[1] / "docker-compose.nas.yml"
        result = subprocess.run(
            [docker, "compose", "-f", str(compose_path), "config", "--format", "json"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        assert result.returncode == 0, "Docker Compose could not render the NAS file"
        rendered_env = json.loads(result.stdout)["services"]["oc"]["environment"]
        assert rendered_env["OC_MCP_ALLOWED_HOSTS"] == "your-nas:*"
        assert rendered_env["OC_API_ALLOWED_HOSTS"] == (api_override or "")

        monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
        monkeypatch.delenv("OC_API_KEY", raising=False)
        monkeypatch.setenv("OC_API_ALLOWED_HOSTS", rendered_env["OC_API_ALLOWED_HOSTS"])
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", rendered_env["OC_MCP_ALLOWED_HOSTS"])
        config = HTTPConfig.from_env()

        recorder = PrometheusMetricsRecorder()
        container = MagicMock()
        container.file_configs = {}
        container.metrics = recorder
        container.metrics_exporter = recorder
        app = create_app(container, config, mount_mcp=True)
        with TestClient(app, base_url="http://your-nas:18000") as client:
            assert client.get("/api/v1/maintenance/status").status_code == 200
            assert client.get("/metrics", headers={"Host": "oc:8000"}).status_code == collector_status
            assert client.get("/metrics", headers={"Host": "evil.example:18000"}).status_code == 421

    def test_empty_api_value_inherits_mcp_host_on_both_surfaces(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
        monkeypatch.delenv("OC_API_KEY", raising=False)
        monkeypatch.setenv("OC_API_ALLOWED_HOSTS", "")
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", "your-nas:*")
        config = HTTPConfig.from_env()
        assert config.allowed_hosts == ("your-nas:*",)

        container = MagicMock()
        container.file_configs = {}
        app = create_app(container, config, mount_mcp=True)
        with TestClient(app, base_url="http://your-nas:18000") as client:
            assert client.get("/health").status_code == 200
            assert client.get("/api/v1/maintenance/status").status_code == 200
            mcp_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
            assert client.post("/mcp/", json=mcp_request).status_code != 421

            # The collector alias is a separate opt-in REST Host, not a
            # side effect of the LAN host or a new MCP allowance.
            assert client.get("/metrics", headers={"Host": "oc:8000"}).status_code == 421
            assert client.get("/api/v1/maintenance/status", headers={"Host": "evil.example:18000"}).status_code == 421
            assert client.post("/mcp/", json=mcp_request, headers={"Host": "evil.example:18000"}).status_code == 421

    def test_explicit_api_value_retains_lan_and_adds_collector_only_for_rest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OC_MAINTENANCE_DISABLED", "1")
        monkeypatch.delenv("OC_API_KEY", raising=False)
        monkeypatch.setenv("OC_API_ALLOWED_HOSTS", "your-nas:*,oc:*")
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", "your-nas:*")
        config = HTTPConfig.from_env()
        assert config.allowed_hosts == ("your-nas:*", "oc:*")

        recorder = PrometheusMetricsRecorder()
        container = MagicMock()
        container.file_configs = {}
        container.metrics = recorder
        container.metrics_exporter = recorder
        app = create_app(container, config, mount_mcp=True)
        with TestClient(app, base_url="http://your-nas:18000") as client:
            assert client.get("/api/v1/maintenance/status").status_code == 200
            assert client.get("/metrics", headers={"Host": "oc:8000"}).status_code == 200
            assert client.get("/metrics", headers={"Host": "evil.example:18000"}).status_code == 421

            mcp_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
            assert client.post("/mcp/", json=mcp_request).status_code != 421
            assert client.post("/mcp/", json=mcp_request, headers={"Host": "oc:8000"}).status_code == 421


class TestMcpSurfaceRejectsForgedHost:
    """The /mcp guard itself — the half nothing asserted until 2026-08-28.

    `test_mcp_path_bypasses_rest_guard` above proves /mcp is deliberately
    EXEMPT from the REST middleware, because FastMCP runs its own
    TransportSecuritySettings guard. But nothing proved that guard actually
    rejects anything. The config tests only check that the allowlist
    PARSES; the bypass test only checks the REST guard stays out of the way.

    So the DNS-rebinding defense on the MCP surface — the one configured in
    production via OC_MCP_ALLOWED_HOSTS — was load-bearing and untested.

    Measured, not assumed. Two mutations, two different outcomes:

    - REMOVING `transport_security=` is already caught, by
      `test_mcp_path_is_skipped` above. FastMCP then falls back to a
      localhost-only default, so an allowlisted host starts getting 421 —
      an availability regression, loud by accident.
    - Setting `enable_dns_rebinding_protection=False` — the real
      off-switch, and what a careless migration or a "stop the 421s"
      change would reach for — leaves the ENTIRE suite green at 681
      passed. The forged Host then reaches the transport with a 406.
      Only the first test below catches it.

    That asymmetry is the point: the existing coverage pins the permissive
    direction (an allowlisted host must work) and nothing pinned the
    rejecting direction. This is also the migration tripwire — the only
    test that would catch the control being silently lost in a future port
    off `mcp<2`.
    """

    def _mounted(self, monkeypatch: pytest.MonkeyPatch, allowed: str, base_url: str) -> TestClient:
        monkeypatch.setenv("OC_MCP_ALLOWED_HOSTS", allowed)
        container = MagicMock()
        container.file_configs = {}
        app = create_app(container, HTTPConfig(), mount_mcp=True)
        return TestClient(app, base_url=base_url)

    def test_forged_host_is_rejected_with_421(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A rebinding page resolving its own name to the container's IP."""
        with self._mounted(monkeypatch, "goodhost:*", "http://evil.example:18000") as client:
            resp = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})

        assert resp.status_code == 421, (
            f"forged Host reached the MCP transport (got {resp.status_code}). "
            "TransportSecuritySettings is not guarding /mcp."
        )

    def test_allowlisted_host_is_not_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The other half — a guard that rejects everything is equally broken."""
        with self._mounted(monkeypatch, "goodhost:*", "http://goodhost:18000") as client:
            resp = client.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})

        assert resp.status_code != 421, "an allowlisted Host must not be rejected"
