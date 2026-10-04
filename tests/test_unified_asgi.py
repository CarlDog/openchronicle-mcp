"""Tests for the unified FastAPI + FastMCP ASGI app (Phase 6)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from openchronicle.interfaces.api.app import create_app
from openchronicle.interfaces.api.config import HTTPConfig

# Real filesystem paths for the mocked container: a MagicMock db_path
# used to leak literal `MagicMock/...` directories into the repo root
# when lifespan-driven maintenance jobs ran (papered over in .gitignore
# for a while), and the maintenance state file needs a real location.
_TMP = tempfile.TemporaryDirectory(prefix="oc-test-asgi-")


def _mock_container() -> MagicMock:
    container = MagicMock()
    container.file_configs = {}
    container.paths.db_path = Path(_TMP.name) / "data" / "openchronicle.db"
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


_MCP_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "routing-test", "version": "1"},
    },
}
_MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
def test_mcp_endpoint_is_served_at_both_paths_without_a_redirect(path: str) -> None:
    """The MCP spec's endpoint form and every documented client URL is
    exactly /mcp. A Mount alone answered it with a 307 to /mcp/, an extra
    round trip per request (QUAL-26). Both forms must reach the transport
    directly: a 200 carrying the initialize result, never a redirect. (OC
    serves MCP statelessly, so there is no session id to check.)"""
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    # An allowed Host: the transport's DNS-rebinding guard answers the
    # TestClient default ("testserver") with 421 before routing matters.
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        resp = client.post(path, json=_MCP_INIT, headers=_MCP_HEADERS, follow_redirects=False)
    assert resp.status_code == 200, f"POST {path} returned {resp.status_code}, expected the transport's 200"
    assert '"serverInfo"' in resp.text, f"POST {path} did not return an initialize result: {resp.text[:200]}"


@pytest.mark.parametrize("path", ["/mcp", "/mcp/"])
def test_mcp_get_reaches_the_transport_without_a_redirect(path: str) -> None:
    """GET (the SSE method) must not be redirected either. A GET that does not
    accept text/event-stream is refused by the transport itself with 406 and a
    JSON-RPC error; asserting that proves the request reached the transport
    without opening an endless SSE stream in the test."""
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        resp = client.get(path, headers={"Accept": "application/json"}, follow_redirects=False)
    assert resp.status_code == 406, f"GET {path} returned {resp.status_code}, expected the transport's 406"
    assert '"jsonrpc"' in resp.text


def test_mount_mcp_false_skips_mcp_route() -> None:
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=False)
    with TestClient(app) as client:
        resp = client.get("/mcp")
    # Without the MCP mount, /mcp is a real 404 from FastAPI's router.
    assert resp.status_code == 404


def test_mcp_post_initialize_hits_transport_at_slash_mcp() -> None:
    """Regression test for the path-doubling bug discovered 2026-05-06.

    FastMCP's streamable-HTTP app defaults to handling ``/mcp`` internally.
    Mounting that at ``/mcp`` on the host without overriding
    ``streamable_http_path`` causes the real endpoint to land at /mcp/mcp,
    silently breaking every documented client config (which expects
    ``/mcp``). The fix sets ``streamable_http_path="/"`` so the inner app
    handles its own root; the host mount path becomes the full URL.

    This test POSTs an MCP initialize request to /mcp/ and asserts the
    response is something other than a FastAPI 404 — i.e. the request
    actually reached the transport. We don't assert on a specific success
    body because the SSE/streamable transport returns flow control that's
    not trivial to assert on with a sync TestClient; the goal is "did we
    hit FastMCP at all."
    """
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "regression-test", "version": "1"},
        },
    }
    with TestClient(app) as client:
        resp = client.post(
            "/mcp/",
            json=init_req,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
    # If the path-doubling bug regresses, this returns 404 (FastAPI router
    # rejects /mcp/ because nothing's mounted there at the inner app's
    # root). Anything 2xx or even a transport-level 4xx like 406 means the
    # request reached FastMCP — that's the regression signal we want.
    assert resp.status_code != 404, (
        "path-doubling regression: POST /mcp/ returned 404, indicating "
        "FastMCP isn't handling its mount root. Check streamable_http_path."
    )


def test_mcp_requests_log_no_lifespan_lines_at_info(caplog: pytest.LogCaptureFixture) -> None:
    """Stateless streamable-HTTP runs FastMCP's lifespan once per request.

    Its "starting"/"shutting down" pair therefore went into OC_LOG_FILE at
    INFO on every MCP call (design 0014 Part 4). They are DEBUG now; the
    once-per-process startup lines live in the ASGI lifespan and the stdio
    entrypoint.
    """
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    with TestClient(app) as client, caplog.at_level(logging.DEBUG, logger="openchronicle.interfaces.mcp.server"):
        for n in range(3):
            client.post(
                "/mcp/",
                json={
                    "jsonrpc": "2.0",
                    "id": n,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "log-test", "version": "1"},
                    },
                },
                headers=headers,
            )
    lifespan = [
        r for r in caplog.records if r.name == "openchronicle.interfaces.mcp.server" and "MCP server" in r.getMessage()
    ]
    starts = [r for r in lifespan if "starting" in r.getMessage()]
    assert len(starts) >= 3, "premise: the lifespan runs once per request"
    assert [r.levelname for r in lifespan if r.levelno != logging.DEBUG] == []


def test_stdio_entrypoint_logs_one_startup_line_and_keeps_stdout_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The stdio server's only INFO startup line, now that the lifespan's is DEBUG."""
    from openchronicle.interfaces.mcp import __main__ as entry

    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "stdio.db"))
    monkeypatch.delenv("OC_MCP_TRANSPORT", raising=False)
    server = MagicMock()
    monkeypatch.setattr("openchronicle.interfaces.mcp.server.create_server", lambda _c, _cfg: server)

    with caplog.at_level(logging.INFO, logger=entry.__name__):
        entry.main()

    server.run.assert_called_once_with(transport="stdio")
    assert [r.getMessage() for r in caplog.records if r.name == entry.__name__] == [
        "OpenChronicle MCP server starting (stdio transport)"
    ]
    assert capsys.readouterr().out == "", "stdout belongs to the stdio protocol"


def test_stdio_startup_line_goes_to_stderr_with_production_logging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Under pytest the root logger already has handlers, which makes the
    entrypoint's logging.basicConfig a no-op, so the test above cannot see
    which stream the line takes. Here the root logger starts empty, as in
    production (test-honesty review)."""
    from openchronicle.interfaces.mcp import __main__ as entry

    monkeypatch.setenv("OC_DB_PATH", str(tmp_path / "stdio.db"))
    monkeypatch.delenv("OC_MCP_TRANSPORT", raising=False)
    monkeypatch.setattr("openchronicle.interfaces.mcp.server.create_server", lambda _c, _cfg: MagicMock())
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    root.handlers.clear()
    try:
        entry.main()
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        root.handlers.extend(saved_handlers)
        root.setLevel(saved_level)

    captured = capsys.readouterr()
    assert "OpenChronicle MCP server starting (stdio transport)" in captured.err
    assert captured.out == "", "stdout belongs to the stdio protocol"


def test_mcp_post_at_doubled_path_does_not_work() -> None:
    """Companion to the regression test above: /mcp/mcp/ should NOT be the
    real endpoint. If a future change accidentally drops streamable_http_path,
    the doubled path would start working and the single path would 404.
    """
    app = create_app(_mock_container(), HTTPConfig(), mount_mcp=True)
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "regression-test", "version": "1"},
        },
    }
    with TestClient(app) as client:
        resp = client.post(
            "/mcp/mcp/",
            json=init_req,
            headers={
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            },
        )
    # The doubled path should be a clean 404 (no transport at this URL).
    assert resp.status_code == 404, (
        f"unexpected response at /mcp/mcp/: {resp.status_code}. If non-404, the path-doubling bug may have re-emerged."
    )


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
    assert formatter_cls == "_RedactingFormatter"  # the human format, redacting (QUAL-12)


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
    assert type(handler.formatter).__name__ == "_RedactingFormatter"
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
