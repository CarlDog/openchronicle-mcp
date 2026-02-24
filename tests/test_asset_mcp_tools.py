"""Tests for asset MCP tools — upload, list, get, link."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

mcp_mod = pytest.importorskip("mcp")  # noqa: F841

from openchronicle.core.domain.exceptions import NotFoundError  # noqa: E402
from openchronicle.core.domain.models.asset import Asset, AssetLink  # noqa: E402

_NOW = datetime(2026, 2, 21, 12, 0, 0, tzinfo=UTC)


def _make_container() -> MagicMock:
    container = MagicMock()
    container.storage = MagicMock()
    container.event_logger = MagicMock()
    container.event_logger.append = MagicMock()
    container.asset_file_storage = MagicMock()
    return container


def _make_context(container: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"container": container}
    return ctx


def _sample_asset(**overrides: Any) -> Asset:
    defaults: dict[str, Any] = {
        "id": "asset-1",
        "project_id": "proj-1",
        "filename": "photo.png",
        "mime_type": "image/png",
        "file_path": "proj-1/asset-1.png",
        "size_bytes": 12345,
        "content_hash": "abc123",
        "metadata": {},
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return Asset(**defaults)


def _sample_link(**overrides: Any) -> AssetLink:
    defaults: dict[str, Any] = {
        "id": "link-1",
        "asset_id": "asset-1",
        "target_type": "conversation",
        "target_id": "convo-1",
        "role": "input",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return AssetLink(**defaults)


class TestAssetUpload:
    def test_upload_returns_asset(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.asset import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.asset.upload_asset.execute",
            return_value=(_sample_asset(), True),
        ):
            tool_fn = mcp._tool_manager._tools["asset_upload"].fn
            result = tool_fn(
                project_id="proj-1",
                source_path="/tmp/photo.png",
                ctx=ctx,
            )

        assert result["id"] == "asset-1"
        assert result["is_new"] is True
        assert result["filename"] == "photo.png"


class TestAssetList:
    def test_lists_assets(self) -> None:
        container = _make_container()
        ctx = _make_context(container)
        container.storage.list_assets.return_value = [
            _sample_asset(),
            _sample_asset(id="asset-2", content_hash="def456"),
        ]

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.asset import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["asset_list"].fn
        result = tool_fn(project_id="proj-1", ctx=ctx)

        assert len(result) == 2
        assert result[0]["id"] == "asset-1"


class TestAssetGet:
    def test_returns_asset_with_links(self) -> None:
        container = _make_container()
        ctx = _make_context(container)
        container.storage.get_asset.return_value = _sample_asset()
        container.storage.list_asset_links.return_value = [_sample_link()]

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.asset import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["asset_get"].fn
        result = tool_fn(asset_id="asset-1", ctx=ctx)

        assert result["id"] == "asset-1"
        assert len(result["links"]) == 1
        assert result["links"][0]["target_type"] == "conversation"

    def test_raises_for_missing(self) -> None:
        container = _make_container()
        ctx = _make_context(container)
        container.storage.get_asset.return_value = None

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.asset import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["asset_get"].fn
        with pytest.raises(NotFoundError, match="Asset not found"):
            tool_fn(asset_id="nope", ctx=ctx)


class TestAssetLink:
    def test_creates_link(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.asset import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.asset.link_asset.execute",
            return_value=_sample_link(),
        ):
            tool_fn = mcp._tool_manager._tools["asset_link"].fn
            result = tool_fn(
                asset_id="asset-1",
                target_type="conversation",
                target_id="convo-1",
                ctx=ctx,
            )

        assert result["id"] == "link-1"
        assert result["role"] == "input"
