"""Tests for the HTTP API interface.

Covers: config, middleware (auth, rate limiting), route handlers (happy + error
paths), and architectural posture (no core → interfaces/api imports).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.interfaces.api.config import HTTPConfig

_SRC_ROOT = Path(__file__).parent.parent / "src"
_FIXED_DT = datetime(2026, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Architectural posture
# ---------------------------------------------------------------------------


class TestHTTPAPIPosture:
    """Core must not import from interfaces.api or FastAPI/uvicorn.

    AST-scanned since 2026-08-17 (shared helper) — the local regex twin
    had the same column-0 blind spot the boundary guard did.
    """

    def test_core_has_no_fastapi_imports(self) -> None:
        from tests.helpers.import_scan import find_forbidden_imports

        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = find_forbidden_imports(core_path, ["fastapi", "uvicorn"], src_root=_SRC_ROOT)
        if violations:
            msg = "Core imports fastapi/uvicorn:\n" + "\n".join(f"  - {v}" for v in violations)
            raise AssertionError(msg)

    def test_core_has_no_interfaces_api_imports(self) -> None:
        from tests.helpers.import_scan import find_forbidden_imports

        core_path = _SRC_ROOT / "openchronicle" / "core"
        violations = find_forbidden_imports(core_path, ["openchronicle.interfaces.api"], src_root=_SRC_ROOT)
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
        project_id="proj-1",
        source="api",
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

    def test_get_project(self, client: TestClient) -> None:
        _get_container(client).storage.get_project.return_value = _make_project(name="alpha")
        resp = client.get("/api/v1/project/proj-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "proj-1"
        assert data["name"] == "alpha"

    def test_get_project_missing_returns_404(self, client: TestClient) -> None:
        _get_container(client).storage.get_project.return_value = None
        resp = client.get("/api/v1/project/nope")
        assert resp.status_code == 404

    def test_update_project_rename(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.update_project.return_value = _make_project(name="renamed")
        resp = client.put("/api/v1/project/proj-1", json={"name": "renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"
        storage.update_project.assert_called_once_with("proj-1", name="renamed", metadata=None)

    def test_update_project_metadata_only(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.update_project.return_value = _make_project()
        resp = client.put("/api/v1/project/proj-1", json={"metadata": {"team": "ops"}})
        assert resp.status_code == 200
        storage.update_project.assert_called_once_with("proj-1", name=None, metadata={"team": "ops"})

    def test_update_project_empty_body_rejected(self, client: TestClient) -> None:
        """At least one of name or metadata must be set — Pydantic guards this."""
        resp = client.put("/api/v1/project/proj-1", json={})
        assert resp.status_code == 422

    def test_update_project_missing_returns_404(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        _get_container(client).storage.update_project.side_effect = NotFoundError(
            "Project not found: nope", code="PROJECT_NOT_FOUND"
        )
        resp = client.put("/api/v1/project/nope", json={"name": "x"})
        assert resp.status_code == 404

    def test_delete_project_without_confirm_returns_422(self, client: TestClient) -> None:
        """Omitting `confirm` is a validation error, not a preview."""
        storage = _get_container(client).storage

        resp = client.delete("/api/v1/project/proj-1")
        assert resp.status_code == 422
        storage.delete_project.assert_not_called()

    def test_delete_project_confirm_false_returns_preview(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.get_project.return_value = _make_project(name="proj")
        storage.count_memory.return_value = 7

        resp = client.delete("/api/v1/project/proj-1?confirm=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {
            "status": "preview",
            "deleted": False,
            "next_step": ("Nothing was deleted. Call again with confirm=true to delete this project and its memories."),
            "project_id": "proj-1",
            "name": "proj",
            "memory_count": 7,
        }
        storage.delete_project.assert_not_called()

    def test_delete_project_confirm_calls_cascade(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.get_project.return_value = _make_project(name="proj")
        storage.delete_project.return_value = 3

        resp = client.delete("/api/v1/project/proj-1?confirm=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {
            "status": "ok",
            "deleted": True,
            "project_id": "proj-1",
            "name": "proj",
            "deleted_memories": 3,
        }
        storage.delete_project.assert_called_once_with("proj-1")
        storage.count_memory.assert_not_called()

    def test_delete_project_missing_returns_404(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.get_project.return_value = None

        resp = client.delete("/api/v1/project/nope?confirm=true")
        assert resp.status_code == 404
        storage.delete_project.assert_not_called()


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

    def test_memory_search_result_carries_relevance(self, client: TestClient) -> None:
        """Search-surface v2 (Q20): every hit explains itself via `relevance`."""
        _get_container(client).storage.search_memory.return_value = [_make_memory()]

        resp = client.get("/api/v1/memory/search", params={"query": "test"})
        assert resp.status_code == 200
        assert resp.json()[0]["relevance"] == {"channel": "keyword", "keyword_rank": 1}

    def test_memory_search_rejects_unknown_mode(self, client: TestClient) -> None:
        resp = client.get("/api/v1/memory/search", params={"query": "test", "mode": "cosmic"})
        assert resp.status_code == 422

    def test_memory_search_semantic_without_provider_is_422(self, client: TestClient) -> None:
        """mode=semantic on a keyword-only deployment is a caller error (422),
        not a silent keyword fallback — the explicit request is honored or
        refused loudly.
        """
        resp = client.get("/api/v1/memory/search", params={"query": "test", "mode": "semantic"})
        assert resp.status_code == 422
        assert "embedding provider" in resp.json()["detail"]

    def test_memory_search_phrase_reaches_the_store(self, client: TestClient) -> None:
        storage = _get_container(client).storage

        resp = client.get("/api/v1/memory/search", params={"query": "quick brown", "phrase": "true"})
        assert resp.status_code == 200
        assert storage.search_memory.call_args.kwargs["phrase"] is True

    def test_memory_search_provider_error_is_502(self, client: TestClient) -> None:
        """A provider failure under mode=semantic surfaces as 502 with the
        ProviderError's code and hint — not the generic 500.
        """
        from openchronicle.core.domain.exceptions import ProviderError

        service = MagicMock()
        service.search_semantic.side_effect = ProviderError("embedding provider timed out", hint="check OLLAMA_HOST")
        _get_container(client).embedding_service = service

        resp = client.get("/api/v1/memory/search", params={"query": "test", "mode": "semantic"})
        assert resp.status_code == 502
        body = resp.json()
        assert body["code"] == "PROVIDER_ERROR"
        assert body["hint"] == "check OLLAMA_HOST"

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

    def test_memory_save_400_no_project(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/memory",
            json={"content": "remember this"},
        )
        assert resp.status_code == 422

    def test_memory_pin(self, client: TestClient) -> None:
        resp = client.put("/api/v1/memory/mem-1/pin", json={"pinned": True})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_memory_delete_without_confirm_returns_422(self, client: TestClient) -> None:
        """Omitting `confirm` is a validation error, not a preview."""
        storage = _get_container(client).storage

        resp = client.delete("/api/v1/memory/mem-1")
        assert resp.status_code == 422
        storage.delete_memory.assert_not_called()

    def test_memory_delete_confirm_false_returns_preview(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.get_memory.return_value = _make_memory()

        resp = client.delete("/api/v1/memory/mem-1?confirm=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "preview"
        assert data["memory_id"] == "mem-1"
        assert data["content"] == "remember this"
        assert data["deleted"] is False
        assert data["next_step"]
        storage.delete_memory.assert_not_called()

    def test_memory_delete_confirm_calls_store(self, client: TestClient) -> None:
        storage = _get_container(client).storage

        resp = client.delete("/api/v1/memory/mem-1?confirm=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"status": "ok", "deleted": True, "memory_id": "mem-1"}
        storage.delete_memory.assert_called_once_with("mem-1")


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
            resp = client.delete("/api/v1/memory/x?confirm=false")
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

    def test_empty_query_rejected(self, client: TestClient) -> None:
        """Parity with MCP memory_search, which rejects empty queries.

        An empty query also silently returns nothing on the FTS5 path,
        so accepting it just produces a confusing empty result.
        """
        resp = client.get("/api/v1/memory/search", params={"query": ""})
        assert resp.status_code == 422

    def test_negative_top_k_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/v1/memory/search", params={"query": "test", "top_k": 0})
        assert resp.status_code == 422


class TestPathParamValidation:
    """Path parameters reject empty or overlength values."""

    def test_empty_memory_id_rejected(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/memory/{'x' * 201}")
        assert resp.status_code == 422


class TestProjectBulkDeleteRoute:
    def test_preview_reports_found_and_missing(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.get_project.side_effect = [_make_project(name="proj"), None]
        storage.count_memory.return_value = 4

        resp = client.post(
            "/api/v1/project/bulk-delete",
            json={"project_ids": ["proj-1", "nope"], "confirm": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is False
        assert data["missing"] == ["nope"]
        assert data["found"][0]["name"] == "proj"
        storage.delete_project.assert_not_called()

    def test_confirm_deletes(self, client: TestClient) -> None:
        storage = _get_container(client).storage
        storage.get_project.return_value = _make_project(name="proj")
        storage.delete_project.return_value = 2

        resp = client.post(
            "/api/v1/project/bulk-delete",
            json={"project_ids": ["proj-1"], "confirm": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["total_deleted_memories"] == 2

    def test_empty_list_is_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/project/bulk-delete", json={"project_ids": [], "confirm": True})
        assert resp.status_code == 422

    def test_missing_confirm_is_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/project/bulk-delete", json={"project_ids": ["proj-1"]})
        assert resp.status_code == 422


class TestConfigFailSoft:
    """Crash-loop guards (2026-08-15 review): one bad config value must
    degrade with a warning under restart: unless-stopped, not crash
    create_app into an indefinite restart loop.
    """

    def test_invalid_port_env_falls_back_to_default(self) -> None:
        with patch.dict("os.environ", {"OC_API_PORT": "not-a-port"}):
            assert HTTPConfig.from_env().port == 8000

    def test_invalid_port_env_falls_back_to_file_value(self) -> None:
        with patch.dict("os.environ", {"OC_API_PORT": "not-a-port"}):
            assert HTTPConfig.from_env(file_config={"port": 7777}).port == 7777

    def test_out_of_range_port_falls_back(self) -> None:
        with patch.dict("os.environ", {"OC_API_PORT": "99999"}):
            assert HTTPConfig.from_env().port == 8000

    def test_invalid_rate_limit_env_uses_default(self) -> None:
        from openchronicle.interfaces.api.middleware.rate_limit import (
            _DEFAULT_RPM,
            RateLimitMiddleware,
        )

        with patch.dict("os.environ", {"OC_API_RATE_LIMIT_RPM": "lots"}):
            middleware = RateLimitMiddleware(MagicMock())
        assert middleware._rpm == _DEFAULT_RPM


class TestMemoryEmbedRoute:
    """The ok/partial/failed mapping is duplicated per surface (MCP twin
    tested in test_mcp_handler_gaps); the 2026-05 'status=ok with
    generated=0' bug lived in exactly this shape.
    """

    def test_not_configured_when_service_absent(self, client: TestClient) -> None:
        _get_container(client).embedding_service = None
        resp = client.post("/api/v1/memory/embed")
        assert resp.status_code == 200
        assert resp.json()["status"] == "not_configured"

    def test_outcome_mapping_and_force_passthrough(self, client: TestClient) -> None:
        from openchronicle.core.application.services.embedding_service import BackfillResult

        service = MagicMock()
        service.generate_missing.return_value = BackfillResult(generated=3, failed=1, elapsed_ms=5)
        service.embedding_status.return_value = {"embedded": 3, "missing": 1}
        _get_container(client).embedding_service = service

        resp = client.post("/api/v1/memory/embed", json={"force": True})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "partial"
        assert data["generated"] == 3
        assert data["failed"] == 1
        assert data["force"] is True
        assert data["embedded"] == 3
        assert service.generate_missing.call_args.kwargs["force"] is True


class TestMemoryGetRoute:
    def test_happy_path(self, client: TestClient) -> None:
        _get_container(client).storage.get_memory.return_value = _make_memory()
        resp = client.get("/api/v1/memory/mem-1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "mem-1"
        assert resp.json()["content"] == "remember this"


class TestMemoryStatsRoute:
    def test_returns_totals(self, client: TestClient) -> None:
        container = _get_container(client)
        container.storage.count_memory.return_value = 2
        container.storage.list_memory.return_value = [_make_memory(), _make_memory()]
        resp = client.get("/api/v1/memory/stats")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2


class TestErrorShapeParity:
    """2026-08-15 review: caller mistakes answered 500 or an off-shape 404."""

    def test_bad_created_at_is_422_not_500(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/memory",
            json={"content": "x", "project_id": "proj-1", "created_at": "not-a-date"},
        )
        assert resp.status_code == 422
        assert "ISO 8601" in resp.text

    def test_memory_get_404_carries_code_field(self, client: TestClient) -> None:
        """This 404 used to be an inline HTTPException without the "code"
        key every sibling 404 carries via the global handler.
        """
        _get_container(client).storage.get_memory.return_value = None
        resp = client.get("/api/v1/memory/ghost")
        assert resp.status_code == 404
        assert resp.json()["code"] == "MEMORY_NOT_FOUND"
