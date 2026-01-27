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
        if event.type != "convo.turn_completed":
            continue
        if event.payload.get("turn_id") != turn_id:
            continue
        if completed_event is None or (event.created_at, event.id) >= (completed_event.created_at, completed_event.id):
            completed_event = event

    if completed_event is None:
        raise ValueError(f"Turn completion event not found for turn_id: {turn_id}")

    cutoff = completed_event.created_at

    routed_event = _latest_event_before(events, "llm.routed", cutoff)
    memory_event = _latest_event_before(events, "memory.retrieved", cutoff)
    memory_used_event = _latest_event_before(events, "memory.used_reported", cutoff)
    completed_llm_event = _latest_event_before(events, "llm.completed", cutoff)
    privacy_override_event = _latest_event_before(events, "privacy.override_used", cutoff)
    privacy_checked_event = _latest_event_before(events, "privacy.outbound_checked", cutoff)

    memory_link_events = [
        event
        for event in events
        if event.type == "convo.turn_memory_linked"
        and event.created_at <= cutoff
        and event.payload.get("turn_id") == turn_id
    ]
    memory_link_events.sort(key=lambda e: (e.created_at, e.id))
    memory_written_ids: list[str] = []
    seen_memory_ids: set[str] = set()
    for event in memory_link_events:
        memory_id = event.payload.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id:
            continue
        if memory_id in seen_memory_ids:
            continue
        seen_memory_ids.add(memory_id)
        memory_written_ids.append(memory_id)

    routed_payload = routed_event.payload if routed_event else {}
    memory_payload = memory_event.payload if memory_event else {}
    memory_used_payload = memory_used_event.payload if memory_used_event else {}
    llm_payload = completed_llm_event.payload if completed_llm_event else {}
    privacy_override_used = bool(privacy_override_event)
    privacy_payload = privacy_checked_event.payload if privacy_checked_event else {}
    privacy_categories = privacy_payload.get("categories", []) if isinstance(privacy_payload, dict) else []
    privacy_counts = privacy_payload.get("counts", {}) if isinstance(privacy_payload, dict) else {}
    if not isinstance(privacy_categories, list):
        privacy_categories = []
    if not isinstance(privacy_counts, dict):
        privacy_counts = {}
    privacy_categories_sorted = sorted([c for c in privacy_categories if isinstance(c, str)])
    privacy_counts_sorted = {k: privacy_counts.get(k) for k in privacy_categories_sorted}
    privacy_effective_mode = privacy_payload.get("mode") if isinstance(privacy_payload, dict) else None
    privacy_external_only = privacy_payload.get("external_only") if isinstance(privacy_payload, dict) else None
    privacy_applies = privacy_payload.get("applies") if isinstance(privacy_payload, dict) else None
    privacy_redactions_applied = (
        privacy_payload.get("redactions_applied") if isinstance(privacy_payload, dict) else None
    )

    privacy_block = {
        "checked": bool(privacy_checked_event) and not privacy_override_used,
        "effective_mode": privacy_effective_mode if isinstance(privacy_effective_mode, str) else "off",
        "external_only": privacy_external_only if isinstance(privacy_external_only, bool) else False,
        "applies": privacy_applies if isinstance(privacy_applies, bool) else False,
        "override_allow_pii": privacy_override_used,
        "categories": privacy_categories_sorted if not privacy_override_used else [],
        "counts": privacy_counts_sorted if not privacy_override_used else {},
        "redactions_applied": privacy_redactions_applied if isinstance(privacy_redactions_applied, bool) else False,
    }
    if privacy_override_used:
        privacy_block["checked"] = False
        privacy_block["applies"] = False

    usage_payload = llm_payload.get("usage") or {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
    }
    used_ids_value = memory_used_payload.get("used_memory_ids") if isinstance(memory_used_payload, dict) else []
    if not isinstance(used_ids_value, list):
        used_ids_value = []
    memory_used_reported_ids = [value for value in used_ids_value if isinstance(value, str)]
    retrieved_count = 0
    pinned_count_value = memory_payload.get("pinned_count", 0) if memory_payload else 0
    relevant_count_value = memory_payload.get("relevant_count", 0) if memory_payload else 0
    if isinstance(pinned_count_value, int):
        retrieved_count += pinned_count_value
    if isinstance(relevant_count_value, int):
        retrieved_count += relevant_count_value
    used_rate = None
    if retrieved_count > 0:
        used_rate = len(memory_used_reported_ids) / retrieved_count

    return {
        "turn_id": turn_id,
        "provider": routed_payload.get("provider"),
        "model": routed_payload.get("model"),
        "memory_written_ids": memory_written_ids,
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
            "memory_used_reported_ids": memory_used_reported_ids,
            "used_rate": used_rate,
        },
        "llm": {
            "request_id": llm_payload.get("request_id") if llm_payload else None,
            "finish_reason": llm_payload.get("finish_reason") if llm_payload else None,
            "latency_ms": llm_payload.get("latency_ms") if llm_payload else None,
            "usage": usage_payload,
        },
        "privacy_override_used": privacy_override_used,
        "privacy": privacy_block,
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
