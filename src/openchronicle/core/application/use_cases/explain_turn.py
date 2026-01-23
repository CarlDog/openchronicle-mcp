from __future__ import annotations

from datetime import datetime

from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.storage_port import StoragePort


def execute(
    storage: StoragePort,
    *,
    conversation_id: str,
    turn_id: str,
) -> dict[str, object]:
    events = storage.list_events(task_id=conversation_id)

    completed_event = None
    for event in events:
        if event.type == "convo.turn_completed" and event.payload.get("turn_id") == turn_id:
            completed_event = event
            break

    if completed_event is None:
        raise ValueError(f"Turn completion event not found for turn_id: {turn_id}")

    cutoff = completed_event.created_at

    routed_event = _latest_event_before(events, "llm.routed", cutoff)
    memory_event = _latest_event_before(events, "memory.retrieved", cutoff)
    completed_llm_event = _latest_event_before(events, "llm.completed", cutoff)

    routed_payload = routed_event.payload if routed_event else {}
    memory_payload = memory_event.payload if memory_event else {}
    llm_payload = completed_llm_event.payload if completed_llm_event else {}

    usage_payload = llm_payload.get("usage") or {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }

    return {
        "turn_id": turn_id,
        "provider": routed_payload.get("provider"),
        "model": routed_payload.get("model"),
        "routing_reasons": routed_payload.get("reasons", [])
        if isinstance(routed_payload.get("reasons", []), list)
        else [],
        "memory": {
            "pinned_ids": memory_payload.get("pinned_ids", []) if memory_payload else [],
            "relevant_ids": memory_payload.get("relevant_ids", []) if memory_payload else [],
            "pinned_count": memory_payload.get("pinned_count", 0) if memory_payload else 0,
            "relevant_count": memory_payload.get("relevant_count", 0) if memory_payload else 0,
            "top_k": memory_payload.get("top_k") if memory_payload else None,
            "include_pinned_memory": memory_payload.get("include_pinned_memory") if memory_payload else None,
        },
        "llm": {
            "request_id": llm_payload.get("request_id") if llm_payload else None,
            "finish_reason": llm_payload.get("finish_reason") if llm_payload else None,
            "latency_ms": llm_payload.get("latency_ms") if llm_payload else None,
            "usage": usage_payload,
        },
    }


def _latest_event_before(events: list[Event], event_type: str, cutoff: datetime) -> Event | None:
    latest: Event | None = None
    for event in events:
        if event.type != event_type:
            continue
        if event.created_at > cutoff:
            continue
        if latest is None or (event.created_at, event.id) >= (latest.created_at, latest.id):
            latest = event
    return latest
