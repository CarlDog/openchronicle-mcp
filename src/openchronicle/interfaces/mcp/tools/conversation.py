"""Conversation tools — create, list, history, ask."""

from __future__ import annotations

from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from openchronicle.core.application.use_cases import (
    ask_conversation,
    convo_mode,
    create_conversation,
    external_turn,
    list_conversations,
    show_conversation,
)
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.mcp.tracking import track_tool
from openchronicle.interfaces.serializers import conversation_to_dict, turn_to_dict


def _get_container(ctx: Context) -> CoreContainer:
    return cast(CoreContainer, ctx.request_context.lifespan_context["container"])


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
            emit_event=container.emit_event,
            title=title,
        )
        return conversation_to_dict(convo)

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
        return [conversation_to_dict(c) for c in convos]

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
            "conversation": conversation_to_dict(convo),
            "turns": [turn_to_dict(t) for t in turns],
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
        if not prompt or not prompt.strip():
            raise DomainValidationError("prompt must be non-empty")
        if len(prompt) > 200_000:
            raise DomainValidationError("prompt exceeds maximum length of 200,000 characters")
        container = _get_container(ctx)
        turn = await ask_conversation.execute(
            convo_store=container.storage,
            storage=container.storage,
            memory_store=container.storage,
            llm=container.llm,
            emit_event=container.emit_event,
            conversation_id=conversation_id,
            prompt_text=prompt,
            interaction_router=container.interaction_router,
            router_policy=container.router_policy,
            allow_pii=False,
            privacy_gate=container.privacy_gate,
            privacy_settings=container.privacy_settings,
            moe=moe,
            mode_prompt_builders=container.plugin_loader.registry_instance().mode_prompt_builders(),
        )
        return turn_to_dict(turn)

    @mcp.tool()
    @track_tool
    def conversation_set_mode(
        conversation_id: str,
        mode: str,
        ctx: Context,
    ) -> dict[str, Any]:
        """Set the conversation mode.

        Mode controls which plugin's mode prompt builder fires during
        ``conversation_ask``. Valid modes: ``general`` (default, no plugin
        builder), ``persona``, ``story`` (storytelling plugin assembles
        characters/locations/style guides from project memory).

        Args:
            conversation_id: The conversation to update.
            mode: One of ``general``, ``persona``, ``story``.
        """
        container = _get_container(ctx)
        normalized = convo_mode.set_mode(container.storage, conversation_id, mode=mode)
        return {"conversation_id": conversation_id, "mode": normalized}

    @mcp.tool()
    @track_tool
    def conversation_get_mode(
        conversation_id: str,
        ctx: Context,
    ) -> dict[str, Any]:
        """Get the current conversation mode.

        Args:
            conversation_id: The conversation to inspect.
        """
        container = _get_container(ctx)
        mode = convo_mode.get_mode(container.storage, conversation_id)
        return {"conversation_id": conversation_id, "mode": mode}

    @mcp.tool()
    @track_tool
    def turn_record(
        conversation_id: str,
        user_text: str,
        assistant_text: str,
        ctx: Context,
        provider: str = "external",
        model: str = "",
    ) -> dict[str, Any]:
        """Record a conversation turn from an external agent.

        Lets MCP callers record turns that didn't go through OC's LLM
        pipeline. More data flowing in → better memory retrieval → better
        context in future interactions.

        Args:
            conversation_id: The conversation to add the turn to.
            user_text: The user message text.
            assistant_text: The assistant response text.
            provider: Provider name (default: "external").
            model: Model name (default: empty).
        """
        if not user_text or not user_text.strip():
            raise DomainValidationError("user_text must be non-empty")
        if len(user_text) > 200_000:
            raise DomainValidationError("user_text exceeds maximum length of 200,000 characters")
        if not assistant_text or not assistant_text.strip():
            raise DomainValidationError("assistant_text must be non-empty")
        if len(assistant_text) > 200_000:
            raise DomainValidationError("assistant_text exceeds maximum length of 200,000 characters")
        container = _get_container(ctx)
        turn = external_turn.execute(
            convo_store=container.storage,
            storage=container.storage,
            emit_event=container.emit_event,
            conversation_id=conversation_id,
            user_text=user_text,
            assistant_text=assistant_text,
            provider=provider,
            model=model,
        )
        return turn_to_dict(turn)
