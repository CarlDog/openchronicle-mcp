"""Shared utilities for CLI command handlers."""

from __future__ import annotations

import json
from typing import Any


def parse_json(value: str) -> dict[str, Any]:
    try:
        result: dict[str, Any] = json.loads(value)
        return result
    except json.JSONDecodeError:
        return {"raw": value}


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, indent=2))


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
