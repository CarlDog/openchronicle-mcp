"""Conversation CLI commands: convo new/show/export/verify/mode/list/remember/ask."""

from __future__ import annotations

import argparse
import asyncio

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import (
    ask_conversation,
    convo_mode,
    create_conversation,
    explain_turn,
    export_convo,
    list_conversations,
    remember_turn,
    show_conversation,
)
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.services.verification import VerificationResult, VerificationService

from ._helpers import json_envelope, json_error_payload, print_json


def _resolve_latest(container: CoreContainer) -> str | None:
    """Return the most recent conversation ID, or None if none exist."""
    convos = container.storage.list_conversations(limit=1)
    if not convos:
        return None
    return convos[0].id


def _resolve_convo_id(args: argparse.Namespace, container: CoreContainer) -> str | None:
    """Resolve conversation_id from args, supporting --latest.

    Returns the resolved ID, or None if resolution fails (error already printed).
    """
    if getattr(args, "latest", False):
        convo_id = _resolve_latest(container)
        if convo_id is None:
            print("No conversations found. Create one with: oc convo new")
            return None
        return convo_id
    if args.conversation_id:
        return str(args.conversation_id)
    print("conversation_id is required (or use --latest)")
    return None


def cmd_convo(args: argparse.Namespace, container: CoreContainer) -> int:
    """Dispatch to convo subcommands."""
    from collections.abc import Callable

    convo_dispatch: dict[str, Callable[[argparse.Namespace, CoreContainer], int]] = {
        "new": cmd_convo_new,
        "show": cmd_convo_show,
        "export": cmd_convo_export,
        "verify": cmd_convo_verify,
        "mode": cmd_convo_mode,
        "list": cmd_convo_list,
        "remember": cmd_convo_remember,
        "ask": cmd_convo_ask,
        "delete": cmd_convo_delete,
    }
    handler = convo_dispatch.get(args.convo_command)
    if handler is None:
        print("Usage: oc convo <subcommand>")
        return 1
    return handler(args, container)


def cmd_convo_new(args: argparse.Namespace, container: CoreContainer) -> int:
    conversation = create_conversation.execute(
        storage=container.storage,
        convo_store=container.storage,
        emit_event=container.event_logger.append,
        title=args.title,
    )
    print(conversation.id)
    return 0


def cmd_convo_show(args: argparse.Namespace, container: CoreContainer) -> int:
    resolved = _resolve_convo_id(args, container)
    if resolved is None:
        return 1
    args.conversation_id = resolved
    try:
        conversation, turns = show_conversation.execute(
            convo_store=container.storage,
            conversation_id=args.conversation_id,
            limit=args.limit,
        )
    except ValueError as exc:
        if args.json:
            payload = json_envelope(
                command="convo.show",
                ok=False,
                result=None,
                error=json_error_payload(error_code=None, message=str(exc), hint=None),
            )
            print_json(payload)
            return 1
        print(str(exc))
        return 1

    if args.json:
        turns_payload: list[dict[str, object]] = []
        for turn in turns:
            explain_payload: dict[str, object] | None = None
            if args.explain:
                try:
                    explain_payload = explain_turn.execute(
                        storage=container.storage,
                        conversation_id=args.conversation_id,
                        turn_id=turn.id,
                    )
                except ValueError:
                    explain_payload = None
            turns_payload.append(
                {
                    "turn_id": turn.id,
                    "turn_index": turn.turn_index,
                    "user_text": turn.user_text,
                    "assistant_text": turn.assistant_text,
                    "explain": explain_payload if args.explain else None,
                }
            )

        payload = json_envelope(
            command="convo.show",
            ok=True,
            result={
                "conversation_id": conversation.id,
                "mode": conversation.mode,
                "turns": turns_payload,
            },
            error=None,
        )
        print_json(payload)
        return 0

    for turn in turns:
        if not args.explain:
            print(f"{turn.turn_index}\t{turn.user_text}\t{turn.assistant_text}")
            continue

        print(f"Turn {turn.turn_index}:")
        print(f"user: {turn.user_text}")
        print(f"assistant: {turn.assistant_text}")

        try:
            explain = explain_turn.execute(
                storage=container.storage,
                conversation_id=args.conversation_id,
                turn_id=turn.id,
            )
        except ValueError:
            print("EXPLAIN")
            print("unavailable: missing events")
            continue

        _print_explain(explain)
    return 0


def cmd_convo_export(args: argparse.Namespace, container: CoreContainer) -> int:
    resolved = _resolve_convo_id(args, container)
    if resolved is None:
        return 1
    args.conversation_id = resolved
    try:
        export = export_convo.execute(
            storage=container.storage,
            convo_store=container.storage,
            conversation_id=args.conversation_id,
            include_explain=args.explain,
            include_verify=args.verify,
        )
    except ValueError as exc:
        if args.json:
            payload = json_envelope(
                command="convo.export",
                ok=False,
                result=None,
                error=json_error_payload(error_code=None, message=str(exc), hint=None),
            )
            print_json(payload)
            return 1
        print(str(exc))
        return 1

    import json

    if args.json:
        ok = True
        if args.verify:
            verification = export.get("verification") if isinstance(export, dict) else None
            verification_dict = verification if isinstance(verification, dict) else {}
            ok = verification_dict.get("ok") is True

        payload = json_envelope(
            command="convo.export",
            ok=ok,
            result=export,
            error=None if ok else json_error_payload(error_code=None, message="verification failed", hint=None),
        )
        print_json(payload)
        if args.verify and args.fail_on_verify and not ok:
            return 1
        return 0

    print(json.dumps(export, sort_keys=True, indent=2))
    if args.verify and args.fail_on_verify:
        verification = export.get("verification") if isinstance(export, dict) else None
        verification_dict = verification if isinstance(verification, dict) else {}
        if verification_dict.get("ok") is not True:
            return 1
    return 0


def cmd_convo_verify(args: argparse.Namespace, container: CoreContainer) -> int:
    verification_service = VerificationService(container.storage)
    convo_verify_result: VerificationResult = verification_service.verify_task_chain(args.conversation_id)
    if args.json:
        first_mismatch = convo_verify_result.first_mismatch or {}
        expected_hash = first_mismatch.get("expected_hash")
        actual_hash = first_mismatch.get("computed_hash")
        if expected_hash is None and actual_hash is None:
            expected_hash = first_mismatch.get("expected_prev_hash")
            actual_hash = first_mismatch.get("actual_prev_hash")
        verification_payload = {
            "ok": convo_verify_result.success,
            "failure_event_id": first_mismatch.get("event_id"),
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }
        payload = json_envelope(
            command="convo.verify",
            ok=convo_verify_result.success,
            result={
                "conversation_id": args.conversation_id,
                "verification": verification_payload,
            },
            error=None
            if convo_verify_result.success
            else json_error_payload(
                error_code=None,
                message=convo_verify_result.error_message or "verification failed",
                hint=None,
            ),
        )
        print_json(payload)
        return 0 if convo_verify_result.success else 1

    if convo_verify_result.success:
        print("OK")
        return 0

    error_message = convo_verify_result.error_message or "verification failed"
    print(f"FAIL: {error_message}")

    first_mismatch = convo_verify_result.first_mismatch or {}
    event_id = first_mismatch.get("event_id")
    if event_id:
        print(f"event_id: {event_id}")

    expected_hash = first_mismatch.get("expected_hash")
    actual_hash = first_mismatch.get("computed_hash")
    if expected_hash is None and actual_hash is None:
        expected_hash = first_mismatch.get("expected_prev_hash")
        actual_hash = first_mismatch.get("actual_prev_hash")
    if expected_hash is not None or actual_hash is not None:
        print(f"expected_hash: {'' if expected_hash is None else expected_hash}")
        print(f"actual_hash: {'' if actual_hash is None else actual_hash}")

    print(f"hint: run oc replay-task {args.conversation_id} --mode verify or oc diagnose")
    return 1


def cmd_convo_mode(args: argparse.Namespace, container: CoreContainer) -> int:
    try:
        if args.mode is None:
            conversation_mode = convo_mode.get_mode(
                convo_store=container.storage,
                conversation_id=args.conversation_id,
            )
        else:
            conversation_mode = convo_mode.set_mode(
                convo_store=container.storage,
                conversation_id=args.conversation_id,
                mode=args.mode,
            )
    except ValueError as exc:
        if args.json:
            payload = json_envelope(
                command="convo.mode",
                ok=False,
                result=None,
                error=json_error_payload(error_code=None, message=str(exc), hint=None),
            )
            print_json(payload)
            return 1
        print(str(exc))
        return 1

    if args.json:
        payload = json_envelope(
            command="convo.mode",
            ok=True,
            result={
                "conversation_id": args.conversation_id,
                "mode": conversation_mode,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(conversation_mode)
    return 0


def cmd_convo_list(args: argparse.Namespace, container: CoreContainer) -> int:
    conversations = list_conversations.execute(convo_store=container.storage, limit=args.limit)
    for conversation in conversations:
        print(f"{conversation.id}\t{conversation.title}\t{conversation.created_at.isoformat()}")
    return 0


def cmd_convo_delete(args: argparse.Namespace, container: CoreContainer) -> int:
    """Delete a conversation and all related data."""
    if not args.force:
        if args.json:
            payload = json_envelope(
                command="convo.delete",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code=None,
                    message="--force flag is required for destructive delete",
                    hint="This permanently removes the conversation, its turns, memory items, and events.",
                ),
            )
            print_json(payload)
            return 1
        print("Error: --force flag is required for destructive delete.")
        print("This permanently removes the conversation, its turns, memory items, and events.")
        return 1

    # Verify exists
    conversation = container.storage.get_conversation(args.conversation_id)
    if conversation is None:
        if args.json:
            payload = json_envelope(
                command="convo.delete",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code=None, message=f"Conversation not found: {args.conversation_id}", hint=None
                ),
            )
            print_json(payload)
            return 1
        print(f"Conversation not found: {args.conversation_id}")
        return 1

    rows_deleted = container.storage.delete_conversation(args.conversation_id)

    if args.json:
        payload = json_envelope(
            command="convo.delete",
            ok=True,
            result={
                "conversation_id": args.conversation_id,
                "rows_deleted": rows_deleted,
            },
            error=None,
        )
        print_json(payload)
        return 0

    print(f"Deleted conversation {args.conversation_id} ({rows_deleted} rows)")
    return 0


def cmd_convo_remember(args: argparse.Namespace, container: CoreContainer) -> int:
    tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]
    item = remember_turn.execute(
        storage=container.storage,
        convo_store=container.storage,
        memory_store=container.storage,
        emit_event=container.event_logger.append,
        conversation_id=args.conversation_id,
        turn_index=args.turn_index,
        which=args.which,
        tags=tags,
        pinned=args.pin,
        source=args.source,
    )
    print(item.id)
    return 0


def cmd_convo_ask(args: argparse.Namespace, container: CoreContainer) -> int:
    # Handle positional ambiguity: `oc convo ask --latest "hello"` puts "hello" in conversation_id
    if getattr(args, "latest", False) and args.prompt is None and args.conversation_id is not None:
        args.prompt = args.conversation_id
        args.conversation_id = None
    resolved = _resolve_convo_id(args, container)
    if resolved is None:
        return 1
    args.conversation_id = resolved
    if not args.prompt:
        print("prompt is required")
        return 1

    async def _run_ask() -> int:
        try:
            turn = await ask_conversation.execute(
                convo_store=container.storage,
                storage=container.storage,
                memory_store=container.storage,
                llm=container.llm,
                interaction_router=container.interaction_router,
                emit_event=container.event_logger.append,
                conversation_id=args.conversation_id,
                prompt_text=args.prompt,
                last_n=args.last_n,
                top_k_memory=args.top_k_memory,
                include_pinned_memory=args.include_pinned_memory,
                allow_pii=args.allow_pii,
                privacy_gate=getattr(container, "privacy_gate", None),
                privacy_settings=getattr(container, "privacy_settings", None),
            )
        except (ValueError, LLMProviderError) as exc:
            if (
                isinstance(exc, LLMProviderError)
                and args.enqueue_if_unavailable
                and ask_conversation.is_enqueueable_provider_failure(exc.error_code)
            ):
                try:
                    task = ask_conversation.enqueue(
                        orchestrator=container.orchestrator,
                        convo_store=container.storage,
                        conversation_id=args.conversation_id,
                        prompt_text=args.prompt,
                        include_explain=args.explain,
                        allow_pii=args.allow_pii,
                        metadata=None,
                        interaction_router=container.interaction_router,
                        emit_event=container.event_logger.append,
                    )
                except (ValueError, LLMProviderError) as enqueue_exc:
                    exc = enqueue_exc
                else:
                    if args.json:
                        payload = json_envelope(
                            command="convo.ask",
                            ok=True,
                            result={
                                "conversation_id": args.conversation_id,
                                "status": "queued",
                                "task_id": task.id,
                                "reason_code": exc.error_code,
                            },
                            error=None,
                        )
                        print_json(payload)
                        return 0
                    print(f"queued: {task.id}")
                    return 0

            if not args.json:
                print(str(exc))
                return 1

            error_code = exc.error_code if isinstance(exc, LLMProviderError) else None
            hint = exc.hint if isinstance(exc, LLMProviderError) else None
            payload = json_envelope(
                command="convo.ask",
                ok=False,
                result=None,
                error=json_error_payload(error_code=error_code, message=str(exc), hint=hint),
            )
            print_json(payload)
            return 1

        if args.json:
            explain_payload: dict[str, object] | None = None
            if args.explain:
                try:
                    explain_payload = explain_turn.execute(
                        storage=container.storage,
                        conversation_id=args.conversation_id,
                        turn_id=turn.id,
                    )
                except ValueError:
                    explain_payload = None
            payload = json_envelope(
                command="convo.ask",
                ok=True,
                result={
                    "conversation_id": turn.conversation_id,
                    "turn_id": turn.id,
                    "turn_index": turn.turn_index,
                    "assistant_text": turn.assistant_text,
                    "explain": explain_payload if args.explain else None,
                },
                error=None,
            )
            print_json(payload)
            return 0

        print(turn.assistant_text)

        if args.explain:
            explain = explain_turn.execute(
                storage=container.storage,
                conversation_id=args.conversation_id,
                turn_id=turn.id,
            )
            print()
            _print_explain(explain)
        return 0

    return asyncio.run(_run_ask())


def _print_explain(explain: dict[str, object]) -> None:
    """Print explain block for a conversation turn."""
    reasons = explain.get("routing_reasons", [])
    reasons_str = ",".join(reasons) if isinstance(reasons, list) else ""
    memory_info = explain.get("memory")
    memory_dict = memory_info if isinstance(memory_info, dict) else {}
    pinned_ids = memory_dict.get("pinned_ids", []) if isinstance(memory_dict, dict) else []
    relevant_ids = memory_dict.get("relevant_ids", []) if isinstance(memory_dict, dict) else []
    pinned_str = ",".join(pinned_ids) if isinstance(pinned_ids, list) else ""
    relevant_str = ",".join(relevant_ids) if isinstance(relevant_ids, list) else ""
    memory_written_ids = explain.get("memory_written_ids", [])
    memory_written_str = ",".join(memory_written_ids) if isinstance(memory_written_ids, list) else ""
    llm_info = explain.get("llm")
    llm_dict = llm_info if isinstance(llm_info, dict) else {}
    usage_info = llm_dict.get("usage") if isinstance(llm_dict, dict) else {}
    usage_dict = usage_info if isinstance(usage_info, dict) else {}
    usage_in = usage_dict.get("input_tokens")
    usage_out = usage_dict.get("output_tokens")
    usage_total = usage_dict.get("total_tokens")
    latency_ms = llm_dict.get("latency_ms")
    finish_reason = llm_dict.get("finish_reason")

    print("EXPLAIN")
    print(f"provider: {explain.get('provider') or ''}")
    print(f"model: {explain.get('model') or ''}")
    print(f"reasons: {reasons_str}")
    print(f"pinned_memory_ids: {pinned_str}")
    print(f"relevant_memory_ids: {relevant_str}")
    print(f"memory_written_ids: {memory_written_str}")
    print(
        "usage: "
        f"in={'' if usage_in is None else usage_in} "
        f"out={'' if usage_out is None else usage_out} "
        f"total={'' if usage_total is None else usage_total} "
        f"latency_ms={'' if latency_ms is None else latency_ms} "
        f"finish_reason={'' if finish_reason is None else finish_reason}"
    )
