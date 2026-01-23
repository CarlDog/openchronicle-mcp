from __future__ import annotations

from collections.abc import Callable

from openchronicle.core.application.routing.router_policy import RouterPolicy
from openchronicle.core.application.services.llm_execution import execute_with_route
from openchronicle.core.domain.models.conversation import Turn
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.llm_port import LLMPort, LLMProviderError
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort


async def execute(
    convo_store: ConversationStorePort,
    storage: StoragePort,
    memory_store: MemoryStorePort,
    llm: LLMPort,
    emit_event: Callable[[Event], None],
    conversation_id: str,
    prompt_text: str,
    *,
    last_n: int = 10,
    top_k_memory: int = 8,
    include_pinned_memory: bool = True,
    max_output_tokens: int = 512,
    temperature: float = 0.2,
) -> Turn:
    conversation = convo_store.get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation not found: {conversation_id}")

    prior_turns = convo_store.list_turns(conversation_id, limit=last_n)

    messages: list[dict[str, str]] = [{"role": "system", "content": "You are a helpful assistant."}]

    pinned_memory = memory_store.list_memory(limit=top_k_memory, pinned_only=True) if include_pinned_memory else []
    relevant_memory = memory_store.search_memory(
        prompt_text,
        top_k=top_k_memory,
        conversation_id=conversation_id,
        include_pinned=False,
    )

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="memory.retrieved",
            payload={
                "pinned_count": len(pinned_memory),
                "relevant_count": len(relevant_memory),
                "pinned_ids": [item.id for item in pinned_memory],
                "relevant_ids": [item.id for item in relevant_memory],
                "query_len": len(prompt_text),
                "top_k": top_k_memory,
                "include_pinned_memory": include_pinned_memory,
            },
        )
    )

    if pinned_memory or relevant_memory:
        memory_lines: list[str] = []
        if include_pinned_memory:
            memory_lines.append("Pinned memory:")
            for item in pinned_memory:
                content_snippet = item.content if len(item.content) <= 300 else item.content[:300] + "..."
                tags_str = ",".join(item.tags)
                memory_lines.append(f"- {item.id} | tags=[{tags_str}] | {content_snippet}")
            memory_lines.append("")

        memory_lines.append("Relevant memory:")
        for item in relevant_memory:
            content_snippet = item.content if len(item.content) <= 300 else item.content[:300] + "..."
            tags_str = ",".join(item.tags)
            memory_lines.append(f"- {item.id} | tags=[{tags_str}] | {content_snippet}")

        messages.append({"role": "system", "content": "\n".join(memory_lines)})
    for turn in prior_turns:
        messages.append({"role": "user", "content": turn.user_text})
        messages.append({"role": "assistant", "content": turn.assistant_text})
    messages.append({"role": "user", "content": prompt_text})

    router = RouterPolicy()
    route_decision = router.route(
        task_type="convo.ask",
        agent_role="user",
        agent_tags=None,
        desired_quality=None,
        provider_preference=None,
        current_task_tokens=None,
        max_tokens_per_task=None,
        rate_limit_triggered=False,
        rpm_limit=None,
    )

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="convo.turn_started",
            payload={"prompt_chars": len(prompt_text)},
        )
    )

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="llm.routed",
            payload={
                "provider": route_decision.provider,
                "model": route_decision.model,
                "reasons": route_decision.reasons,
            },
        )
    )

    try:
        response = await execute_with_route(
            llm,
            route_decision,
            messages,
            max_output_tokens=max_output_tokens,
            temperature=temperature,
        )
    except LLMProviderError as exc:
        emit_event(
            Event(
                project_id=conversation.project_id,
                task_id=conversation.id,
                type="convo.turn_failed",
                payload={"error_code": exc.error_code, "hint": exc.hint},
            )
        )
        raise

    assistant_text = response.content

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="llm.completed",
            payload={
                "provider": response.provider,
                "model": response.model,
                "request_id": response.request_id,
                "finish_reason": response.finish_reason,
                "latency_ms": response.latency_ms,
                "usage": {
                    "input_tokens": response.usage.input_tokens if response.usage else None,
                    "output_tokens": response.usage.output_tokens if response.usage else None,
                    "total_tokens": response.usage.total_tokens if response.usage else None,
                },
            },
        )
    )

    with storage.transaction():
        turn_index = convo_store.next_turn_index(conversation_id)
        turn = Turn(
            conversation_id=conversation_id,
            turn_index=turn_index,
            user_text=prompt_text,
            assistant_text=assistant_text,
            provider=route_decision.provider,
            model=route_decision.model,
            routing_reasons=route_decision.reasons,
        )
        convo_store.add_turn(turn)

    emit_event(
        Event(
            project_id=conversation.project_id,
            task_id=conversation.id,
            type="convo.turn_completed",
            payload={
                "turn_id": turn.id,
                "turn_index": turn.turn_index,
                "provider": turn.provider,
                "model": turn.model,
            },
        )
    )

    return turn
