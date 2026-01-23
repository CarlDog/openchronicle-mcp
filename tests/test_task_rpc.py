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
        title="Async",
    )
    return conversation.id


def _run_rpc(request: dict[str, object], *, env: dict[str, str]) -> dict[str, Any]:
    result = run_oc_module(["rpc", "--request", json.dumps(request)], env=env)
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


def _ask_async(conversation_id: str, *, env: dict[str, str]) -> str:
    payload = _run_rpc(
        {
            "command": "convo.ask_async",
            "args": {
                "conversation_id": conversation_id,
                "prompt": "hello",
                "explain": False,
            },
        },
        env=env,
    )
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    return cast(str, result["task_id"])


def test_task_get_from_ask_async(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="task_rpc.db")
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))
    task_id = _ask_async(conversation_id, env=env)

    payload = _run_rpc({"command": "task.get", "args": {"task_id": task_id}}, env=env)
    assert payload["ok"] is True
    task = cast(dict[str, Any], payload["result"])["task"]
    assert task["task_id"] == task_id
    assert task["type"] == "convo.ask"
    assert task["status"] == "pending"


def test_task_list_ordering(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="task_rpc.db")
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))
    ids = [
        _ask_async(conversation_id, env=env),
        _ask_async(conversation_id, env=env),
        _ask_async(conversation_id, env=env),
    ]

    payload = _run_rpc({"command": "task.list", "args": {"limit": 10}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    tasks = cast(list[dict[str, Any]], result["tasks"])
    task_ids = {task["task_id"] for task in tasks}
    assert set(ids).issubset(task_ids)

    ordering = [(task["created_at"], task["task_id"]) for task in tasks]
    assert ordering == sorted(ordering, reverse=True)


def test_task_get_not_found(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="task_rpc.db")
    payload = _run_rpc({"command": "task.get", "args": {"task_id": "missing"}}, env=env)
    assert payload["ok"] is False
    error = cast(dict[str, Any], payload["error"])
    assert error["error_code"] == "TASK_NOT_FOUND"
