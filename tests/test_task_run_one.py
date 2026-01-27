from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.domain.models.project import Task, TaskStatus
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
        title="Run One",
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


def test_task_run_one_none(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_one.db",
        extra_env={"OC_LLM_PROVIDER": "stub", "OC_PRIVACY_OUTBOUND_MODE": "off"},
    )
    payload = _run_rpc({"command": "task.run_one", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert result["ran"] is False
    assert result["task_id"] is None
    assert result["status"] == "none"
    assert result["scanned"] == 0
    assert result["skipped_unrunnable"] == 0


def test_task_run_one_deterministic(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_one.db",
        extra_env={"OC_LLM_PROVIDER": "stub", "OC_PRIVACY_OUTBOUND_MODE": "off"},
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    _ask_async(conversation_id, env=env, prompt="first")
    _ask_async(conversation_id, env=env, prompt="second")

    storage = SqliteStore(str(env["OC_DB_PATH"]))
    tasks = [
        task
        for project in storage.list_projects()
        for task in storage.list_tasks_by_project(project.id)
        if task.type == "convo.ask"
    ]
    tasks.sort(key=lambda task: (task.created_at, task.id))
    expected_order = [task.id for task in tasks]

    payload1 = _run_rpc({"command": "task.run_one", "args": {}}, env=env)
    result1 = cast(dict[str, Any], payload1["result"])
    assert result1["task_id"] == expected_order[0]
    assert result1["status"] == "completed"
    assert result1["scanned"] >= 1
    assert result1["skipped_unrunnable"] == 0

    turns_after_first = storage.list_turns(conversation_id)
    assert len(turns_after_first) == 1

    payload2 = _run_rpc({"command": "task.run_one", "args": {}}, env=env)
    result2 = cast(dict[str, Any], payload2["result"])
    assert result2["task_id"] == expected_order[1]
    assert result2["status"] == "completed"
    assert result2["scanned"] >= 1
    assert result2["skipped_unrunnable"] == 0

    turns_after_second = storage.list_turns(conversation_id)
    assert len(turns_after_second) == 2


def test_task_run_one_tie_breaker(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_one.db",
        extra_env={"OC_LLM_PROVIDER": "stub", "OC_PRIVACY_OUTBOUND_MODE": "off"},
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    storage = SqliteStore(str(env["OC_DB_PATH"]))
    conversation = storage.get_conversation(conversation_id)
    assert conversation is not None

    fixed_time = datetime(2024, 1, 1, tzinfo=UTC)
    task_b = Task(
        id="task-b",
        project_id=conversation.project_id,
        type="convo.ask",
        payload={"conversation_id": conversation_id, "prompt": "second"},
        status=TaskStatus.PENDING,
        created_at=fixed_time,
        updated_at=fixed_time,
    )
    task_a = Task(
        id="task-a",
        project_id=conversation.project_id,
        type="convo.ask",
        payload={"conversation_id": conversation_id, "prompt": "first"},
        status=TaskStatus.PENDING,
        created_at=fixed_time,
        updated_at=fixed_time,
    )
    storage.add_task(task_b)
    storage.add_task(task_a)

    payload1 = _run_rpc({"command": "task.run_one", "args": {}}, env=env)
    result1 = cast(dict[str, Any], payload1["result"])
    assert result1["task_id"] == "task-a"
    assert result1["status"] == "completed"
    assert result1["skipped_unrunnable"] == 0

    payload2 = _run_rpc({"command": "task.run_one", "args": {}}, env=env)
    result2 = cast(dict[str, Any], payload2["result"])
    assert result2["task_id"] == "task-b"
    assert result2["status"] == "completed"
    assert result2["skipped_unrunnable"] == 0


def test_task_run_one_failure(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_one.db",
        extra_env={"OC_LLM_PROVIDER": "stub", "OC_PRIVACY_OUTBOUND_MODE": "off"},
    )
    env["OC_PRIVACY_OUTBOUND_MODE"] = "block"
    env["OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY"] = "0"
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    task_id = _ask_async(conversation_id, env=env, prompt="email me at user@example.com")

    payload = _run_rpc({"command": "task.run_one", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert result["status"] == "failed"
    assert result["skipped_unrunnable"] == 0
    error = cast(dict[str, Any], result["error"])
    assert error["error_code"] == "OUTBOUND_PII_BLOCKED"

    storage = SqliteStore(str(env["OC_DB_PATH"]))
    task = storage.get_task(task_id)
    assert task is not None
    assert task.status.value == "failed"


def test_task_run_one_skips_unrunnable(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="run_one.db",
        extra_env={"OC_LLM_PROVIDER": "stub", "OC_PRIVACY_OUTBOUND_MODE": "off"},
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    storage = SqliteStore(str(env["OC_DB_PATH"]))
    conversation = storage.get_conversation(conversation_id)
    assert conversation is not None

    unrunnable_task = Task(
        project_id=conversation.project_id,
        type="unknown.task",
        payload={"note": "should be skipped"},
    )
    storage.add_task(unrunnable_task)

    _ask_async(conversation_id, env=env, prompt="hello")

    payload = _run_rpc({"command": "task.run_one", "args": {}}, env=env)
    result = cast(dict[str, Any], payload["result"])
    assert result["ran"] is True
    assert result["status"] == "completed"
    assert result["skipped_unrunnable"] == 1
    assert result["scanned"] == 2

    skipped_task = storage.get_task(unrunnable_task.id)
    assert skipped_task is not None
    assert skipped_task.status.value == "pending"
