from __future__ import annotations

from openchronicle.core.domain.models.conversation import Conversation
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort


def execute(convo_store: ConversationStorePort, limit: int | None = None) -> list[Conversation]:
    return convo_store.list_conversations(limit=limit)
