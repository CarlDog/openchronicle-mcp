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
from openchronicle.core.domain.services.verification import VerificationResult, VerificationService

STDIO_RPC_PROTOCOL_VERSION = "1"
SUPPORTED_COMMANDS: tuple[str, ...] = (
    "convo.ask",
    "convo.export",
    "convo.mode",
    "convo.show",
    "convo.verify",
    "system.commands",
    "system.info",
    "system.ping",
    "system.shutdown",
)


def json_error_payload(
    *,
    error_code: str | None,
    message: str,
    hint: str | None,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "error_code": error_code,
        "message": message,
        "hint": hint,
        "details": details,
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


def _sanitize_details(details: dict[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in details.items():
        key_lower = key.lower()
        if "prompt" in key_lower or "user_text" in key_lower or "assistant_text" in key_lower:
            continue
        sanitized[key] = value
    return sanitized


def _normalize_error(exc: Exception) -> dict[str, object]:
    if hasattr(exc, "error_code") or hasattr(exc, "hint"):
        error_code = getattr(exc, "error_code", None)
        hint = getattr(exc, "hint", None)
        details: dict[str, object] = {}

        configured_providers = getattr(exc, "configured_providers", None)
        if configured_providers:
            details["configured_providers"] = configured_providers

        configured_pools = getattr(exc, "configured_pools", None)
        if configured_pools:
            details["configured_pools"] = configured_pools

        config_dir = getattr(exc, "config_dir", None)
        if config_dir:
            details["config_dir"] = config_dir

        extra_details = getattr(exc, "details", None)
        if isinstance(extra_details, dict):
            details.update(extra_details)

        if details:
            details = _sanitize_details(details)
            try:
                json.dumps(details)
            except TypeError:
                details = {}

        return json_error_payload(
            error_code=error_code,
            message=str(exc),
            hint=hint,
            details=details or None,
        )

    if isinstance(exc, ValueError):
        return json_error_payload(
            error_code="INVALID_ARGUMENT",
            message=str(exc),
            hint=None,
            details=None,
        )

    return json_error_payload(
        error_code="INTERNAL_ERROR",
        message="Internal error",
        hint="See stderr logs for details.",
        details=None,
    )


def dispatch_json_command(
    container: CoreContainer,
    command: str,
    args: dict[str, object],
) -> dict[str, object]:
    if command not in SUPPORTED_COMMANDS:
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

    if command == "system.info":
        return json_envelope(
            command=command,
            ok=True,
            result={
                "name": "openchronicle",
                "protocol_version": STDIO_RPC_PROTOCOL_VERSION,
                "capabilities": {
                    "rpc": True,
                    "serve": True,
                },
            },
            error=None,
        )

    if command == "system.commands":
        return json_envelope(
            command=command,
            ok=True,
            result={"commands": list(SUPPORTED_COMMANDS)},
            error=None,
        )

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

    except Exception as exc:
        return json_envelope(
            command=command,
            ok=False,
            result=None,
            error=_normalize_error(exc),
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


def dispatch_request(container: CoreContainer, request: dict[str, object]) -> dict[str, object]:
    command_value = request.get("command")
    args_value = request.get("args")
    protocol_value = request.get("protocol_version")

    if protocol_value is not None and not isinstance(protocol_value, str):
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="INVALID_REQUEST",
                message="Request 'protocol_version' must be a string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        return payload

    if protocol_value is not None and protocol_value != STDIO_RPC_PROTOCOL_VERSION:
        payload = json_envelope(
            command=str(command_value) if isinstance(command_value, str) else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="UNSUPPORTED_PROTOCOL_VERSION",
                message=f"Unsupported protocol_version: {protocol_value}",
                hint='Use protocol_version "1".',
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        return payload

    if not isinstance(command_value, str):
        payload = json_envelope(
            command=str(command_value) if command_value is not None else "unknown",
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="INVALID_REQUEST",
                message="Request must include 'command' string",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        return payload

    if args_value is None:
        args_value = {}
    if not isinstance(args_value, dict):
        payload = json_envelope(
            command=command_value,
            ok=False,
            result=None,
            error=json_error_payload(
                error_code="INVALID_REQUEST",
                message="Request 'args' must be an object",
                hint=None,
            ),
        )
        payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
        return payload

    response = dispatch_json_command(container, command_value, args_value)
    response["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
    return response


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
            payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        if not isinstance(request, dict):
            payload = json_envelope(
                command="unknown",
                ok=False,
                result=None,
                error=json_error_payload(
                    error_code="INVALID_REQUEST",
                    message="Request must be a JSON object",
                    hint=None,
                ),
            )
            payload["protocol_version"] = STDIO_RPC_PROTOCOL_VERSION
            output_stream.write(json_dumps_line(payload) + "\n")
            output_stream.flush()
            continue

        response = dispatch_request(container, request)
        output_stream.write(json_dumps_line(response) + "\n")
        output_stream.flush()
        if isinstance(request.get("command"), str) and request.get("command") == "system.shutdown":
            break
    return 0
