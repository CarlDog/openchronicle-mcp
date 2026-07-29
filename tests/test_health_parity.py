"""The MCP `health` tool and the REST /health route must agree.

They drifted before: REST appended `maintenance_degraded` after building
the payload, so the MCP tool was strictly poorer and nobody noticed. Both
now fill the same fields on `DiagnosticsReport`, and the key-set test
below is what keeps that true — it fails the moment one surface learns
something the other doesn't.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from openchronicle.interfaces.api.config import HTTPConfig
from openchronicle.version import DISTRIBUTION_NAME, package_version

mcp_mod = pytest.importorskip("mcp")  # noqa: F841


@pytest.fixture()
def store(tmp_path: Path) -> SqliteStore:
    s = SqliteStore(str(tmp_path / "oc.db"))
    s.init_schema()
    return s


def _container(store: SqliteStore) -> MagicMock:
    container = MagicMock()
    container.file_configs = {}
    container.storage = store
    container.embedding_service = None
    container.embedding_status_dict.return_value = {"status": "disabled", "provider": "none"}
    container.maintenance_degraded = False
    return container


def _mcp_health(container: MagicMock) -> dict[str, Any]:
    from mcp.server.fastmcp import FastMCP

    from openchronicle.interfaces.mcp.tools.system import register

    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"container": container}
    mcp = FastMCP("test")
    register(mcp)
    result = asyncio.run(mcp._tool_manager._tools["health"].fn(ctx=ctx))
    return dict(result)


def _rest_health(container: MagicMock) -> dict[str, Any]:
    from openchronicle.interfaces.api.app import create_app

    client = TestClient(create_app(container, HTTPConfig()))
    return dict(client.get("/api/v1/health").json())


class TestHealthParity:
    def test_mcp_and_rest_return_identical_key_sets(self, store: SqliteStore) -> None:
        container = _container(store)
        assert set(_mcp_health(container)) == set(_rest_health(container))


class TestHealthFields:
    def test_reports_package_version(self, store: SqliteStore) -> None:
        assert _mcp_health(_container(store))["package_version"] == package_version()

    def test_package_version_resolves_the_real_distribution(self) -> None:
        """The guard for a bug that shipped and stayed invisible.

        `oc version` asked importlib.metadata for "openchronicle" while
        the distribution is "openchronicle-mcp", so it always printed
        "unknown". The old test only asserted the substring
        "openchronicle" appeared in the output, which the failure string
        satisfied.
        """
        assert DISTRIBUTION_NAME == "openchronicle-mcp"
        assert package_version() != "unknown"

    def test_reports_schema_version(self, store: SqliteStore) -> None:
        assert _mcp_health(_container(store))["schema_version"] == store.schema_version()

    def test_reports_maintenance_degraded(self, store: SqliteStore) -> None:
        container = _container(store)
        container.maintenance_degraded = True
        assert _mcp_health(container)["maintenance_degraded"] is True

    def test_reports_fts5_active(self, store: SqliteStore) -> None:
        assert _mcp_health(_container(store))["fts5_active"] == store.fts5_active
