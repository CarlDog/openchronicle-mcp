"""Use case: standalone context assembly for external agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openchronicle.core.application.services.embedding_service import EmbeddingService

from openchronicle.core.application.services.context_builder import (
    build_turn_messages,
    format_memory_messages,
    format_time_context,
)
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort


@dataclass
class RetrievedMemory:
    """A memory item included in the assembled context."""

    id: str
    content: str
    tags: list[str]
    pinned: bool
    source: str


@dataclass
class AssembledContext:
    """Context assembled from conversation history and memory retrieval."""

    conversation_id: str
    conversation_title: str
    conversation_mode: str
    messages: list[dict[str, str]]
    retrieved_memories: list[RetrievedMemory] = field(default_factory=list)
    prior_turn_count: int = 0
    last_interaction_at: str | None = None
    seconds_since_last_interaction: int | None = None


def _memory_item_to_retrieved(item: MemoryItem, *, pinned: bool) -> RetrievedMemory:
    return RetrievedMemory(
        id=item.id,
        content=item.content,
        tags=list(item.tags),
        pinned=pinned,
        source=item.source,
    )


def execute(
    convo_store: ConversationStorePort,
    memory_store: MemoryStorePort,
    conversation_id: str,
    prompt_text: str,
    *,
    last_n: int = 10,
    top_k_memory: int = 8,
    include_pinned_memory: bool = True,
    embedding_service: EmbeddingService | None = None,
) -> AssembledContext:
    """Assemble context for an external agent without routing or LLM calls.

    Returns messages ready to send to any LLM, plus metadata about the
    retrieved memories and conversation state.

    Pinned memories have a separate budget and do not reduce the search
    result count.  This prevents a large number of pinned items from
    crowding out query-relevant results.
    """
    conversation = convo_store.get_conversation(conversation_id)
    if conversation is None:
        raise NotFoundError(f"Conversation {conversation_id} not found")

    if not prompt_text or not prompt_text.strip():
        raise DomainValidationError("prompt must be non-empty")

    prior_turns = convo_store.list_turns(conversation_id, limit=last_n)

    # Build messages: system + memory + time + turns + prompt
    messages: list[dict[str, str]] = [{"role": "system", "content": "You are a helpful assistant."}]

    # Pinned memories have their own budget (not counted against top_k)
    pinned_memory = memory_store.list_memory(pinned_only=True) if include_pinned_memory else []
    if embedding_service is not None:
        relevant_memory = embedding_service.search_hybrid(
            prompt_text,
            top_k=top_k_memory,
            conversation_id=conversation_id,
            include_pinned=False,
        )
    else:
        relevant_memory = memory_store.search_memory(
            prompt_text,
            top_k=top_k_memory,
            conversation_id=conversation_id,
            include_pinned=False,
        )

    memory_text = format_memory_messages(pinned_memory, relevant_memory, include_pinned_memory)
    if memory_text is not None:
        messages.append({"role": "system", "content": memory_text})

    time_ctx_msg, ref_time, delta_seconds = format_time_context(prior_turns, conversation)
    messages.append({"role": "system", "content": time_ctx_msg})

    messages.extend(build_turn_messages(prior_turns, prompt_text))

    # Build retrieved memories list
    retrieved: list[RetrievedMemory] = []
    for item in pinned_memory:
        retrieved.append(_memory_item_to_retrieved(item, pinned=True))
    for item in relevant_memory:
        retrieved.append(_memory_item_to_retrieved(item, pinned=False))

    return AssembledContext(
        conversation_id=conversation_id,
        conversation_title=conversation.title or "",
        conversation_mode=conversation.mode or "general",
        messages=messages,
        retrieved_memories=retrieved,
        prior_turn_count=len(prior_turns),
        last_interaction_at=ref_time.isoformat(),
        seconds_since_last_interaction=delta_seconds,
    )
