from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.domain.errors.error_codes import CONVERSATION_NOT_FOUND, MISSING_API_KEY, TIMEOUT
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
        title="Enqueue",
    )
    return conversation.id


def test_cli_convo_ask_enqueue_if_unavailable(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="enqueue.db",
        extra_env={
            "OC_LLM_PROVIDER": "stub",
            "OC_LLM_FAST_POOL": "",
            "OC_LLM_QUALITY_POOL": "",
            "OC_STUB_ERROR_CODE": TIMEOUT,
        },
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    result = run_oc_module(
        [
            "convo",
            "ask",
            conversation_id,
            "hi",
            "--enqueue-if-unavailable",
            "--json",
        ],
        env=env,
    )

    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))
    assert payload["ok"] is True
    response = cast(dict[str, Any], payload["result"])
    assert response["status"] == "queued"
    assert response["reason_code"] == TIMEOUT
    task_id = cast(str, response["task_id"])

    request = json.dumps({"command": "task.get", "args": {"task_id": task_id}})
    task_response = run_oc_module(["rpc", "--request", request], env=env)
    task_payload = cast(dict[str, Any], json.loads(task_response.stdout.strip()))
    assert task_payload["ok"] is True
    task_result = cast(dict[str, Any], task_payload["result"])
    task = cast(dict[str, Any], task_result["task"])
    assert task["status"] == "pending"

    storage = SqliteStore(str(env["OC_DB_PATH"]))
    turns = storage.list_turns(conversation_id)
    assert turns == []


def test_rpc_convo_ask_enqueue_if_unavailable(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="enqueue_rpc.db",
        extra_env={
            "OC_LLM_PROVIDER": "stub",
            "OC_LLM_FAST_POOL": "",
            "OC_LLM_QUALITY_POOL": "",
            "OC_STUB_ERROR_CODE": TIMEOUT,
        },
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    request = json.dumps(
        {
            "protocol_version": "1",
            "command": "convo.ask",
            "args": {
                "conversation_id": conversation_id,
                "prompt": "hi",
                "enqueue_if_unavailable": True,
            },
        }
    )
    result = run_oc_module(["rpc", "--request", request], env=env)
    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))

    assert payload["ok"] is True
    response = cast(dict[str, Any], payload["result"])
    assert response["status"] == "queued"
    assert response["reason_code"] == TIMEOUT
    assert "task_id" in response


def test_rpc_convo_ask_enqueue_if_unavailable_invalid_argument(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="enqueue_invalid.db")

    request = json.dumps(
        {
            "protocol_version": "1",
            "command": "convo.ask",
            "args": {
                "conversation_id": "missing",
                "prompt": "hi",
                "enqueue_if_unavailable": True,
            },
        }
    )
    result = run_oc_module(["rpc", "--request", request], env=env)
    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))

    assert payload["ok"] is False
    error = cast(dict[str, Any], payload["error"])
    assert error["error_code"] == CONVERSATION_NOT_FOUND


def test_rpc_convo_ask_enqueue_if_unavailable_permanent_error(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="enqueue_perm.db",
        extra_env={
            "OC_LLM_PROVIDER": "stub",
            "OC_LLM_FAST_POOL": "",
            "OC_LLM_QUALITY_POOL": "",
            "OC_STUB_ERROR_CODE": MISSING_API_KEY,
        },
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    request = json.dumps(
        {
            "protocol_version": "1",
            "command": "convo.ask",
            "args": {
                "conversation_id": conversation_id,
                "prompt": "hi",
                "enqueue_if_unavailable": True,
            },
        }
    )
    result = run_oc_module(["rpc", "--request", request], env=env)
    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))

    assert payload["ok"] is False
    error = cast(dict[str, Any], payload["error"])
    assert error["error_code"] == MISSING_API_KEY
