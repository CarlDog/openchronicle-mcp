from __future__ import annotations

import asyncio
import json
import sys
from io import TextIOBase
from typing import TextIO

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import (
    ask_conversation,
    convo_mode,
    explain_turn,
    export_convo,
    show_conversation,
)
from openchronicle.core.domain.ports.llm_port import LLMProviderError
from openchronicle.core.domain.services.verification import VerificationResult, VerificationService


def json_error_payload(*, error_code: str | None, message: str, hint: str | None) -> dict[str, object]:
    return {
        "error_code": error_code,
        "message": message,
        "hint": hint,
    }


def json_envelope(
    *,
    command: str,
    ok: bool,
    result: dict[str, object] | None,
    error: dict[str, object] | None,
) -> dict[str, object]:
    return {
        "command": command,
        "ok": ok,
        "result": result,
        "error": error,
    }


def json_dumps_line(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True)


def coerce_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def dispatch_json_command(
    container: CoreContainer,
    command: str,
    args: dict[str, object],
) -> dict[str, object]:
    if command == "system.ping":
        return json_envelope(
            command=command,
            ok=True,
            result={"pong": True},
            error=None,
        )

    if command == "system.shutdown":
        return json_envelope(
            command=command,
            ok=True,
            result=None,
            error=None,
        )

    try:
        if command == "convo.export":
            conversation_id = str(args.get("conversation_id", ""))
            include_explain = bool(args.get("explain", False))
            include_verify = bool(args.get("verify", False))

            export = export_convo.execute(
                storage=container.storage,
                convo_store=container.storage,
                conversation_id=conversation_id,
                include_explain=include_explain,
                include_verify=include_verify,
            )

            ok = True
            if include_verify:
                verification = export.get("verification") if isinstance(export, dict) else None
                verification_dict = verification if isinstance(verification, dict) else {}
                ok = verification_dict.get("ok") is True

            return json_envelope(
                command=command,
                ok=ok,
                result=export,
                error=None
                if ok
                else json_error_payload(
                    error_code=None,
                    message="verification failed",
                    hint=None,
                ),
            )

        if command == "convo.verify":
            conversation_id = str(args.get("conversation_id", ""))
            verification_service = VerificationService(container.storage)
            convo_verify_result: VerificationResult = verification_service.verify_task_chain(conversation_id)

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

            return json_envelope(
                command=command,
                ok=convo_verify_result.success,
                result={
                    "conversation_id": conversation_id,
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

        if command == "convo.mode":
            conversation_id = str(args.get("conversation_id", ""))
            mode_value = args.get("mode")
            if isinstance(mode_value, str) and mode_value:
                conversation_mode = convo_mode.set_mode(
                    convo_store=container.storage,
                    conversation_id=conversation_id,
                    mode=mode_value,
                )
            else:
                conversation_mode = convo_mode.get_mode(
                    convo_store=container.storage,
                    conversation_id=conversation_id,
                )

            return json_envelope(
                command=command,
                ok=True,
                result={
                    "conversation_id": conversation_id,
                    "mode": conversation_mode,
                },
                error=None,
            )

        if command == "convo.show":
            conversation_id = str(args.get("conversation_id", ""))
            limit_raw = args.get("limit")
            limit_value = coerce_int(limit_raw, 0)
            limit: int | None = limit_value if limit_value > 0 else None
            include_explain = bool(args.get("explain", False))

            conversation, turns = show_conversation.execute(
                convo_store=container.storage,
                conversation_id=conversation_id,
                limit=limit,
            )

            turns_payload: list[dict[str, object]] = []
            for turn in turns:
                explain_payload: dict[str, object] | None = None
                if include_explain:
                    try:
                        explain_payload = explain_turn.execute(
                            storage=container.storage,
                            conversation_id=conversation_id,
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
                        "explain": explain_payload if include_explain else None,
                    }
                )

            return json_envelope(
                command=command,
                ok=True,
                result={
                    "conversation_id": conversation.id,
                    "mode": conversation.mode,
                    "turns": turns_payload,
                },
                error=None,
            )

        if command == "convo.ask":
            conversation_id = str(args.get("conversation_id", ""))
            prompt_text = str(args.get("prompt", ""))
            last_n = coerce_int(args.get("last_n"), 10)
            top_k_memory = coerce_int(args.get("top_k_memory"), 8)
            include_pinned_memory = bool(args.get("include_pinned_memory", True))
            include_explain = bool(args.get("explain", False))

            async def _run() -> dict[str, object]:
                turn = await ask_conversation.execute(
                    convo_store=container.storage,
                    storage=container.storage,
                    memory_store=container.storage,
                    llm=container.llm,
                    interaction_router=container.interaction_router,
                    emit_event=container.event_logger.append,
                    conversation_id=conversation_id,
                    prompt_text=prompt_text,
                    last_n=last_n,
                    top_k_memory=top_k_memory,
                    include_pinned_memory=include_pinned_memory,
                )

                explain_payload: dict[str, object] | None = None
                if include_explain:
                    try:
                        explain_payload = explain_turn.execute(
                            storage=container.storage,
                            conversation_id=conversation_id,
                            turn_id=turn.id,
                        )
                    except ValueError:
                        explain_payload = None
                return {
                    "conversation_id": turn.conversation_id,
                    "turn_id": turn.id,
                    "turn_index": turn.turn_index,
                    "assistant_text": turn.assistant_text,
                    "explain": explain_payload if include_explain else None,
                }

            result = asyncio.run(_run())
            return json_envelope(
                command=command,
                ok=True,
                result=result,
                error=None,
            )

        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="UNKNOWN_COMMAND",
                message=f"Unsupported command: {command}",
                hint=None,
            ),
        )
    except LLMProviderError as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=exc.error_code,
                message=str(exc),
                hint=exc.hint,
            ),
        )
    except ValueError as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=None,
                message=str(exc),
                hint=None,
            ),
        )
    except Exception as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code=None,
                message=str(exc),
                hint=None,
            ),
        )


def serve_stdio(
    container: CoreContainer,
    *,
    input_stream: TextIO | TextIOBase | None = None,
    output_stream: TextIO | TextIOBase | None = None,
) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    assert input_stream is not None
    assert output_stream is not None

    while True:
        line = input_stream.readline()
        if not line:
            break
        raw = line.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
        except json.JSONDecodeError as exc:
            payload = json_envelope(
                command="unknown",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code="INVALID_JSON",
                    message=str(exc),
                    hint=None,
                ),
            )
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        command = request.get("command") if isinstance(request, dict) else None
        args = request.get("args") if isinstance(request, dict) else None
        if not isinstance(command, str) or not isinstance(args, dict):
            payload = json_envelope(
                command=str(command) if command is not None else "unknown",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code="INVALID_REQUEST",
                    message="Request must include 'command' string and 'args' object",
                    hint=None,
                ),
            )
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        response = dispatch_json_command(container, command, args)
        output_stream.write(json_dumps_line(response) + "\n")
        output_stream.flush()
        if command == "system.shutdown":
            break
    return 0
