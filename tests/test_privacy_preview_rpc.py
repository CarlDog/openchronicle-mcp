from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tests.helpers.subprocess_env import build_env, run_oc_module


def _run_rpc(request: dict[str, object], *, env: dict[str, str]) -> dict[str, Any]:
    result = run_oc_module(["rpc", "--request", json.dumps(request)], env=env)
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


def test_privacy_preview_detects_email(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="privacy_preview.db")
    payload = _run_rpc(
        {
            "command": "privacy.preview",
            "args": {
                "text": "contact a@b.com",
                "provider": "openai",
                "mode_override": "warn",
                "categories_override": ["email"],
            },
        },
        env=env,
    )
    assert payload["ok"] is True
    report = cast(dict[str, Any], payload["result"])["report"]
    assert report["categories"] == ["email"]
    assert report["counts"]["email"] == 1


def test_privacy_preview_redacts(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="privacy_preview.db")
    payload = _run_rpc(
        {
            "command": "privacy.preview",
            "args": {
                "text": "contact a@b.com",
                "provider": "openai",
                "mode_override": "redact",
                "categories_override": ["email"],
            },
        },
        env=env,
    )
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert "redacted_text" in result
    assert "[REDACTED_EMAIL]" in result["redacted_text"]
    assert "a@b.com" not in result["redacted_text"]


def test_privacy_preview_external_only_local_provider(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="privacy_preview.db")
    payload = _run_rpc(
        {
            "command": "privacy.preview",
            "args": {
                "text": "contact a@b.com",
                "provider": "ollama",
                "mode_override": "block",
                "external_only_override": True,
                "categories_override": ["email"],
            },
        },
        env=env,
    )
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert result["effective_policy"]["applies"] is False
    assert "redacted_text" not in result


def test_privacy_preview_invalid_override(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="privacy_preview.db")
    payload = _run_rpc(
        {
            "command": "privacy.preview",
            "args": {
                "text": "contact a@b.com",
                "categories_override": "email",
            },
        },
        env=env,
    )
    assert payload["ok"] is False
    error = cast(dict[str, Any], payload["error"])
    assert error["error_code"] == "INVALID_ARGUMENT"
