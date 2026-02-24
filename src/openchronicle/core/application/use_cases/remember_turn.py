from __future__ import annotations

from collections.abc import Callable

from openchronicle.core.application.use_cases import add_memory
from openchronicle.core.domain.errors.error_codes import CONVERSATION_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort


def execute(
    *,
    storage: StoragePort,
    convo_store: ConversationStorePort,
    memory_store: MemoryStorePort,
    emit_event: Callable[[Event], None],
    conversation_id: str,
    turn_index: int,
    which: str,
    tags: list[str],
    pinned: bool,
    source: str = "turn",
) -> MemoryItem:
    conversation = convo_store.get_conversation(conversation_id)
    if conversation is None:
        raise NotFoundError(f"Conversation not found: {conversation_id}", code=CONVERSATION_NOT_FOUND)

    turn = convo_store.get_turn_by_index(conversation_id, turn_index)
    if turn is None:
        raise NotFoundError(f"Turn not found: conversation={conversation_id} index={turn_index}")

    if which == "user":
        content = turn.user_text
    elif which == "assistant":
        content = turn.assistant_text
    else:
        raise DomainValidationError("which must be 'user' or 'assistant'")

    item = MemoryItem(
        content=content,
        tags=tags,
        pinned=pinned,
        conversation_id=conversation.id,
        project_id=conversation.project_id,
        source=source,
    )

    memory_item = add_memory.execute(store=memory_store, emit_event=emit_event, item=item)
    convo_store.link_memory_to_turn(turn.id, memory_item.id)

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="convo.turn_memory_linked",
            payload={
                "turn_id": turn.id,
                "turn_index": turn.turn_index,
                "memory_id": memory_item.id,
                "which": which,
            },
        )
    )

    return memory_item
