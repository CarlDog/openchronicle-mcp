from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.infrastructure.logging.event_logger import EventLogger
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore
from tests.helpers.subprocess_env import build_env, oc_command, repo_root


def _send(proc: subprocess.Popen[str], request: dict[str, object]) -> dict[str, Any]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line
    return cast(dict[str, Any], json.loads(line))


def _prepare_conversation(db_path: Path) -> str:
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)
    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Metrics",
    )
    return conversation.id


def test_system_metrics_snapshot(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="metrics.db",
        extra_env={"OC_LLM_PROVIDER": "stub"},
    )
    conversation_id = _prepare_conversation(Path(env["OC_DB_PATH"]))
    proc = subprocess.Popen(
        oc_command(["serve"]),
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=repo_root(),
    )

    try:
        snapshot1 = _send(proc, {"command": "system.metrics", "args": {}})
        result1 = cast(dict[str, Any], snapshot1["result"])
        requests1 = cast(dict[str, Any], result1["requests"])
        assert requests1["total"] >= 1
        assert requests1["ok"] >= 1
        assert "system.metrics" in requests1["by_command"]
        assert result1["uptime_seconds"] >= 0
        assert result1["telemetry_enabled"] is True
        assert "llm" in result1
        assert "perf" in result1
        assert "context" in result1
        memory1 = cast(dict[str, Any], result1["memory"])
        assert "retrieved_total" in memory1
        assert "pinned_total" in memory1
        assert "retrieval_reason_counts" in memory1
        assert "unique_memory_ids_seen_total" in memory1

        bad_response = _send(proc, {"command": "nope", "args": {}})
        assert bad_response["ok"] is False

        snapshot2 = _send(proc, {"command": "system.metrics", "args": {}})
        result2 = cast(dict[str, Any], snapshot2["result"])
        requests2 = cast(dict[str, Any], result2["requests"])
        assert requests2["error"] >= requests1["error"] + 1
        assert "UNKNOWN_COMMAND" in requests2["by_error_code"]

        _send(
            proc,
            {
                "command": "convo.ask",
                "args": {
                    "conversation_id": conversation_id,
                    "prompt": "metrics prompt",
                    "last_n": 2,
                    "top_k_memory": 0,
                },
            },
        )

        snapshot2b = _send(proc, {"command": "system.metrics", "args": {}})
        result2b = cast(dict[str, Any], snapshot2b["result"])
        llm2 = cast(dict[str, Any], result2b["llm"])
        assert llm2["calls_total"] >= 1
        assert llm2["calls_by_provider"].get("stub", 0) >= 1
        if llm2["tokens_total"] == 0:
            assert llm2["usage_unknown_calls"] >= 1

        _send(proc, {"command": "task.run_many", "args": {"limit": 1}})

        snapshot3 = _send(proc, {"command": "system.metrics", "args": {}})
        result3 = cast(dict[str, Any], snapshot3["result"])
        tasks2 = cast(dict[str, Any], result2["tasks"])
        tasks3 = cast(dict[str, Any], result3["tasks"])
        assert tasks3["run_many"] >= tasks2["run_many"] + 1
        assert tasks3["completed"] >= tasks2["completed"]
        assert tasks3["failed"] >= tasks2["failed"]

        _send(proc, {"command": "system.shutdown", "args": {}})
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.terminate()


def test_system_metrics_telemetry_disabled(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="metrics-disabled.db",
        extra_env={
            "OC_LLM_PROVIDER": "stub",
            "OC_TELEMETRY_ENABLED": "0",
        },
    )
    proc = subprocess.Popen(
        oc_command(["serve"]),
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=repo_root(),
    )

    try:
        snapshot = _send(proc, {"command": "system.metrics", "args": {}})
        result = cast(dict[str, Any], snapshot["result"])
        assert result["telemetry_enabled"] is False
        assert "llm" not in result
        assert "perf" not in result
        assert "context" not in result
        _send(proc, {"command": "system.shutdown", "args": {}})
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.terminate()
