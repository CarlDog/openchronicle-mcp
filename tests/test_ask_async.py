from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def _rpc_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["OC_DB_PATH"] = str(tmp_path / "async.db")
    env["OC_CONFIG_DIR"] = str(tmp_path / "config")
    env["OC_PLUGIN_DIR"] = str(tmp_path / "plugins")
    env["OC_OUTPUT_DIR"] = str(tmp_path / "output")
    return env


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


def test_convo_ask_async_enqueues_task(tmp_path: Path) -> None:
    env = _rpc_env(tmp_path)
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))

    request = json.dumps(
        {
            "command": "convo.ask_async",
            "args": {
                "conversation_id": conversation_id,
                "prompt": "hello",
                "explain": False,
            },
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "openchronicle.interfaces.cli.main", "rpc", "--request", request],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0

    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))
    assert payload["ok"] is True
    response = cast(dict[str, Any], payload["result"])
    assert response["conversation_id"] == conversation_id
    assert response["status"] == "queued"
    task_id = cast(str, response["task_id"])

    storage = SqliteStore(str(env["OC_DB_PATH"]))
    task = storage.get_task(task_id)
    assert task is not None
    assert task.type == "convo.ask"
    assert task.status.value == "pending"
    assert task.payload.get("conversation_id") == conversation_id

    events = storage.list_events(task_id=task_id)
    assert any(event.type == "convo.ask_queued" for event in events)

    turns = storage.list_turns(conversation_id)
    assert turns == []
