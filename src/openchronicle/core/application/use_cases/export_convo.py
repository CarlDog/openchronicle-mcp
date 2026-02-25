from __future__ import annotations

import logging

from openchronicle.core.application.use_cases import explain_turn
from openchronicle.core.domain.errors.error_codes import CONVERSATION_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.domain.services.verification import VerificationService

_logger = logging.getLogger(__name__)


def execute(
    *,
    storage: StoragePort,
    convo_store: ConversationStorePort,
    conversation_id: str,
    include_explain: bool = False,
    include_verify: bool = False,
) -> dict[str, object]:
    conversation = convo_store.get_conversation(conversation_id)
    if conversation is None:
        raise NotFoundError(f"Conversation not found: {conversation_id}", code=CONVERSATION_NOT_FOUND)

    turns = convo_store.list_turns(conversation_id)

    export: dict[str, object] = {
        "format_version": "1",
        "conversation": {
            "id": conversation.id,
            "project_id": conversation.project_id,
            "title": conversation.title,
            "mode": conversation.mode,
            "created_at": conversation.created_at.isoformat(),
        },
        "turns": [],
    }

    if include_verify:
        verifier = VerificationService(storage)
        try:
            verification_result = verifier.verify_task_chain(conversation_id)
            first_mismatch = verification_result.first_mismatch or {}
            expected_hash = first_mismatch.get("expected_hash")
            actual_hash = first_mismatch.get("computed_hash")
            if expected_hash is None and actual_hash is None:
                expected_hash = first_mismatch.get("expected_prev_hash")
                actual_hash = first_mismatch.get("actual_prev_hash")
            export["verification"] = {
                "ok": verification_result.success,
                "failure_event_id": first_mismatch.get("event_id"),
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            }
        except Exception:
            _logger.exception("Verification failed for conversation %s", conversation_id)
            export["verification"] = {
                "ok": False,
                "failure_event_id": None,
                "expected_hash": None,
                "actual_hash": None,
            }

    exported_turns: list[dict[str, object]] = []
    for turn in turns:
        turn_entry: dict[str, object] = {
            "id": turn.id,
            "turn_index": turn.turn_index,
            "user_text": turn.user_text,
            "assistant_text": turn.assistant_text,
            "provider": turn.provider,
            "model": turn.model,
            "routing_reasons": list(turn.routing_reasons),
            "memory_written_ids": list(turn.memory_written_ids),
            "created_at": turn.created_at.isoformat(),
        }

        if include_explain:
            try:
                turn_entry["explain"] = explain_turn.execute(
                    storage=storage,
                    conversation_id=conversation_id,
                    turn_id=turn.id,
                )
            except (ValueError, NotFoundError):
                turn_entry["explain"] = {"unavailable": True}

        exported_turns.append(turn_entry)

    export["turns"] = exported_turns
    return export
