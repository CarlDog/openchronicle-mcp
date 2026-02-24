from __future__ import annotations

from openchronicle.core.domain.errors.error_codes import CONVERSATION_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort


def execute(
    convo_store: ConversationStorePort,
    conversation_id: str,
    limit: int | None = None,
) -> tuple[Conversation, list[Turn]]:
    conversation = convo_store.get_conversation(conversation_id)
    if conversation is None:
        raise NotFoundError(f"Conversation not found: {conversation_id}", code=CONVERSATION_NOT_FOUND)

    turns = convo_store.list_turns(conversation_id, limit=limit)
    return conversation, turns
