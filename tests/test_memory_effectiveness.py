from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

from openchronicle.core.application.use_cases import add_memory, create_conversation
from openchronicle.core.domain.models.memory_item import MemoryItem
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


def _prepare_conversation_and_memory(db_path: Path) -> tuple[str, str]:
    storage = SqliteStore(str(db_path))
    storage.init_schema()
    event_logger = EventLogger(storage)
    conversation = create_conversation.execute(
        storage=storage,
        convo_store=storage,
        emit_event=event_logger.append,
        title="Memory Effectiveness",
    )
    item = MemoryItem(
        content="alpha memory seed",
        tags=["test"],
        pinned=True,
        conversation_id=conversation.id,
        project_id=conversation.project_id,
        source="test",
    )
    stored = add_memory.execute(store=storage, emit_event=event_logger.append, item=item)
    return conversation.id, stored.id


def test_memory_metrics_without_self_report(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="memory_effectiveness.db",
        extra_env={"OC_LLM_PROVIDER": "stub"},
    )
    conversation_id, _memory_id = _prepare_conversation_and_memory(Path(env["OC_DB_PATH"]))

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
        _send(
            proc,
            {
                "command": "convo.ask",
                "args": {
                    "conversation_id": conversation_id,
                    "prompt": "alpha",
                    "last_n": 1,
                    "top_k_memory": 5,
                },
            },
        )

        snapshot = _send(proc, {"command": "system.metrics", "args": {}})
        result = cast(dict[str, Any], snapshot["result"])
        memory_metrics = cast(dict[str, Any], result["memory"])
        assert memory_metrics["retrieved_total"] > 0
        assert memory_metrics["self_report_enabled"] is False
        assert memory_metrics["used_ids_total"] == 0

        _send(proc, {"command": "system.shutdown", "args": {}})
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.terminate()


def test_memory_self_report_valid(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="memory_effectiveness_valid.db",
        extra_env={
            "OC_LLM_PROVIDER": "stub",
            "OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED": "1",
            "OC_STUB_META_ECHO": "1",
        },
    )
    conversation_id, memory_id = _prepare_conversation_and_memory(Path(env["OC_DB_PATH"]))
    env["OC_STUB_META_IDS"] = memory_id

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
        response = _send(
            proc,
            {
                "command": "convo.ask",
                "args": {
                    "conversation_id": conversation_id,
                    "prompt": "alpha",
                    "last_n": 1,
                    "top_k_memory": 5,
                    "explain": True,
                },
            },
        )
        result = cast(dict[str, Any], response["result"])
        assistant_text = cast(str, result["assistant_text"])
        assert "<OC_META>" not in assistant_text

        explain_payload = cast(dict[str, Any], result["explain"])
        memory_block = cast(dict[str, Any], explain_payload["memory"])
        used_ids = cast(list[str], memory_block.get("memory_used_reported_ids"))
        assert memory_id in used_ids

        snapshot = _send(proc, {"command": "system.metrics", "args": {}})
        metrics = cast(dict[str, Any], snapshot["result"])
        memory_metrics = cast(dict[str, Any], metrics["memory"])
        assert memory_metrics["self_report_enabled"] is True
        assert memory_metrics["self_report_valid_total"] >= 1
        assert memory_metrics["used_ids_total"] >= 1

        _send(proc, {"command": "system.shutdown", "args": {}})
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.terminate()


def test_memory_self_report_invalid_non_strict(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="memory_effectiveness_invalid.db",
        extra_env={
            "OC_LLM_PROVIDER": "stub",
            "OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED": "1",
            "OC_STUB_META_ECHO": "1",
        },
    )
    conversation_id, _memory_id = _prepare_conversation_and_memory(Path(env["OC_DB_PATH"]))
    env["OC_STUB_META_IDS"] = "not-a-real-id"

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
        response = _send(
            proc,
            {
                "command": "convo.ask",
                "args": {
                    "conversation_id": conversation_id,
                    "prompt": "alpha",
                    "last_n": 1,
                    "top_k_memory": 5,
                },
            },
        )
        assert response["ok"] is True

        snapshot = _send(proc, {"command": "system.metrics", "args": {}})
        metrics = cast(dict[str, Any], snapshot["result"])
        memory_metrics = cast(dict[str, Any], metrics["memory"])
        assert memory_metrics["self_report_invalid_total"] >= 1

        _send(proc, {"command": "system.shutdown", "args": {}})
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.terminate()
