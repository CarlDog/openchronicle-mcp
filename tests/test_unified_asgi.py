"""Tests for the unified FastAPI + FastMCP ASGI app (Phase 6)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig


def _mock_container() -> MagicMock:
    container = MagicMock()
    container.file_configs = {}
    container.storage = MagicMock()
    container.storage.list_projects.return_value = []
    container.storage.list_memory.return_value = []
    container.storage.search_memory.return_value = []
    container.embedding_service = None
    container.embedding_status_dict.return_value = {"status": "disabled", "provider": "none"}
    return container


def test_unified_app_exposes_health() -> None:
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unified_app_exposes_api_routes() -> None:
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    with TestClient(app) as client:
        resp = client.get("/api/v1/project")
    assert resp.status_code == 200


def test_unified_app_mounts_mcp_under_slash_mcp() -> None:
    """The MCP transport is mounted at /mcp.

    A bare `GET /mcp` redirects to `GET /mcp/` (Starlette's mount-trailing-
    slash convention). That redirect itself proves the mount: an unmounted
    path would 404 from FastAPI's router instead.
    """
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    with TestClient(app) as client:
        resp = client.get("/mcp", follow_redirects=False)
    assert resp.status_code == 307, (
        f"expected redirect from /mcp → /mcp/ (mount sentinel), got {resp.status_code}"
    )
    assert resp.headers.get("location", "").endswith("/mcp/")


def test_mount_mcp_false_skips_mcp_route() -> None:
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=False)
    with TestClient(app) as client:
        resp = client.get("/mcp")
    # Without the MCP mount, /mcp is a real 404 from FastAPI's router.
    assert resp.status_code == 404


def test_log_format_default_is_human(monkeypatch: pytest.MonkeyPatch) -> None:
    """OC_LOG_FORMAT default is 'human' per the locked Q19 decision."""
    import logging

    from openchronicle.interfaces.logging_setup import configure_root_logger

    monkeypatch.delenv("OC_LOG_FORMAT", raising=False)
    monkeypatch.delenv("OC_LOG_LEVEL", raising=False)
    configure_root_logger()
    handler = logging.getLogger().handlers[0]
    formatter_cls = type(handler.formatter).__name__
    # Plain logging.Formatter, not _JsonFormatter
    assert formatter_cls == "Formatter"


def test_log_format_json_switches_formatter(monkeypatch: pytest.MonkeyPatch) -> None:
    import logging

    from openchronicle.interfaces.logging_setup import _JsonFormatter, configure_root_logger

    monkeypatch.setenv("OC_LOG_FORMAT", "json")
    configure_root_logger()
    handler = logging.getLogger().handlers[0]
    assert isinstance(handler.formatter, _JsonFormatter)
    # Reset so other tests aren't affected
    monkeypatch.setenv("OC_LOG_FORMAT", "human")
    configure_root_logger()


def test_log_format_invalid_falls_back_to_human(monkeypatch: pytest.MonkeyPatch) -> None:
    import logging

    monkeypatch.setenv("OC_LOG_FORMAT", "yaml")
    from openchronicle.interfaces.logging_setup import configure_root_logger

    configure_root_logger()
    handler = logging.getLogger().handlers[0]
    assert type(handler.formatter).__name__ == "Formatter"
    monkeypatch.delenv("OC_LOG_FORMAT", raising=False)
    configure_root_logger()


def test_json_formatter_serializes_records() -> None:
    import json
    import logging

    from openchronicle.interfaces.logging_setup import _JsonFormatter

    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    formatter = _JsonFormatter()
    out = formatter.format(record)
    parsed = json.loads(out)
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test.logger"
    assert parsed["message"] == "hello world"
    assert "ts" in parsed
