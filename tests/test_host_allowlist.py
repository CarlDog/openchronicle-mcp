"""Host-allowlist middleware tests — DNS-rebinding defense on the REST surface.

Regression context (2026-08-15 review): the rc2 DNS-rebinding fix covered
only the mounted /mcp app (FastMCP TransportSecuritySettings); the REST
surface had no Host validation at all, so with auth disabled a rebinding
page could read memories and call bulk-delete. These tests pin the REST
guard, its always-allowed loopback set, and the env fallback that lets one
stack variable protect both surfaces.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

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
