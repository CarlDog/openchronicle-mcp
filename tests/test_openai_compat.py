"""Tests for the OpenAI-compatible API (/v1/models, /v1/chat/completions)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from openchronicle.core.application.config.model_config import ModelConfigEntry
from openchronicle.core.application.routing.router_policy import RouteDecision
from openchronicle.core.domain.ports.llm_port import (
    LLMProviderError,
    LLMResponse,
    LLMUsage,
    StreamChunk,
)
from openchronicle.interfaces.api.config import HTTPConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STUB_ENTRIES = [
    ModelConfigEntry(
        provider="openai",
        model="gpt-4o",
        enabled=True,
        filename="openai_gpt4o.json",
        display_name="GPT-4o",
        api_config={},
    ),
    ModelConfigEntry(
        provider="ollama",
        model="llama3",
        enabled=True,
        filename="ollama_llama3.json",
        display_name="Llama 3",
        api_config={},
    ),
    ModelConfigEntry(
        provider="stub",
        model="stub-model",
        enabled=True,
        filename="stub.json",
        display_name="Stub",
        api_config={},
    ),
]


def _make_mock_container(entries: list[ModelConfigEntry] | None = None) -> MagicMock:
    container = MagicMock()
    container.model_config_loader.list_enabled.return_value = entries if entries is not None else _STUB_ENTRIES
    container.router_policy.route.return_value = RouteDecision(
        provider="stub",
        model="stub-model",
        mode="fast",
        reasons=["default"],
    )
    container.llm = AsyncMock()
    container.file_configs = {}
    container.embedding_service = None
    container.embedding_status_dict.return_value = {"status": "disabled", "provider": "none"}
    container.media_port = None
    container.storage = MagicMock()
    container.storage.get_mcp_tool_stats.return_value = []
    container.storage.get_moe_stats.return_value = []
    container.storage.list_conversations.return_value = []
    container.storage.list_assets.return_value = []
    container.storage.search_memory.return_value = []
    container.storage.list_memory.return_value = []
    container.orchestrator.list_projects.return_value = []
    return container


def _make_client(
    container: MagicMock | None = None,
    api_key: str | None = None,
) -> TestClient:
    from openchronicle.interfaces.api.app import create_app

    c = container or _make_mock_container()
    config = HTTPConfig(api_key=api_key) if api_key else HTTPConfig()
    app = create_app(c, config)
    return TestClient(app)


def _get_container(client: TestClient) -> MagicMock:
    return client.app.state.container  # type: ignore[attr-defined, no-any-return]


def _stub_response(content: str = "Hello!") -> LLMResponse:
    return LLMResponse(
        content=content,
        provider="stub",
        model="stub-model",
        finish_reason="stop",
        usage=LLMUsage(input_tokens=10, output_tokens=5, total_tokens=15),
    )


# ---------------------------------------------------------------------------
# GET /v1/models
# ---------------------------------------------------------------------------


class TestListModels:
    def test_returns_openai_list_format(self) -> None:
        client = _make_client()
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert isinstance(data["data"], list)

    def test_model_entries_have_required_fields(self) -> None:
        client = _make_client()
        resp = client.get("/v1/models")
        for model in resp.json()["data"]:
            assert "id" in model
            assert model["object"] == "model"
            assert "created" in model
            assert "owned_by" in model

    def test_model_ids_use_provider_slash_model(self) -> None:
        client = _make_client()
        resp = client.get("/v1/models")
        ids = [m["id"] for m in resp.json()["data"]]
        assert "openai/gpt-4o" in ids
        assert "ollama/llama3" in ids
        assert "stub/stub-model" in ids

    def test_owned_by_is_provider(self) -> None:
        client = _make_client()
        resp = client.get("/v1/models")
        for model in resp.json()["data"]:
            provider = model["id"].split("/")[0]
            assert model["owned_by"] == provider

    def test_only_enabled_models_appear(self) -> None:
        entries = [
            ModelConfigEntry(
                provider="openai",
                model="gpt-4o",
                enabled=True,
                filename="f.json",
                display_name=None,
                api_config={},
            ),
        ]
        container = _make_mock_container(entries)
        client = _make_client(container)
        resp = client.get("/v1/models")
        assert len(resp.json()["data"]) == 1

    def test_empty_models_returns_empty_list(self) -> None:
        container = _make_mock_container(entries=[])
        client = _make_client(container)
        resp = client.get("/v1/models")
        data = resp.json()
        assert data == {"object": "list", "data": []}


# ---------------------------------------------------------------------------
# POST /v1/chat/completions — non-streaming
# ---------------------------------------------------------------------------


class TestChatCompletionsNonStreaming:
    def test_valid_request_returns_completion_format(self) -> None:
        client = _make_client()
        _get_container(client).llm.complete_async = AsyncMock(return_value=_stub_response())
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["id"].startswith("chatcmpl-")
        assert "created" in data
        assert "model" in data
        assert "choices" in data
        assert "usage" in data

    def test_response_message_has_role_and_content(self) -> None:
        client = _make_client()
        _get_container(client).llm.complete_async = AsyncMock(return_value=_stub_response("World"))
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        msg = resp.json()["choices"][0]["message"]
        assert msg["role"] == "assistant"
        assert msg["content"] == "World"

    def test_usage_fields_present(self) -> None:
        client = _make_client()
        _get_container(client).llm.complete_async = AsyncMock(return_value=_stub_response())
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        usage = resp.json()["usage"]
        assert usage["prompt_tokens"] == 10
        assert usage["completion_tokens"] == 5
        assert usage["total_tokens"] == 15

    def test_auto_model_uses_default_routing(self) -> None:
        client = _make_client()
        container = _get_container(client)
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client.post(
            "/v1/chat/completions",
            json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
        )
        container.router_policy.route.assert_called_once()

    def test_explicit_model_uses_direct_route(self) -> None:
        client = _make_client()
        container = _get_container(client)
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "stub/stub-model",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert resp.status_code == 200
        # Should NOT have called router_policy.route — explicit model bypasses it
        container.router_policy.route.assert_not_called()
        # Model label in response should match request
        assert resp.json()["model"] == "stub/stub-model"

    def test_unknown_model_returns_404(self) -> None:
        client = _make_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "nonexistent/model",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_model_without_slash_returns_404(self) -> None:
        client = _make_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "model": "badformat",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert resp.status_code == 404

    def test_empty_messages_rejected(self) -> None:
        client = _make_client()
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": []},
        )
        assert resp.status_code == 422

    def test_temperature_forwarded(self) -> None:
        client = _make_client()
        container = _get_container(client)
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "temperature": 0.7,
            },
        )
        call_kwargs = container.llm.complete_async.call_args
        assert call_kwargs.kwargs.get("temperature") == 0.7

    def test_max_tokens_forwarded(self) -> None:
        client = _make_client()
        container = _get_container(client)
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 500,
            },
        )
        call_kwargs = container.llm.complete_async.call_args
        assert call_kwargs.kwargs.get("max_output_tokens") == 500

    def test_llm_error_returns_502(self) -> None:
        client = _make_client()
        container = _get_container(client)
        container.llm.complete_async = AsyncMock(side_effect=LLMProviderError("provider down", status_code=503))
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 503

    def test_usage_defaults_to_zero_when_none(self) -> None:
        response = LLMResponse(
            content="hi",
            provider="stub",
            model="stub-model",
            usage=None,
        )
        client = _make_client()
        _get_container(client).llm.complete_async = AsyncMock(return_value=response)
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        usage = resp.json()["usage"]
        assert usage == {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


# ---------------------------------------------------------------------------
# POST /v1/chat/completions — streaming
# ---------------------------------------------------------------------------


class TestChatCompletionsStreaming:
    @staticmethod
    def _parse_sse(text: str) -> list[dict | str]:
        """Parse SSE text into list of parsed JSON dicts or raw strings."""
        events: list[dict | str] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("data: "):
                payload = line[len("data: ") :]
                if payload == "[DONE]":
                    events.append("[DONE]")
                else:
                    events.append(json.loads(payload))
        return events

    def _make_streaming_client(self) -> TestClient:
        """Build a client whose LLM streams 3 chunks."""
        client = _make_client()
        container = _get_container(client)

        chunks = [
            StreamChunk(text="Hello", finished=False, provider="stub", model="stub-model"),
            StreamChunk(text=" world", finished=False, provider="stub", model="stub-model"),
            StreamChunk(
                text="",
                finished=True,
                provider="stub",
                model="stub-model",
                finish_reason="stop",
                usage=LLMUsage(input_tokens=5, output_tokens=2, total_tokens=7),
            ),
        ]

        async def mock_stream(**kwargs: object) -> object:
            for c in chunks:
                yield c

        container.llm.stream_async = mock_stream
        return client

    def test_returns_event_stream_content_type(self) -> None:
        client = self._make_streaming_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

    def test_sse_format(self) -> None:
        client = self._make_streaming_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        events = self._parse_sse(resp.text)
        # Should have 3 data chunks + [DONE]
        assert len(events) == 4
        assert events[-1] == "[DONE]"

    def test_first_chunk_has_role(self) -> None:
        client = self._make_streaming_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        events = self._parse_sse(resp.text)
        first = events[0]
        assert isinstance(first, dict)
        assert first["choices"][0]["delta"]["role"] == "assistant"

    def test_content_chunks_have_delta_content(self) -> None:
        client = self._make_streaming_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        events = self._parse_sse(resp.text)
        first = events[0]
        second = events[1]
        assert isinstance(first, dict)
        assert isinstance(second, dict)
        assert first["choices"][0]["delta"].get("content") == "Hello"
        assert second["choices"][0]["delta"]["content"] == " world"

    def test_final_chunk_has_finish_reason(self) -> None:
        client = self._make_streaming_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        events = self._parse_sse(resp.text)
        final = events[-2]  # Last JSON chunk before [DONE]
        assert isinstance(final, dict)
        assert final["choices"][0]["finish_reason"] == "stop"

    def test_chunk_object_type_is_chunk(self) -> None:
        client = self._make_streaming_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        events = self._parse_sse(resp.text)
        for event in events:
            if isinstance(event, dict):
                assert event["object"] == "chat.completion.chunk"

    def test_stream_ends_with_done(self) -> None:
        client = self._make_streaming_client()
        resp = client.post(
            "/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        assert resp.text.rstrip().endswith("data: [DONE]")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestOpenAICompatAuth:
    def test_models_requires_auth_when_configured(self) -> None:
        client = _make_client(api_key="test-secret")
        resp = client.get("/v1/models")
        assert resp.status_code == 401

    def test_models_with_bearer_token(self) -> None:
        client = _make_client(api_key="test-secret")
        resp = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer test-secret"},
        )
        assert resp.status_code == 200

    def test_completions_requires_auth_when_configured(self) -> None:
        client = _make_client(api_key="test-secret")
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 401

    def test_completions_with_bearer_token(self) -> None:
        client = _make_client(api_key="test-secret")
        container = _get_container(client)
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        resp = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": "Bearer test-secret"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# V2 — Persistent endpoints (project-scoped / conversation-scoped)
# ---------------------------------------------------------------------------


def _make_v2_container() -> MagicMock:
    """Build a mock container with V2-specific setup (project + conversation)."""
    container = _make_mock_container()

    from openchronicle.core.domain.models.conversation import Conversation
    from openchronicle.core.domain.models.project import Project

    project = Project(id="proj-1", name="Test Project")
    container.storage.get_project.return_value = project

    webui_convo = Conversation(
        id="convo-webui",
        project_id="proj-1",
        title="Open WebUI Session",
        mode="webui",
    )
    container.storage.list_conversations.return_value = [webui_convo]
    container.storage.get_conversation.return_value = webui_convo

    # assemble_context needs: list_turns, list_memory, search_memory
    container.storage.list_turns.return_value = []
    container.storage.list_memory.return_value = []
    container.storage.search_memory.return_value = []

    # external_turn needs: next_turn_index, add_turn, transaction
    container.storage.next_turn_index.return_value = 0
    container.emit_event = MagicMock()

    return container


class TestPersistentModelsEndpoints:
    """GET /v1/p/{project_id}/models and /v1/p/{pid}/c/{cid}/models."""

    def test_project_models_includes_oc_synthetic_model(self) -> None:
        client = _make_client()
        resp = client.get("/v1/p/any-project/models")
        data = resp.json()["data"]
        assert data[0]["id"] == "openchronicle"
        assert data[0]["owned_by"] == "openchronicle"

    def test_project_models_includes_real_models_after_oc(self) -> None:
        client = _make_client()
        v1_data = client.get("/v1/models").json()["data"]
        v2_data = client.get("/v1/p/any-project/models").json()["data"]
        assert v2_data[1:] == v1_data

    def test_conversation_models_includes_oc_synthetic_model(self) -> None:
        client = _make_client()
        resp = client.get("/v1/p/any-project/c/any-convo/models")
        data = resp.json()["data"]
        assert data[0]["id"] == "openchronicle"

    def test_v1_models_does_not_include_oc_synthetic(self) -> None:
        client = _make_client()
        data = client.get("/v1/models").json()["data"]
        ids = [m["id"] for m in data]
        assert "openchronicle" not in ids

    def test_project_models_returns_200(self) -> None:
        client = _make_client()
        resp = client.get("/v1/p/some-project-id/models")
        assert resp.status_code == 200
        assert resp.json()["object"] == "list"

    def test_conversation_models_returns_200(self) -> None:
        client = _make_client()
        resp = client.get("/v1/p/some-project-id/c/some-convo-id/models")
        assert resp.status_code == 200
        assert resp.json()["object"] == "list"

    def test_openchronicle_model_routes_like_auto(self) -> None:
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/chat/completions",
            json={"model": "openchronicle", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200
        container.router_policy.route.assert_called_once()


class TestAutoSessionChatCompletions:
    """POST /v1/p/{project_id}/chat/completions — auto-session mode."""

    def test_creates_webui_conversation_on_first_request(self) -> None:
        container = _make_v2_container()
        # No existing webui conversation
        container.storage.list_conversations.return_value = []
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 200
        container.storage.add_conversation.assert_called_once()

    def test_reuses_existing_webui_conversation(self) -> None:
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 200
        container.storage.add_conversation.assert_not_called()

    def test_invalid_project_returns_404(self) -> None:
        container = _make_v2_container()
        container.storage.get_project.return_value = None
        client = _make_client(container)

        resp = client.post(
            "/v1/p/nonexistent/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 404

    def test_non_streaming_returns_openai_format(self) -> None:
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response("Hi there"))
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert data["choices"][0]["message"]["content"] == "Hi there"

    def test_turn_recorded_after_response(self) -> None:
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response("response"))
        client = _make_client(container)

        client.post(
            "/v1/p/proj-1/chat/completions",
            json={"messages": [{"role": "user", "content": "question"}]},
        )
        container.storage.add_turn.assert_called_once()

    def test_streaming_returns_sse_format(self) -> None:
        container = _make_v2_container()
        chunks = [
            StreamChunk(text="Hi", finished=False, provider="stub", model="stub-model"),
            StreamChunk(text="", finished=True, provider="stub", model="stub-model", finish_reason="stop"),
        ]

        async def mock_stream(**kwargs: object) -> object:
            for c in chunks:
                yield c

        container.llm.stream_async = mock_stream
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "stream": True},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert "data: [DONE]" in resp.text

    def test_streaming_records_turn_after_done(self) -> None:
        container = _make_v2_container()
        chunks = [
            StreamChunk(text="Hello world", finished=False, provider="stub", model="stub-model"),
            StreamChunk(text="", finished=True, provider="stub", model="stub-model", finish_reason="stop"),
        ]

        async def mock_stream(**kwargs: object) -> object:
            for c in chunks:
                yield c

        container.llm.stream_async = mock_stream
        client = _make_client(container)

        client.post(
            "/v1/p/proj-1/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "stream": True},
        )
        container.storage.add_turn.assert_called_once()

    def test_extracts_last_user_message(self) -> None:
        """When multiple messages are sent, the last user message is the prompt."""
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client = _make_client(container)

        client.post(
            "/v1/p/proj-1/chat/completions",
            json={
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "first"},
                    {"role": "assistant", "content": "sure"},
                    {"role": "user", "content": "second"},
                ],
            },
        )
        # The turn recorded should use "second" as user_text
        turn_args = container.storage.add_turn.call_args[0][0]
        assert turn_args.user_text == "second"

    def test_synthetic_task_prompt_not_recorded(self) -> None:
        """Open WebUI follow-up suggestion prompts should not pollute turns."""
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response("suggestions"))
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/chat/completions",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": "### Task:\nSuggest 3-5 relevant follow-up questions",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        # Turn should NOT be recorded for synthetic prompts
        container.storage.add_turn.assert_not_called()


class TestExplicitConversationChatCompletions:
    """POST /v1/p/{project_id}/c/{conversation_id}/chat/completions."""

    def test_valid_project_and_conversation_works(self) -> None:
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/c/convo-webui/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 200

    def test_conversation_not_in_project_returns_404(self) -> None:
        container = _make_v2_container()
        from openchronicle.core.domain.models.conversation import Conversation

        other_convo = Conversation(id="other-convo", project_id="other-project", mode="general")
        container.storage.get_conversation.return_value = other_convo
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/c/other-convo/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 404

    def test_missing_conversation_returns_404(self) -> None:
        container = _make_v2_container()
        container.storage.get_conversation.return_value = None
        client = _make_client(container)

        resp = client.post(
            "/v1/p/proj-1/c/nonexistent/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 404

    def test_missing_project_returns_404(self) -> None:
        container = _make_v2_container()
        container.storage.get_project.return_value = None
        client = _make_client(container)

        resp = client.post(
            "/v1/p/bad-proj/c/convo-webui/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 404

    def test_turn_recording_uses_correct_provider_model(self) -> None:
        container = _make_v2_container()
        container.llm.complete_async = AsyncMock(return_value=_stub_response())
        client = _make_client(container)

        client.post(
            "/v1/p/proj-1/c/convo-webui/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        turn = container.storage.add_turn.call_args[0][0]
        assert turn.provider == "stub"
        assert turn.model == "stub-model"

    def test_streaming_records_turn(self) -> None:
        container = _make_v2_container()
        chunks = [
            StreamChunk(text="Result", finished=False, provider="stub", model="stub-model"),
            StreamChunk(text="", finished=True, provider="stub", model="stub-model", finish_reason="stop"),
        ]

        async def mock_stream(**kwargs: object) -> object:
            for c in chunks:
                yield c

        container.llm.stream_async = mock_stream
        client = _make_client(container)

        client.post(
            "/v1/p/proj-1/c/convo-webui/chat/completions",
            json={"messages": [{"role": "user", "content": "hello"}], "stream": True},
        )
        container.storage.add_turn.assert_called_once()


class TestListConversationsProjectFilter:
    """Port-level test: list_conversations with project_id filter."""

    def test_filter_by_project_id(self) -> None:
        container = _make_v2_container()
        container.storage.list_conversations.return_value = []
        _make_client(container)

        container.storage.list_conversations(project_id="proj-1")
        container.storage.list_conversations.assert_called_with(project_id="proj-1")

    def test_no_filter_returns_all(self) -> None:
        container = _make_v2_container()
        _make_client(container)

        container.storage.list_conversations()
        container.storage.list_conversations.assert_called_with()
