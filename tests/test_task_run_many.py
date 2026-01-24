from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from tests.helpers.subprocess_env import build_env, run_oc_module


def _prepare_conversation(db_path: Path) -> str:
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)
    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Run Many",
    )
    return conversation.id


def _run_rpc(request: dict[str, object], *, env: dict[str, str]) -> dict[str, Any]:
    result = run_oc_module(["rpc", "--request", json.dumps(request)], env=env)
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


def _ask_async(conversation_id: str, *, env: dict[str, str], prompt: str) -> str:
    payload = _run_rpc(
        {
            "command": "convo.ask_async",
            "args": {
                "conversation_id": conversation_id,
                "prompt": prompt,
            },
        },
        env=env,
    )
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    return cast(str, result["task_id"])


def test_task_run_many_none(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_many.db",
        extra_env={"OC_LLM_PROVIDER": "stub", "OC_PRIVACY_OUTBOUND_MODE": "off"},
    )
    payload = _run_rpc({"command": "task.run_many", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert result["ran"] == 0
    assert result["completed"] == 0
    assert result["failed"] == 0
    assert result["tasks"] == []


def test_task_run_many_limits_and_continues(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_many.db",
        extra_env={"OC_LLM_PROVIDER": "stub", "OC_PRIVACY_OUTBOUND_MODE": "off"},
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    _ask_async(conversation_id, env=env, prompt="first")
    _ask_async(conversation_id, env=env, prompt="second")
    _ask_async(conversation_id, env=env, prompt="third")

    payload1 = _run_rpc({"command": "task.run_many", "args": {"limit": 2}}, env=env)
    assert payload1["ok"] is True
    result1 = cast(dict[str, Any], payload1["result"])
    assert result1["ran"] == 2
    assert result1["completed"] == 2
    assert result1["failed"] == 0
    assert len(cast(list[dict[str, Any]], result1["tasks"])) == 2

    pending_payload = _run_rpc(
        {"command": "task.list", "args": {"status": "pending", "limit": 10}},
        env=env,
    )
    pending_result = cast(dict[str, Any], pending_payload["result"])
    assert pending_result["total"] == 1

    payload2 = _run_rpc({"command": "task.run_many", "args": {"limit": 2}}, env=env)
    result2 = cast(dict[str, Any], payload2["result"])
    assert result2["ran"] == 1
    assert result2["completed"] == 1
    assert result2["failed"] == 0
    assert len(cast(list[dict[str, Any]], result2["tasks"])) == 1

    pending_payload_after = _run_rpc(
        {"command": "task.list", "args": {"status": "pending", "limit": 10}},
        env=env,
    )
    pending_result_after = cast(dict[str, Any], pending_payload_after["result"])
    assert pending_result_after["total"] == 0


def test_task_run_many_failure(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_many.db",
        extra_env={
            "OC_LLM_PROVIDER": "stub",
            "OC_PRIVACY_OUTBOUND_MODE": "block",
            "OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY": "0",
        },
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    _ask_async(conversation_id, env=env, prompt="email me at user@example.com")

    payload = _run_rpc({"command": "task.run_many", "args": {"limit": 1}}, env=env)
    result = cast(dict[str, Any], payload["result"])
    assert result["ran"] == 1
    assert result["completed"] == 0
    assert result["failed"] == 1
    tasks = cast(list[dict[str, Any]], result["tasks"])
    assert tasks[0]["status"] == "failed"
    error = cast(dict[str, Any], tasks[0]["error"])
    assert error["error_code"] == "OUTBOUND_PII_BLOCKED"
