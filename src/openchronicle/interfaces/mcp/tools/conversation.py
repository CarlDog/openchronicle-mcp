"""Conversation tools — create, list, history, ask."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import (
    ask_conversation,
    create_conversation,
    list_conversations,
    show_conversation,
)
from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


def _turn_to_dict(t: Turn) -> dict[str, Any]:
    """Convert a Turn dataclass to a JSON-safe dict."""
    return {
        "id": t.id,
        "conversation_id": t.conversation_id,
        "turn_index": t.turn_index,
        "user_text": t.user_text,
        "assistant_text": t.assistant_text,
        "provider": t.provider,
        "model": t.model,
        "routing_reasons": t.routing_reasons,
        "created_at": t.created_at.isoformat(),
    }


def _convo_to_dict(c: Conversation) -> dict[str, Any]:
    """Convert a Conversation dataclass to a JSON-safe dict."""
    return {
        "id": c.id,
        "project_id": c.project_id,
        "title": c.title,
        "mode": c.mode,
        "created_at": c.created_at.isoformat(),
    }


def register(mcp: FastMCP) -> None:
    """Register conversation tools on the MCP server."""

    @mcp.tool()
    @track_tool
    def conversation_create(
        ctx: Context,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation.

        Args:
            title: Optional title for the conversation.
        """
        container = _get_container(ctx)
        convo = create_conversation.execute(
            storage=container.storage,
            convo_store=container.storage,
            emit_event=container.event_logger.append,
            title=title,
        )
        return _convo_to_dict(convo)

    @mcp.tool()
    @track_tool
    def conversation_list(
        ctx: Context,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """List conversations, most recent first.

        Args:
            limit: Maximum number of conversations to return (None for all).
        """
        container = _get_container(ctx)
        convos = list_conversations.execute(
            convo_store=container.storage,
            limit=limit,
        )
        return [_convo_to_dict(c) for c in convos]

    @mcp.tool()
    @track_tool
    def conversation_history(
        conversation_id: str,
        ctx: Context,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Retrieve the turn history for a conversation.

        Args:
            conversation_id: The conversation to retrieve.
            limit: Maximum number of turns to return (None for all).
        """
        container = _get_container(ctx)
        convo, turns = show_conversation.execute(
            convo_store=container.storage,
            conversation_id=conversation_id,
            limit=limit,
        )
        return {
            "conversation": _convo_to_dict(convo),
            "turns": [_turn_to_dict(t) for t in turns],
        }

    @mcp.tool()
    @track_tool
    async def conversation_ask(
        conversation_id: str,
        prompt: str,
        ctx: Context,
        moe: bool = False,
    ) -> dict[str, Any]:
        """Send a message through OpenChronicle's full pipeline.

        Routes through memory retrieval, privacy gate, provider selection,
        LLM call, turn persistence, and event logging. Non-streaming.

        Args:
            conversation_id: The conversation to continue.
            prompt: The user message to send.
            moe: Use Mixture-of-Experts consensus mode.
        """
        container = _get_container(ctx)
        turn = await ask_conversation.execute(
            convo_store=container.storage,
            storage=container.storage,
            memory_store=container.storage,
            llm=container.llm,
            emit_event=container.event_logger.append,
            conversation_id=conversation_id,
            prompt_text=prompt,
            interaction_router=container.interaction_router,
            router_policy=container.router_policy,
            allow_pii=False,
            privacy_gate=container.privacy_gate,
            privacy_settings=container.privacy_settings,
            moe=moe,
        )
        return _turn_to_dict(turn)
