from __future__ import annotations

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort

ALLOWED_CONVERSATION_MODES = ("general", "persona", "story")


def get_mode(convo_store: ConversationStorePort, conversation_id: str) -> str:
    mode = convo_store.get_conversation_mode(conversation_id)
    return mode or "general"


def set_mode(convo_store: ConversationStorePort, conversation_id: str, mode: str) -> str:
    normalized = (mode or "").strip().lower()
    if normalized not in ALLOWED_CONVERSATION_MODES:
        allowed = ", ".join(ALLOWED_CONVERSATION_MODES)
        raise DomainValidationError(f"Invalid conversation mode: {mode}. Allowed: {allowed}.")

    convo_store.set_conversation_mode(conversation_id, normalized)
    return normalized
