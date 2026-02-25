"""Use case: record a conversation turn from an external agent."""

from __future__ import annotations

import logging
from collections.abc import Callable

from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.conversation import Turn
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort

_logger = logging.getLogger(__name__)


def execute(
    convo_store: ConversationStorePort,
    storage: StoragePort,
    emit_event: Callable[[Event], None],
    conversation_id: str,
    user_text: str,
    assistant_text: str,
    *,
    provider: str = "external",
    model: str = "",
) -> Turn:
    """Record a turn that was produced outside OC's LLM pipeline.

    External agents (Claude Code, Goose, IDE plugins) can use this to feed
    their conversation data into OC, improving memory retrieval quality
    without requiring an OC-managed LLM call.
    """
    convo = convo_store.get_conversation(conversation_id)
    if convo is None:
        raise NotFoundError(f"Conversation {conversation_id} not found")

    if not user_text or not user_text.strip():
        raise DomainValidationError("user_text must be non-empty")
    if not assistant_text or not assistant_text.strip():
        raise DomainValidationError("assistant_text must be non-empty")

    with storage.transaction():
        turn_index = convo_store.next_turn_index(conversation_id)
        turn = Turn(
            conversation_id=conversation_id,
            turn_index=turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
            provider=provider,
            model=model,
            routing_reasons=["external"],
        )
        convo_store.add_turn(turn)

    _logger.info(
        "Recorded external turn %d in conversation %s (provider=%s)",
        turn_index,
        conversation_id,
        provider,
    )

    emit_event(
        Event(
            project_id=convo.project_id,
            task_id=convo.id,
            type="convo.turn_recorded",
            payload={
                "turn_id": turn.id,
                "turn_index": turn.turn_index,
                "provider": turn.provider,
                "model": turn.model,
            },
        )
    )

    return turn
