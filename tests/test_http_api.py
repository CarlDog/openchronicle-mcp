"""Tests for the HTTP API interface.

Covers: config, middleware (auth, rate limiting), route handlers (happy + error
paths), and architectural posture (no core → interfaces/api imports).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from openchronicle.core.domain.models.asset import Asset, AssetLink
from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.interfaces.api.config import HTTPConfig

_SRC_ROOT = Path(__file__).parent.parent / "src"
_FIXED_DT = datetime(2026, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Architectural posture
# ---------------------------------------------------------------------------


def _scan_for_forbidden_imports(base_path: Path, forbidden: list[str]) -> list[str]:
    violations: list[str] = []
    for py_file in base_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        content = py_file.read_text(encoding="utf-8")
        rel = py_file.relative_to(_SRC_ROOT)
        for pattern in forbidden:
            if re.search(rf"^(?:from|import)\s+{re.escape(pattern)}", content, re.MULTILINE):
                violations.append(f"{rel}: imports {pattern}")
    return violations


class TestHTTPAPIPosture:
    """Core must not import from interfaces.api or FastAPI/uvicorn."""

    def test_core_has_no_fastapi_imports(self) -> None:
        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = _scan_for_forbidden_imports(core_path, ["fastapi", "uvicorn"])
        if violations:
            msg = "Core imports fastapi/uvicorn:\n" + "\n".join(f"  - {v}" for v in violations)
            raise AssertionError(msg)

    def test_core_has_no_interfaces_api_imports(self) -> None:
        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = _scan_for_forbidden_imports(
            core_path,
            ["openchronicle.interfaces.api"],
        )
        if violations:
            msg = "Core imports interfaces.api:\n" + "\n".join(f"  - {v}" for v in violations)
            raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestHTTPConfig:
    def test_defaults(self) -> None:
        config = HTTPConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.api_key is None

    def test_from_env_defaults(self) -> None:
        config = HTTPConfig.from_env()
        assert config.host == "127.0.0.1"
        assert config.port == 8000
        assert config.api_key is None

    def test_from_env_with_env_vars(self) -> None:
        with patch.dict("os.environ", {"OC_API_HOST": "0.0.0.0", "OC_API_PORT": "9000", "OC_API_KEY": "test-key"}):
            config = HTTPConfig.from_env()
            assert config.host == "0.0.0.0"
            assert config.port == 9000
            assert config.api_key == "test-key"

    def test_from_env_file_config_fallback(self) -> None:
        config = HTTPConfig.from_env(file_config={"host": "10.0.0.1", "port": 7777, "api_key": "file-key"})
        assert config.host == "10.0.0.1"
        assert config.port == 7777
        assert config.api_key == "file-key"

    def test_env_overrides_file_config(self) -> None:
        with patch.dict("os.environ", {"OC_API_PORT": "5555"}):
            config = HTTPConfig.from_env(file_config={"port": 7777})
            assert config.port == 5555

    def test_empty_api_key_is_none(self) -> None:
        config = HTTPConfig.from_env(file_config={"api_key": ""})
        assert config.api_key is None


# ---------------------------------------------------------------------------
# App factory + client fixtures
# ---------------------------------------------------------------------------


def _make_mock_container() -> MagicMock:
    """Build a minimal mock CoreContainer for route testing."""
    container = MagicMock()
    container.file_configs = {}

    # Storage mock — default return values for list operations
    container.storage = MagicMock()
    container.storage.get_mcp_tool_stats.return_value = []
    container.storage.get_moe_stats.return_value = []
    container.storage.list_conversations.return_value = []
    container.storage.list_assets.return_value = []
    container.storage.search_memory.return_value = []
    container.storage.list_memory.return_value = []
    container.storage.list_projects.return_value = []

    # Embedding service defaults to None (FTS5-only) unless test overrides
    container.embedding_service = None
    container.embedding_status_dict.return_value = {"status": "disabled", "provider": "none"}

    # Media port defaults to None unless test overrides
    container.media_port = None

    return container


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with no auth middleware."""
    from openchronicle.interfaces.api.app import create_app

    container = _make_mock_container()
    config = HTTPConfig()
    app = create_app(container, config)
    return TestClient(app)


@pytest.fixture()
def authed_client() -> TestClient:
    """Create a test client with API key auth enabled."""
    from openchronicle.interfaces.api.app import create_app

    container = _make_mock_container()
    config = HTTPConfig(api_key="test-secret-key")
    app = create_app(container, config)
    return TestClient(app)


def _get_container(client: TestClient) -> MagicMock:
    """Helper to access the mock container from a test client."""
    return client.app.state.container  # type: ignore[attr-defined, no-any-return]


# ---------------------------------------------------------------------------
# Test domain model factories
# ---------------------------------------------------------------------------


def _make_project(name: str = "test") -> Project:
    return Project(id="proj-1", name=name, metadata={}, created_at=_FIXED_DT)


def _make_memory(content: str = "remember this") -> MemoryItem:
    return MemoryItem(
        id="mem-1",
        content=content,
        tags=["test"],
        pinned=False,
        conversation_id=None,
        project_id="proj-1",
        source="api",
        created_at=_FIXED_DT,
    )


def _make_conversation(title: str = "test convo") -> Conversation:
    return Conversation(id="conv-1", project_id="proj-1", title=title, mode="general", created_at=_FIXED_DT)


def _make_turn(conversation_id: str = "conv-1") -> Turn:
    return Turn(
        id="turn-1",
        conversation_id=conversation_id,
        turn_index=0,
        user_text="hello",
        assistant_text="hi there",
        provider="stub",
        model="stub-model",
        routing_reasons=["default"],
        created_at=_FIXED_DT,
    )


def _make_asset() -> Asset:
    return Asset(
        id="asset-1",
        project_id="proj-1",
        filename="test.txt",
        mime_type="text/plain",
        file_path="/data/assets/abc123",
        size_bytes=42,
        content_hash="abc123",
        metadata={},
        created_at=_FIXED_DT,
    )


def _make_asset_link() -> AssetLink:
    return AssetLink(
        id="link-1",
        asset_id="asset-1",
        target_type="conversation",
        target_id="conv-1",
        role="reference",
        created_at=_FIXED_DT,
    )


# ---------------------------------------------------------------------------
# Middleware: auth
# ---------------------------------------------------------------------------


class TestAuthMiddleware:
    def test_health_is_public_even_with_auth(self, authed_client: TestClient) -> None:
        resp = authed_client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_docs_is_public_even_with_auth(self, authed_client: TestClient) -> None:
        resp = authed_client.get("/docs")
        assert resp.status_code == 200

    def test_authenticated_endpoint_requires_key(self, authed_client: TestClient) -> None:
        resp = authed_client.get("/api/v1/project")
        assert resp.status_code == 401

    def test_bearer_auth_works(self, authed_client: TestClient) -> None:
        resp = authed_client.get(
            "/api/v1/project",
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert resp.status_code == 200

    def test_x_api_key_header_works(self, authed_client: TestClient) -> None:
        resp = authed_client.get(
            "/api/v1/project",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert resp.status_code == 200

    def test_wrong_key_returns_403(self, authed_client: TestClient) -> None:
        resp = authed_client.get(
            "/api/v1/project",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 403

    def test_no_auth_middleware_when_key_unset(self, client: TestClient) -> None:
        """When no API key is configured, endpoints are open."""
        resp = client.get("/api/v1/project")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Middleware: rate limit
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers

    def test_rate_limit_enforced(self) -> None:
        """Verify 429 is returned when RPM limit is exceeded."""
        from openchronicle.interfaces.api.app import create_app

        container = _make_mock_container()
        config = HTTPConfig()

        with patch.dict("os.environ", {"OC_API_RATE_LIMIT_RPM": "3"}):
            app = create_app(container, config)
            tc = TestClient(app)

            for _ in range(3):
                resp = tc.get("/api/v1/health")
                assert resp.status_code == 200

            resp = tc.get("/api/v1/health")
            assert resp.status_code == 429
            assert "retry-after" in resp.headers

    def test_rate_limit_remaining_decrements(self, client: TestClient) -> None:
        """Remaining counter should decrease with each request."""
        resp1 = client.get("/api/v1/health")
        resp2 = client.get("/api/v1/health")
        remaining1 = int(resp1.headers["x-ratelimit-remaining"])
        remaining2 = int(resp2.headers["x-ratelimit-remaining"])
        assert remaining2 == remaining1 - 1


# ---------------------------------------------------------------------------
# Routes: system
# ---------------------------------------------------------------------------


class TestSystemRoutes:
    def test_health_returns_report(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "db_exists" in data

    def test_liveness_probe_returns_minimal_ok(self, client: TestClient) -> None:
        """Top-level /health is the liveness probe Synology/Docker/k8s hit.

        Returns immediately with no DB or diagnostic work — the full readiness
        endpoint stays at /api/v1/health. Regression guard for the noisy 404
        spam observed on the NAS deployment when external probers hit /health
        every ~5s.
        """
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_liveness_probe_is_public_even_with_auth(self, authed_client: TestClient) -> None:
        resp = authed_client.get("/health")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Routes: project
# ---------------------------------------------------------------------------


class TestProjectRoutes:
    def test_create_project(self, client: TestClient) -> None:
        resp = client.post("/api/v1/project", json={"name": "test"})
        assert resp.status_code == 200
        data = resp.json()
        # The slim use case constructs a Project; storage.add_project is a no-op mock
        assert data["name"] == "test"

    def test_list_projects(self, client: TestClient) -> None:
        _get_container(client).storage.list_projects.return_value = [_make_project()]

        resp = client.get("/api/v1/project")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_projects_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/project")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Routes: memory
# ---------------------------------------------------------------------------


class TestMemoryRoutes:
    def test_memory_search(self, client: TestClient) -> None:
        _get_container(client).storage.search_memory.return_value = [_make_memory()]

        resp = client.get("/api/v1/memory/search", params={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "remember this"

    def test_memory_search_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/memory/search", params={"query": "nothing"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_memory_list(self, client: TestClient) -> None:
        _get_container(client).storage.list_memory.return_value = [_make_memory()]

        resp = client.get("/api/v1/memory")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_memory_save_with_project_id(self, client: TestClient) -> None:
        saved = _make_memory()
        _get_container(client).storage.upsert_memory.return_value = saved

        resp = client.post(
            "/api/v1/memory",
            json={"content": "remember this", "project_id": "proj-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "remember this"

    def test_memory_save_derives_project_from_conversation(self, client: TestClient) -> None:
        convo = _make_conversation()
        _get_container(client).storage.get_conversation.return_value = convo
        saved = _make_memory()
        _get_container(client).storage.upsert_memory.return_value = saved

        resp = client.post(
            "/api/v1/memory",
            json={"content": "remember this", "conversation_id": "conv-1"},
        )
        assert resp.status_code == 200

    def test_memory_save_404_bad_conversation(self, client: TestClient) -> None:
        _get_container(client).storage.get_conversation.return_value = None

        resp = client.post(
            "/api/v1/memory",
            json={"content": "remember this", "conversation_id": "nonexistent"},
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_memory_save_400_no_project(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/memory",
            json={"content": "remember this"},
        )
        assert resp.status_code == 400
        assert "project_id is required" in resp.json()["detail"]

    def test_memory_pin(self, client: TestClient) -> None:
        resp = client.put("/api/v1/memory/mem-1/pin", json={"pinned": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Shared serializers
# ---------------------------------------------------------------------------


class TestSharedSerializers:
    """Verify the shared serializers module works correctly."""

    def test_project_to_dict(self) -> None:
        from openchronicle.interfaces.serializers import project_to_dict

        d = project_to_dict(_make_project())
        assert d["id"] == "proj-1"
        assert d["name"] == "test"
        assert d["created_at"] == _FIXED_DT.isoformat()

    def test_memory_to_dict(self) -> None:
        from openchronicle.interfaces.serializers import memory_to_dict

        d = memory_to_dict(_make_memory())
        assert d["id"] == "mem-1"
        assert d["tags"] == ["test"]
        assert d["source"] == "api"

    def test_turn_to_dict(self) -> None:
        from openchronicle.interfaces.serializers import turn_to_dict

        d = turn_to_dict(_make_turn())
        assert d["user_text"] == "hello"
        assert d["routing_reasons"] == ["default"]

    def test_asset_to_dict(self) -> None:
        from openchronicle.interfaces.serializers import asset_to_dict

        d = asset_to_dict(_make_asset())
        assert d["filename"] == "test.txt"
        assert d["size_bytes"] == 42

    def test_asset_link_to_dict(self) -> None:
        from openchronicle.interfaces.serializers import asset_link_to_dict

        d = asset_link_to_dict(_make_asset_link())
        assert d["target_type"] == "conversation"
        assert d["role"] == "reference"

    def test_conversation_to_dict(self) -> None:
        from openchronicle.interfaces.serializers import conversation_to_dict

        d = conversation_to_dict(_make_conversation())
        assert d["title"] == "test convo"
        assert d["mode"] == "general"


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


class TestGlobalExceptionHandlers:
    """Global handlers turn domain exceptions into correct HTTP codes."""

    def test_not_found_error_returns_404(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.memory.delete_memory.execute",
            side_effect=NotFoundError("Memory not found: x", code="MEMORY_NOT_FOUND"),
        ):
            resp = client.delete("/api/v1/memory/x")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "MEMORY_NOT_FOUND"
        assert "Memory not found" in body["detail"]

    def test_validation_error_returns_422(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import (
            ValidationError as DomainValidationError,
        )

        with patch(
            "openchronicle.interfaces.api.routes.memory.update_memory.execute",
            side_effect=DomainValidationError("At least one of content or tags must be provided"),
        ):
            resp = client.put("/api/v1/memory/m1", json={"content": None, "tags": None})
        assert resp.status_code == 422
        body = resp.json()
        assert body["code"] == "INVALID_ARGUMENT"
        assert "At least one" in body["detail"]

    def test_unhandled_exception_returns_500_sanitized(self, client: TestClient) -> None:
        # Must disable raise_server_exceptions so the global handler can run
        app = client.app
        no_raise_client = TestClient(app, raise_server_exceptions=False)
        with patch(
            "openchronicle.interfaces.api.routes.project.list_projects.execute",
            side_effect=RuntimeError("secret internal detail"),
        ):
            resp = no_raise_client.get("/api/v1/project")
        assert resp.status_code == 500
        body = resp.json()
        assert body["code"] == "INTERNAL_ERROR"
        assert body["detail"] == "Internal server error"
        assert "secret" not in body["detail"]


# ---------------------------------------------------------------------------
# Input validation (Pydantic Field constraints)
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Pydantic Field constraints reject bad input at the API boundary."""

    def test_empty_content_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/memory",
            json={"content": "", "project_id": "p1"},
        )
        assert resp.status_code == 422

    def test_content_too_long_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/memory",
            json={"content": "x" * 100_001, "project_id": "p1"},
        )
        assert resp.status_code == 422

    def test_empty_project_name_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/project", json={"name": ""})
        assert resp.status_code == 422

    def test_negative_offset_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/v1/memory/search", params={"query": "test", "offset": -1})
        assert resp.status_code == 422

    def test_negative_top_k_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/v1/memory/search", params={"query": "test", "top_k": 0})
        assert resp.status_code == 422


class TestPathParamValidation:
    """Path parameters reject empty or overlength values."""

    def test_empty_memory_id_rejected(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/memory/{'x' * 201}")
        assert resp.status_code == 422


