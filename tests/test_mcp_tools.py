"""Tests for MCP server tools — mock container, verify each tool returns valid data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

mcp_mod = pytest.importorskip("mcp")  # noqa: F841

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError  # noqa: E402
from openchronicle.core.domain.models.conversation import Conversation, Turn  # noqa: E402
from openchronicle.core.domain.models.memory_item import MemoryItem  # noqa: E402
from openchronicle.core.domain.models.project import Project  # noqa: E402
from openchronicle.interfaces.mcp.config import MCPConfig  # noqa: E402
from openchronicle.interfaces.mcp.server import create_server  # noqa: E402

# ── Fixtures ──────────────────────────────────────────────────────


def _make_container() -> MagicMock:
    """Build a mock CoreContainer with storage, event_logger, llm, etc."""
    container = MagicMock()
    container.storage = MagicMock()
    container.event_logger = MagicMock()
    container.event_logger.append = MagicMock()
    container.llm = MagicMock()
    container.interaction_router = MagicMock()
    container.router_policy = MagicMock()
    container.privacy_gate = MagicMock()
    container.privacy_settings = MagicMock()
    container.file_configs = {}
    return container


def _make_context(container: MagicMock) -> MagicMock:
    """Build a mock Context that returns our container via lifespan_context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"container": container}
    return ctx


_NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


def _sample_memory(**overrides: Any) -> MemoryItem:
    defaults: dict[str, Any] = {
        "id": "mem-1",
        "content": "User prefers Python",
        "tags": ["preference"],
        "pinned": False,
        "conversation_id": None,
        "project_id": "proj-1",
        "source": "manual",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return MemoryItem(**defaults)


def _sample_conversation(**overrides: Any) -> Conversation:
    defaults: dict[str, Any] = {
        "id": "convo-1",
        "project_id": "proj-1",
        "title": "Test convo",
        "mode": "general",
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return Conversation(**defaults)


def _sample_turn(**overrides: Any) -> Turn:
    defaults: dict[str, Any] = {
        "id": "turn-1",
        "conversation_id": "convo-1",
        "turn_index": 0,
        "user_text": "Hello",
        "assistant_text": "Hi there!",
        "provider": "stub",
        "model": "stub-model",
        "routing_reasons": ["default"],
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return Turn(**defaults)


def _sample_project(**overrides: Any) -> Project:
    defaults: dict[str, Any] = {
        "id": "proj-1",
        "name": "Test Project",
        "metadata": {"type": "test"},
        "created_at": _NOW,
    }
    defaults.update(overrides)
    return Project(**defaults)


# ── Server creation ──────────────────────────────────────────────


class TestServerCreation:
    def test_create_server_registers_tools(self) -> None:
        container = _make_container()
        config = MCPConfig()
        server = create_server(container, config)
        tool_names = list(server._tool_manager._tools.keys())
        expected = [
            "health",
            "project_create",
            "project_list",
            "memory_search",
            "memory_save",
            "memory_list",
            "memory_pin",
            "memory_update",
            "memory_get",
            "memory_delete",
            "memory_stats",
            "memory_embed",
            "conversation_create",
            "conversation_list",
            "conversation_history",
            "conversation_ask",
            "conversation_set_mode",
            "conversation_get_mode",
            "turn_record",
            "context_recent",
            "context_assemble",
            "tool_stats",
            "moe_stats",
            "search_turns",
            "onboard_git",
            "asset_upload",
            "asset_list",
            "asset_get",
            "asset_link",
            "webhook_register",
            "webhook_list",
            "webhook_delete",
            "media_generate",
        ]
        assert sorted(tool_names) == sorted(expected)


# ── Project tools ─────────────────────────────────────────────────


class TestProjectCreate:
    def test_creates_project(self) -> None:
        container = _make_container()
        ctx = _make_context(container)
        proj = _sample_project()
        with patch("openchronicle.interfaces.mcp.tools.project.create_project") as mock_uc:
            mock_uc.execute.return_value = proj
            from openchronicle.interfaces.mcp.tools.project import register

            mcp_server = MagicMock()
            registered: dict[str, Any] = {}
            mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
            register(mcp_server)
            result = registered["project_create"](name="My Project", ctx=ctx)
        assert result["id"] == "proj-1"
        assert result["name"] == "Test Project"


class TestProjectList:
    def test_lists_projects(self) -> None:
        container = _make_container()
        ctx = _make_context(container)
        projects = [_sample_project(), _sample_project(id="proj-2", name="Second")]
        with patch("openchronicle.interfaces.mcp.tools.project.list_projects") as mock_uc:
            mock_uc.execute.return_value = projects
            from openchronicle.interfaces.mcp.tools.project import register

            mcp_server = MagicMock()
            registered: dict[str, Any] = {}
            mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
            register(mcp_server)
            result = registered["project_list"](ctx=ctx)
        assert len(result) == 2
        assert result[0]["id"] == "proj-1"
        assert result[1]["id"] == "proj-2"


# ── Memory tools ──────────────────────────────────────────────────


class TestMemorySearch:
    def test_returns_results(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        # Call the function directly (registered tools are wrapped)
        container.storage.search = MagicMock(return_value=[_sample_memory()])

        with patch(
            "openchronicle.interfaces.mcp.tools.memory.search_memory.execute",
            return_value=[_sample_memory()],
        ) as mock_search:
            # Access the raw function
            tool_fn = mcp._tool_manager._tools["memory_search"].fn
            result = tool_fn(query="Python", ctx=ctx)

        assert len(result) == 1
        assert result[0]["content"] == "User prefers Python"
        assert result[0]["id"] == "mem-1"
        mock_search.assert_called_once()


class TestMemorySave:
    def test_saves_with_project_id(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        saved_mem = _sample_memory(source="mcp")
        with patch(
            "openchronicle.interfaces.mcp.tools.memory.add_memory.execute",
            return_value=saved_mem,
        ):
            tool_fn = mcp._tool_manager._tools["memory_save"].fn
            result = tool_fn(content="Remember this", project_id="proj-1", ctx=ctx)

        assert result["content"] == "User prefers Python"
        assert result["source"] == "mcp"

    def test_derives_project_from_conversation(self) -> None:
        container = _make_container()
        ctx = _make_context(container)
        container.storage.get_conversation = MagicMock(return_value=_sample_conversation(project_id="proj-from-convo"))

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        saved_mem = _sample_memory(project_id="proj-from-convo", source="mcp")
        with patch(
            "openchronicle.interfaces.mcp.tools.memory.add_memory.execute",
            return_value=saved_mem,
        ) as mock_add:
            tool_fn = mcp._tool_manager._tools["memory_save"].fn
            tool_fn(content="Remember this", conversation_id="convo-1", ctx=ctx)

        # Verify project_id was derived
        call_args = mock_add.call_args
        item = call_args.kwargs["item"]
        assert item.project_id == "proj-from-convo"

    def test_raises_without_project_id(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["memory_save"].fn
        with pytest.raises(DomainValidationError, match="project_id is required"):
            tool_fn(content="Remember this", ctx=ctx)


class TestMemoryList:
    def test_returns_all(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.memory.list_memory.execute",
            return_value=[_sample_memory(), _sample_memory(id="mem-2")],
        ):
            tool_fn = mcp._tool_manager._tools["memory_list"].fn
            result = tool_fn(ctx=ctx)

        assert len(result) == 2


class TestMemoryPin:
    def test_pins_memory(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.memory.pin_memory.execute",
        ) as mock_pin:
            tool_fn = mcp._tool_manager._tools["memory_pin"].fn
            result = tool_fn(memory_id="mem-1", ctx=ctx)

        assert result["status"] == "ok"
        assert result["pinned"] == "True"
        mock_pin.assert_called_once()


# ── Conversation tools ────────────────────────────────────────────


class TestConversationCreate:
    def test_creates_conversation(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.create_conversation.execute",
            return_value=_sample_conversation(),
        ):
            tool_fn = mcp._tool_manager._tools["conversation_create"].fn
            result = tool_fn(ctx=ctx, title="My chat")

        assert result["id"] == "convo-1"
        assert result["title"] == "Test convo"


class TestConversationList:
    def test_lists_conversations(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.list_conversations.execute",
            return_value=[_sample_conversation(), _sample_conversation(id="convo-2")],
        ):
            tool_fn = mcp._tool_manager._tools["conversation_list"].fn
            result = tool_fn(ctx=ctx)

        assert len(result) == 2


class TestConversationHistory:
    def test_returns_turns(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.show_conversation.execute",
            return_value=(_sample_conversation(), [_sample_turn(), _sample_turn(turn_index=1)]),
        ):
            tool_fn = mcp._tool_manager._tools["conversation_history"].fn
            result = tool_fn(conversation_id="convo-1", ctx=ctx)

        assert result["conversation"]["id"] == "convo-1"
        assert len(result["turns"]) == 2


class TestConversationAsk:
    @pytest.mark.asyncio
    async def test_ask_returns_turn(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.ask_conversation.execute",
            new_callable=AsyncMock,
            return_value=_sample_turn(assistant_text="I can help!"),
        ):
            tool_fn = mcp._tool_manager._tools["conversation_ask"].fn
            result = await tool_fn(conversation_id="convo-1", prompt="Help me", ctx=ctx)

        assert result["assistant_text"] == "I can help!"
        assert result["user_text"] == "Hello"


class TestConversationMode:
    def test_set_mode_returns_normalized(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.convo_mode.set_mode",
            return_value="story",
        ):
            tool_fn = mcp._tool_manager._tools["conversation_set_mode"].fn
            result = tool_fn(conversation_id="convo-1", mode="story", ctx=ctx)

        assert result == {"conversation_id": "convo-1", "mode": "story"}

    def test_set_mode_rejects_invalid(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.convo_mode.set_mode",
            side_effect=DomainValidationError("Invalid conversation mode: nope"),
        ):
            tool_fn = mcp._tool_manager._tools["conversation_set_mode"].fn
            with pytest.raises(DomainValidationError, match="Invalid conversation mode"):
                tool_fn(conversation_id="convo-1", mode="nope", ctx=ctx)

    def test_get_mode_returns_current(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.convo_mode.get_mode",
            return_value="general",
        ):
            tool_fn = mcp._tool_manager._tools["conversation_get_mode"].fn
            result = tool_fn(conversation_id="convo-1", ctx=ctx)

        assert result == {"conversation_id": "convo-1", "mode": "general"}


class TestTurnRecord:
    def test_turn_record_happy_path(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.conversation.external_turn.execute",
            return_value=_sample_turn(provider="external", model="", routing_reasons=["external"]),
        ):
            tool_fn = mcp._tool_manager._tools["turn_record"].fn
            result = tool_fn(
                conversation_id="convo-1",
                user_text="hello",
                assistant_text="hi",
                ctx=ctx,
            )

        assert result["provider"] == "external"
        assert result["routing_reasons"] == ["external"]

    def test_turn_record_rejects_empty_user_text(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["turn_record"].fn
        with pytest.raises(DomainValidationError, match="user_text"):
            tool_fn(
                conversation_id="convo-1",
                user_text="",
                assistant_text="hi",
                ctx=ctx,
            )

    def test_turn_record_rejects_empty_assistant_text(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.conversation import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["turn_record"].fn
        with pytest.raises(DomainValidationError, match="assistant_text"):
            tool_fn(
                conversation_id="convo-1",
                user_text="hello",
                assistant_text="",
                ctx=ctx,
            )


# ── Context tools ─────────────────────────────────────────────────


class TestContextRecent:
    def test_with_conversation_and_query(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.context import register

        mcp = FastMCP("test")
        register(mcp)

        with (
            patch(
                "openchronicle.interfaces.mcp.tools.context.show_conversation.execute",
                return_value=(_sample_conversation(), [_sample_turn()]),
            ),
            patch(
                "openchronicle.interfaces.mcp.tools.context.search_memory.execute",
                return_value=[_sample_memory()],
            ),
        ):
            tool_fn = mcp._tool_manager._tools["context_recent"].fn
            result = tool_fn(ctx=ctx, conversation_id="convo-1", query="Python")

        assert "conversation" in result
        assert len(result["recent_turns"]) == 1
        assert len(result["memories"]) == 1

    def test_empty_without_args(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.context import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["context_recent"].fn
        result = tool_fn(ctx=ctx)

        assert "message" in result


class TestContextAssemble:
    def test_context_assemble_happy_path(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.context import register

        mcp = FastMCP("test")
        register(mcp)

        from openchronicle.core.application.use_cases.assemble_context import AssembledContext

        mock_result = AssembledContext(
            conversation_id="convo-1",
            conversation_title="Test",
            conversation_mode="general",
            messages=[{"role": "system", "content": "You are a helpful assistant."}],
            retrieved_memories=[],
            prior_turn_count=0,
            last_interaction_at=_NOW.isoformat(),
            seconds_since_last_interaction=0,
        )

        with patch(
            "openchronicle.interfaces.mcp.tools.context.assemble_context.execute",
            return_value=mock_result,
        ):
            tool_fn = mcp._tool_manager._tools["context_assemble"].fn
            result = tool_fn(conversation_id="convo-1", prompt="hello", ctx=ctx)

        assert result["conversation_id"] == "convo-1"
        assert result["conversation_title"] == "Test"
        assert len(result["messages"]) == 1

    def test_context_assemble_rejects_empty_prompt(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.context import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["context_assemble"].fn
        with pytest.raises(DomainValidationError, match="prompt"):
            tool_fn(conversation_id="convo-1", prompt="", ctx=ctx)


# ── System tools ──────────────────────────────────────────────────


class TestHealth:
    def test_returns_diagnostics(self) -> None:
        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.system import register

        mcp = FastMCP("test")
        register(mcp)

        container = _make_container()
        container.embedding_status_dict.return_value = {"status": "disabled", "provider": "none"}
        ctx = _make_context(container)

        # Mock diagnose_runtime.execute to avoid needing real filesystem
        from openchronicle.core.application.models.diagnostics_report import DiagnosticsReport

        mock_report = DiagnosticsReport(
            timestamp_utc=_NOW,
            db_path="data/test.db",
            db_exists=True,
            db_size_bytes=1024,
            db_modified_utc=_NOW,
            config_dir="config",
            config_dir_exists=True,
            plugin_dir="plugins",
            plugin_dir_exists=True,
            running_in_container_hint=False,
            persistence_hint="sqlite",
            provider_env_summary={"OC_LLM_PROVIDER": "stub"},
            models_dir="config/models",
            models_dir_exists=True,
            model_config_files_count=2,
            model_config_provider_summary={"openai": {"gpt-4o": 1}},
            model_config_load_errors={},
        )

        with patch(
            "openchronicle.interfaces.mcp.tools.system.diagnose_runtime.execute",
            return_value=mock_report,
        ):
            tool_fn = mcp._tool_manager._tools["health"].fn
            result = tool_fn(ctx=ctx)

        assert result["db_exists"] is True
        assert result["config_dir"] == "config"
        # Datetime should be serialized
        assert "2026-02-20" in result["timestamp_utc"]
        # Embedding status should be present
        assert result["embedding_status"]["status"] == "disabled"


class TestSearchTurns:
    def test_returns_results(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.system import register

        mcp = FastMCP("test")
        register(mcp)

        container.storage.search_turns = MagicMock(return_value=[_sample_turn()])

        tool_fn = mcp._tool_manager._tools["search_turns"].fn
        result = tool_fn(query="Hello", ctx=ctx)

        assert len(result) == 1
        assert result[0]["user_text"] == "Hello"
        container.storage.search_turns.assert_called_once_with("Hello", top_k=10, conversation_id=None)

    def test_empty_query_rejected(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.system import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["search_turns"].fn
        with pytest.raises(DomainValidationError, match="query must be non-empty"):
            tool_fn(query="", ctx=ctx)

    def test_whitespace_query_rejected(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.system import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["search_turns"].fn
        with pytest.raises(DomainValidationError, match="query must be non-empty"):
            tool_fn(query="   ", ctx=ctx)


class TestMCPParameterValidation:
    """MCP tool parameter validation — clamping and rejection."""

    def test_memory_search_empty_query_rejected(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["memory_search"].fn
        with pytest.raises(DomainValidationError, match="query must be non-empty"):
            tool_fn(query="", ctx=ctx)

    def test_memory_save_empty_content_rejected(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["memory_save"].fn
        with pytest.raises(DomainValidationError, match="content must be non-empty"):
            tool_fn(content="", ctx=ctx)

    def test_memory_save_overlength_content_rejected(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        tool_fn = mcp._tool_manager._tools["memory_save"].fn
        with pytest.raises(DomainValidationError, match="exceeds maximum length"):
            tool_fn(content="x" * 100_001, ctx=ctx)

    def test_memory_search_top_k_clamped(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.memory.search_memory.execute",
            return_value=[],
        ) as mock_search:
            tool_fn = mcp._tool_manager._tools["memory_search"].fn
            tool_fn(query="test", ctx=ctx, top_k=999_999)

        # top_k should be clamped to 1000
        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["top_k"] == 1000

    def test_memory_search_negative_offset_clamped(self) -> None:
        container = _make_container()
        ctx = _make_context(container)

        from mcp.server.fastmcp import FastMCP

        from openchronicle.interfaces.mcp.tools.memory import register

        mcp = FastMCP("test")
        register(mcp)

        with patch(
            "openchronicle.interfaces.mcp.tools.memory.search_memory.execute",
            return_value=[],
        ) as mock_search:
            tool_fn = mcp._tool_manager._tools["memory_search"].fn
            tool_fn(query="test", ctx=ctx, offset=-5)

        call_kwargs = mock_search.call_args[1]
        assert call_kwargs["offset"] == 0
