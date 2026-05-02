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
    container.orchestrator.list_projects.return_value = []

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
        resp = authed_client.get("/api/v1/stats/tools")
        assert resp.status_code == 401

    def test_bearer_auth_works(self, authed_client: TestClient) -> None:
        resp = authed_client.get(
            "/api/v1/stats/tools",
            headers={"Authorization": "Bearer test-secret-key"},
        )
        assert resp.status_code == 200

    def test_x_api_key_header_works(self, authed_client: TestClient) -> None:
        resp = authed_client.get(
            "/api/v1/stats/tools",
            headers={"X-API-Key": "test-secret-key"},
        )
        assert resp.status_code == 200

    def test_wrong_key_returns_403(self, authed_client: TestClient) -> None:
        resp = authed_client.get(
            "/api/v1/stats/tools",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 403

    def test_no_auth_middleware_when_key_unset(self, client: TestClient) -> None:
        """When no API key is configured, endpoints are open."""
        resp = client.get("/api/v1/stats/tools")
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

    def test_tool_stats(self, client: TestClient) -> None:
        resp = client.get("/api/v1/stats/tools")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_moe_stats(self, client: TestClient) -> None:
        resp = client.get("/api/v1/stats/moe")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Routes: project
# ---------------------------------------------------------------------------


class TestProjectRoutes:
    def test_create_project(self, client: TestClient) -> None:
        project = _make_project()
        _get_container(client).orchestrator.create_project.return_value = project

        resp = client.post("/api/v1/project", json={"name": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "proj-1"
        assert data["name"] == "test"
        assert data["created_at"] == _FIXED_DT.isoformat()

    def test_list_projects(self, client: TestClient) -> None:
        # list_projects use case calls orchestrator.storage.list_projects()
        _get_container(client).orchestrator.storage.list_projects.return_value = [_make_project()]

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
# Routes: conversation
# ---------------------------------------------------------------------------


class TestConversationRoutes:
    def test_conversation_create(self, client: TestClient) -> None:
        convo = _make_conversation()
        container = _get_container(client)
        container.storage.get_default_project.return_value = _make_project()
        container.storage.create_conversation.return_value = convo

        resp = client.post("/api/v1/conversation", json={"title": "test convo"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "test convo"

    def test_conversation_list(self, client: TestClient) -> None:
        _get_container(client).storage.list_conversations.return_value = [_make_conversation()]

        resp = client.get("/api/v1/conversation")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_conversation_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/conversation")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_conversation_history(self, client: TestClient) -> None:
        convo = _make_conversation()
        turn = _make_turn()
        _get_container(client).storage.get_conversation.return_value = convo
        _get_container(client).storage.list_turns.return_value = [turn]

        resp = client.get("/api/v1/conversation/conv-1/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation"]["id"] == "conv-1"
        assert len(data["turns"]) == 1
        assert data["turns"][0]["user_text"] == "hello"

    def test_conversation_ask(self, client: TestClient) -> None:
        turn = _make_turn()
        # ask_conversation.execute is async — mock it as AsyncMock
        with patch(
            "openchronicle.interfaces.api.routes.conversation.ask_conversation.execute",
            new_callable=AsyncMock,
            return_value=turn,
        ):
            resp = client.post(
                "/api/v1/conversation/conv-1/ask",
                json={"prompt": "hello"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["assistant_text"] == "hi there"
        assert data["provider"] == "stub"

    def test_context_recent(self, client: TestClient) -> None:
        convo = _make_conversation()
        turn = _make_turn()
        container = _get_container(client)
        container.storage.get_conversation.return_value = convo
        container.storage.list_turns.return_value = [turn]

        resp = client.get("/api/v1/conversation/conv-1/context")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation"]["id"] == "conv-1"
        assert len(data["recent_turns"]) == 1

    def test_context_recent_with_memory_query(self, client: TestClient) -> None:
        convo = _make_conversation()
        container = _get_container(client)
        container.storage.get_conversation.return_value = convo
        container.storage.list_turns.return_value = []
        container.storage.search_memory.return_value = [_make_memory()]

        resp = client.get(
            "/api/v1/conversation/conv-1/context",
            params={"query": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        assert len(data["memories"]) == 1


class TestConversationModeRoutes:
    def test_set_mode_returns_normalized(self, client: TestClient) -> None:
        with patch(
            "openchronicle.interfaces.api.routes.conversation.convo_mode.set_mode",
            return_value="story",
        ):
            resp = client.post(
                "/api/v1/conversation/conv-1/mode",
                json={"mode": "story"},
            )
        assert resp.status_code == 200
        assert resp.json() == {"conversation_id": "conv-1", "mode": "story"}

    def test_set_mode_rejects_invalid(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError

        with patch(
            "openchronicle.interfaces.api.routes.conversation.convo_mode.set_mode",
            side_effect=DomainValidationError("Invalid conversation mode: nope"),
        ):
            resp = client.post(
                "/api/v1/conversation/conv-1/mode",
                json={"mode": "nope"},
            )
        assert resp.status_code == 422

    def test_get_mode_returns_current(self, client: TestClient) -> None:
        with patch(
            "openchronicle.interfaces.api.routes.conversation.convo_mode.get_mode",
            return_value="general",
        ):
            resp = client.get("/api/v1/conversation/conv-1/mode")
        assert resp.status_code == 200
        assert resp.json() == {"conversation_id": "conv-1", "mode": "general"}


class TestTurnRecordRoutes:
    def test_turn_record_happy_path(self, client: TestClient) -> None:
        turn = _make_turn()
        turn.provider = "external"
        turn.routing_reasons = ["external"]
        with patch(
            "openchronicle.interfaces.api.routes.conversation.external_turn.execute",
            return_value=turn,
        ):
            resp = client.post(
                "/api/v1/conversation/conv-1/turns",
                json={"user_text": "hello", "assistant_text": "hi"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "external"
        assert data["routing_reasons"] == ["external"]

    def test_turn_record_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.conversation.external_turn.execute",
            side_effect=NotFoundError("Conversation nonexistent not found"),
        ):
            resp = client.post(
                "/api/v1/conversation/nonexistent/turns",
                json={"user_text": "hello", "assistant_text": "hi"},
            )
        assert resp.status_code == 404

    def test_turn_record_empty_fields_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/conversation/conv-1/turns",
            json={"user_text": "", "assistant_text": "hi"},
        )
        assert resp.status_code == 422


class TestAssembleContextRoutes:
    def test_assemble_context_happy_path(self, client: TestClient) -> None:
        from openchronicle.core.application.use_cases.assemble_context import AssembledContext

        mock_result = AssembledContext(
            conversation_id="conv-1",
            conversation_title="Test",
            conversation_mode="general",
            messages=[{"role": "system", "content": "You are a helpful assistant."}],
            retrieved_memories=[],
            prior_turn_count=0,
            last_interaction_at="2026-02-24T12:00:00+00:00",
            seconds_since_last_interaction=0,
        )
        with patch(
            "openchronicle.interfaces.api.routes.conversation.assemble_context.execute",
            return_value=mock_result,
        ):
            resp = client.post(
                "/api/v1/conversation/conv-1/assemble-context",
                json={"prompt": "hello"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == "conv-1"
        assert data["messages"][0]["role"] == "system"

    def test_assemble_context_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.conversation.assemble_context.execute",
            side_effect=NotFoundError("Conversation nonexistent not found"),
        ):
            resp = client.post(
                "/api/v1/conversation/nonexistent/assemble-context",
                json={"prompt": "hello"},
            )
        assert resp.status_code == 404

    def test_assemble_context_empty_prompt_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/conversation/conv-1/assemble-context",
            json={"prompt": ""},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Routes: asset
# ---------------------------------------------------------------------------


class TestAssetRoutes:
    def test_asset_upload(self, client: TestClient) -> None:
        asset = _make_asset()
        with patch(
            "openchronicle.interfaces.api.routes.asset.upload_asset.execute",
            return_value=(asset, True),
        ):
            resp = client.post(
                "/api/v1/asset",
                json={"project_id": "proj-1", "source_path": "/tmp/test.txt"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "asset-1"
        assert data["is_new"] is True

    def test_asset_list(self, client: TestClient) -> None:
        _get_container(client).storage.list_assets.return_value = [_make_asset()]

        resp = client.get("/api/v1/asset", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_asset_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/asset", params={"project_id": "proj-1"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_asset_get(self, client: TestClient) -> None:
        asset = _make_asset()
        link = _make_asset_link()
        container = _get_container(client)
        container.storage.get_asset.return_value = asset
        container.storage.list_asset_links.return_value = [link]

        resp = client.get("/api/v1/asset/asset-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.txt"
        assert len(data["links"]) == 1
        assert data["links"][0]["target_type"] == "conversation"

    def test_asset_get_404(self, client: TestClient) -> None:
        _get_container(client).storage.get_asset.return_value = None

        resp = client.get("/api/v1/asset/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_asset_link(self, client: TestClient) -> None:
        link = _make_asset_link()
        with patch(
            "openchronicle.interfaces.api.routes.asset.link_asset.execute",
            return_value=link,
        ):
            resp = client.post(
                "/api/v1/asset/asset-1/link",
                json={"target_type": "conversation", "target_id": "conv-1"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["asset_id"] == "asset-1"
        assert data["role"] == "reference"


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
            "openchronicle.interfaces.api.routes.conversation.show_conversation.execute",
            side_effect=NotFoundError("Conversation not found: x", code="CONVERSATION_NOT_FOUND"),
        ):
            resp = client.get("/api/v1/conversation/x/history")
        assert resp.status_code == 404
        body = resp.json()
        assert body["code"] == "CONVERSATION_NOT_FOUND"
        assert "Conversation not found" in body["detail"]

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

    def test_file_not_found_error_returns_400(self, client: TestClient) -> None:
        with patch(
            "openchronicle.interfaces.api.routes.asset.upload_asset.execute",
            side_effect=FileNotFoundError("Source file not found: /bad/path"),
        ):
            resp = client.post(
                "/api/v1/asset",
                json={"project_id": "p1", "source_path": "/bad/path"},
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["code"] == "FILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Conversation error paths
# ---------------------------------------------------------------------------


class TestConversationErrors:
    """Conversation routes return 404 for nonexistent conversations."""

    def test_history_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.conversation.show_conversation.execute",
            side_effect=NotFoundError("Conversation not found: missing"),
        ):
            resp = client.get("/api/v1/conversation/missing/history")
        assert resp.status_code == 404

    def test_ask_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.conversation.ask_conversation.execute",
            side_effect=NotFoundError("Conversation not found: missing"),
        ):
            resp = client.post(
                "/api/v1/conversation/missing/ask",
                json={"prompt": "hello"},
            )
        assert resp.status_code == 404

    def test_context_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.conversation.show_conversation.execute",
            side_effect=NotFoundError("Conversation not found: missing"),
        ):
            resp = client.get("/api/v1/conversation/missing/context")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Memory error paths
# ---------------------------------------------------------------------------


class TestMemoryErrors:
    """Memory routes return 404 for nonexistent memory."""

    def test_pin_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.memory.pin_memory.execute",
            side_effect=NotFoundError("Memory not found: nope"),
        ):
            resp = client.put("/api/v1/memory/nope/pin", json={"pinned": True})
        assert resp.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.memory.delete_memory.execute",
            side_effect=NotFoundError("Memory not found: nope"),
        ):
            resp = client.delete("/api/v1/memory/nope")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Asset error paths
# ---------------------------------------------------------------------------


class TestAssetErrors:
    """Asset routes return correct errors."""

    def test_upload_bad_file_returns_400(self, client: TestClient) -> None:
        with patch(
            "openchronicle.interfaces.api.routes.asset.upload_asset.execute",
            side_effect=FileNotFoundError("Source file not found: /nope"),
        ):
            resp = client.post(
                "/api/v1/asset",
                json={"project_id": "p1", "source_path": "/nope"},
            )
        assert resp.status_code == 400

    def test_link_not_found(self, client: TestClient) -> None:
        from openchronicle.core.domain.exceptions import NotFoundError

        with patch(
            "openchronicle.interfaces.api.routes.asset.link_asset.execute",
            side_effect=NotFoundError("Asset not found: nope"),
        ):
            resp = client.post(
                "/api/v1/asset/nope/link",
                json={"target_type": "conversation", "target_id": "c1"},
            )
        assert resp.status_code == 404


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

    def test_empty_prompt_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/conversation/c1/ask",
            json={"prompt": ""},
        )
        assert resp.status_code == 422

    def test_empty_source_path_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/asset",
            json={"project_id": "p1", "source_path": ""},
        )
        assert resp.status_code == 422

    def test_zero_limit_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/v1/conversation", params={"limit": 0})
        assert resp.status_code == 422

    def test_limit_over_max_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/v1/conversation", params={"limit": 10_001})
        assert resp.status_code == 422


class TestSearchTurnsRoute:
    def test_search_turns_happy_path(self, client: TestClient) -> None:
        turn = _make_turn()
        _get_container(client).storage.search_turns.return_value = [turn]

        resp = client.post(
            "/api/v1/conversation/search-turns",
            json={"query": "hello"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["user_text"] == "hello"

    def test_search_turns_empty_results(self, client: TestClient) -> None:
        _get_container(client).storage.search_turns.return_value = []

        resp = client.post(
            "/api/v1/conversation/search-turns",
            json={"query": "nonexistent"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_turns_empty_query_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/conversation/search-turns",
            json={"query": ""},
        )
        assert resp.status_code == 422

    def test_search_turns_with_conversation_id(self, client: TestClient) -> None:
        turn = _make_turn()
        _get_container(client).storage.search_turns.return_value = [turn]

        resp = client.post(
            "/api/v1/conversation/search-turns",
            json={"query": "hello", "conversation_id": "conv-1", "top_k": 5},
        )
        assert resp.status_code == 200
        _get_container(client).storage.search_turns.assert_called_once_with("hello", top_k=5, conversation_id="conv-1")


class TestPathParamValidation:
    """Path parameters reject empty or overlength values."""

    def test_empty_conversation_id_rejected(self, client: TestClient) -> None:
        # FastAPI treats /{conversation_id}/history with empty string as 404
        # because the route won't match — but we can test overlength
        resp = client.get(f"/api/v1/conversation/{'x' * 201}/history")
        assert resp.status_code == 422

    def test_empty_memory_id_rejected(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/memory/{'x' * 201}")
        assert resp.status_code == 422

    def test_empty_asset_id_rejected(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/asset/{'x' * 201}")
        assert resp.status_code == 422


class TestSystemParamValidation:
    """System route query parameters reject overlength values."""

    def test_tool_stats_overlength_tool_name(self, client: TestClient) -> None:
        resp = client.get("/api/v1/stats/tools", params={"tool_name": "x" * 201})
        assert resp.status_code == 422

    def test_moe_stats_overlength_provider(self, client: TestClient) -> None:
        resp = client.get("/api/v1/stats/moe", params={"winner_provider": "x" * 201})
        assert resp.status_code == 422


class TestOpenAPIMemoryFilter:
    """The /memory-tools/openapi.json endpoint returns a curated subset
    of OC's OpenAPI spec for memory-focused LLM tool-call clients."""

    def test_returns_valid_openapi_spec(self, client: TestClient) -> None:
        resp = client.get("/memory-tools/openapi.json")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("openapi", "").startswith("3.")
        assert "paths" in body
        assert "info" in body
        # Title rebranded to indicate it's the curated subset
        assert "Memory Tools" in body["info"]["title"]

    def test_servers_field_points_at_api_root(self, client: TestClient) -> None:
        """Open WebUI computes the API base by stripping /openapi.json from
        the spec URL — which would yield /memory-tools, not /. The servers
        field must override that so tool paths (/api/v1/memory) resolve to
        the host root. The exact base URL depends on the test client's host
        but it should NOT contain /memory-tools."""
        body = client.get("/memory-tools/openapi.json").json()
        assert "servers" in body
        assert len(body["servers"]) >= 1
        server_url = body["servers"][0]["url"]
        assert "/memory-tools" not in server_url
        # Should be just scheme://host[:port], no trailing slash
        assert not server_url.endswith("/")

    def test_includes_memory_paths(self, client: TestClient) -> None:
        body = client.get("/memory-tools/openapi.json").json()
        paths = set(body["paths"].keys())
        # Core memory CRUD must be present
        assert "/api/v1/memory" in paths
        assert "/api/v1/memory/search" in paths
        assert "/api/v1/memory/{memory_id}" in paths
        assert "/api/v1/memory/{memory_id}/pin" in paths
        # Project scoping for memory project_id parameters
        assert "/api/v1/project" in paths

    def test_excludes_non_memory_paths(self, client: TestClient) -> None:
        body = client.get("/memory-tools/openapi.json").json()
        paths = set(body["paths"].keys())
        # Webhook, asset, conversation, hook surfaces should NOT appear —
        # they're noise for the chat-with-memory use case.
        assert not any(p.startswith("/api/v1/webhook") for p in paths)
        assert not any(p.startswith("/api/v1/asset") for p in paths)
        assert not any(p.startswith("/api/v1/conversation") for p in paths)
        assert not any(p.startswith("/api/v1/hooks") for p in paths)
        assert not any(p.startswith("/api/v1/media") for p in paths)
        # System/diagnostic endpoints also excluded — operator surface, not LLM tools
        assert "/api/v1/health" not in paths
        # The filter endpoint itself isn't in its own output (we filter it out
        # via the whitelist not including it)
        assert "/memory-tools/openapi.json" not in paths

    def test_components_preserved(self, client: TestClient) -> None:
        """Components (schemas) must be preserved so $ref's in kept paths resolve."""
        body = client.get("/memory-tools/openapi.json").json()
        # If the full spec has components, the filtered one should too.
        # (The full spec almost certainly has component schemas for request/response models.)
        full = client.get("/openapi.json").json()
        if "components" in full:
            assert "components" in body
            assert body["components"] == full["components"]

    def test_kept_paths_only_have_whitelisted_methods(self, client: TestClient) -> None:
        """Methods on kept paths are filtered to the whitelisted set."""
        body = client.get("/memory-tools/openapi.json").json()
        # /api/v1/memory should have get + post (not patch/delete/etc.)
        memory_methods = set(body["paths"]["/api/v1/memory"].keys())
        assert memory_methods <= {"get", "post"}
        # /api/v1/memory/{memory_id} should have get + put + delete (not post)
        item_methods = set(body["paths"]["/api/v1/memory/{memory_id}"].keys())
        assert item_methods <= {"get", "put", "delete"}
        assert "post" not in item_methods
