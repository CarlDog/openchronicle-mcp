"""Conversation routes — create, list, history, ask, context."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from openchronicle.core.application.use_cases import (
    ask_conversation,
    create_conversation,
    list_conversations,
    search_memory,
    show_conversation,
)
from openchronicle.core.infrastructure.wiring.container import CoreContainer
from openchronicle.interfaces.api.deps import get_container
from openchronicle.interfaces.serializers import conversation_to_dict, memory_to_dict, turn_to_dict

router = APIRouter(prefix="/conversation")

ContainerDep = Annotated[CoreContainer, Depends(get_container)]


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=500)


@router.post("")
def conversation_create(
    body: ConversationCreateRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Create a new conversation."""
    convo = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title=body.title,
    )
    return conversation_to_dict(convo)


@router.get("")
def conversation_list(
    container: ContainerDep,
    limit: int | None = Query(default=None, ge=1, le=10_000),
) -> list[dict[str, Any]]:
    """List conversations, most recent first."""
    convos = list_conversations.execute(
        convo_store=container.storage,
        limit=limit,
    )
    return [conversation_to_dict(c) for c in convos]


@router.get("/{conversation_id}/history")
def conversation_history(
    conversation_id: str,
    container: ContainerDep,
    limit: int | None = Query(default=None, ge=1, le=10_000),
) -> dict[str, Any]:
    """Retrieve the turn history for a conversation."""
    convo, turns = show_conversation.execute(
        convo_store=container.storage,
        conversation_id=conversation_id,
        limit=limit,
    )
    return {
        "conversation": conversation_to_dict(convo),
        "turns": [turn_to_dict(t) for t in turns],
    }


class ConversationAskRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=200_000)
    moe: bool = False


@router.post("/{conversation_id}/ask")
async def conversation_ask(
    conversation_id: str,
    body: ConversationAskRequest,
    container: ContainerDep,
) -> dict[str, Any]:
    """Send a message through the full OC pipeline. Non-streaming."""
    turn = await ask_conversation.execute(
        convo_store=container.storage,
        storage=container.storage,
        memory_store=container.storage,
        llm=container.llm,
        emit_event=container.event_logger.append,
        conversation_id=conversation_id,
        prompt_text=body.prompt,
        interaction_router=container.interaction_router,
        router_policy=container.router_policy,
        allow_pii=False,
        privacy_gate=container.privacy_gate,
        privacy_settings=container.privacy_settings,
        moe=body.moe,
    )
    return turn_to_dict(turn)


@router.get("/{conversation_id}/context")
def context_recent(
    conversation_id: str,
    container: ContainerDep,
    query: str | None = None,
    turn_limit: int = Query(default=5, ge=1, le=1000),
    memory_limit: int = Query(default=5, ge=1, le=1000),
) -> dict[str, Any]:
    """Get recent context: conversation turns + relevant memories."""
    result: dict[str, Any] = {}

    convo, turns = show_conversation.execute(
        convo_store=container.storage,
        conversation_id=conversation_id,
        limit=turn_limit,
    )
    result["conversation"] = {
        "id": convo.id,
        "title": convo.title,
        "mode": convo.mode,
    }
    result["recent_turns"] = [
        {
            "turn_index": t.turn_index,
            "user_text": t.user_text,
            "assistant_text": t.assistant_text,
            "created_at": t.created_at.isoformat(),
        }
        for t in turns
    ]

    if query:
        memories = search_memory.execute(
            store=container.storage,
            query=query,
            top_k=memory_limit,
            conversation_id=conversation_id,
        )
        result["memories"] = [memory_to_dict(m) for m in memories]

    return result
