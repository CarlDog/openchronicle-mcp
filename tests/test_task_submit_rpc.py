"""Test task.submit RPC command."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _run_oc(args: list[str], db_path: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Helper to run oc with environment variables.

    Uses sys.executable -m to invoke the CLI module directly,
    avoiding PATH dependency issues on Windows.
    """
    # Replace "oc" with python -m invocation
    if args and args[0] == "oc":
        args = [sys.executable, "-m", "openchronicle.interfaces.cli.main", *args[1:]]
    env = {**os.environ, "OC_DB_PATH": str(db_path)}
    return subprocess.run(args, capture_output=True, text=True, check=check, env=env)


def test_task_submit_creates_task_in_db() -> None:
    """Task.submit should create a task that can be retrieved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime_dir = Path(tmpdir)
        db_path = runtime_dir / "test.db"

        # Create project
        create_result = _run_oc(["oc", "init-project", "test-project"], db_path)
        project_id = create_result.stdout.strip()

        # Submit task via RPC
        submit_request = {
            "protocol_version": "1",
            "command": "task.submit",
            "args": {
                "project_id": project_id,
                "task_type": "plugin.invoke",
                "payload": {"handler": "hello.echo", "input": {"prompt": "test"}},
            },
        }

        submit_result = _run_oc(["oc", "rpc", "--request", json.dumps(submit_request)], db_path)

        submit_response = json.loads(submit_result.stdout)
        assert submit_response["ok"] is True
        assert "task_id" in submit_response["result"]
        assert submit_response["result"]["status"] == "pending"

        task_id = submit_response["result"]["task_id"]

        # Verify task exists via task.get
        get_request = {
            "protocol_version": "1",
            "command": "task.get",
            "args": {"task_id": task_id},
        }

        get_result = _run_oc(["oc", "rpc", "--request", json.dumps(get_request)], db_path)

        get_response = json.loads(get_result.stdout)
        assert get_response["ok"] is True
        assert get_response["result"]["task"]["task_id"] == task_id
        assert get_response["result"]["task"]["type"] == "plugin.invoke"


def test_task_submit_and_execute_hello_echo(tmp_path: Path) -> None:
    """Task.submit + task.run_many should execute hello.echo deterministically."""
    db_path = tmp_path / "test.db"

    # Create project
    create_result = _run_oc(["oc", "init-project", "test-project"], db_path)
    project_id = create_result.stdout.strip()

    # Submit hello.echo task via plugin.invoke
    submit_request = {
        "protocol_version": "1",
        "command": "task.submit",
        "args": {
            "project_id": project_id,
            "task_type": "plugin.invoke",
            "payload": {"handler": "hello.echo", "input": {"prompt": "test message"}},
        },
    }

    submit_result = _run_oc(["oc", "rpc", "--request", json.dumps(submit_request)], db_path)

    submit_response = json.loads(submit_result.stdout)
    task_id = submit_response["result"]["task_id"]

    # Execute task
    run_request = {
        "protocol_version": "1",
        "command": "task.run_many",
        "args": {"limit": 1, "max_seconds": 5, "type": "plugin.invoke"},
    }

    _run_oc(["oc", "rpc", "--request", json.dumps(run_request)], db_path)

    # Poll until task completes (or fails) with bounded retries
    get_request = {
        "protocol_version": "1",
        "command": "task.get",
        "args": {"task_id": task_id},
    }

    max_attempts = 20
    sleep_seconds = 0.1
    last_response: dict[str, object] | None = None
    status = "pending"

    for _ in range(max_attempts):
        get_result = _run_oc(["oc", "rpc", "--request", json.dumps(get_request)], db_path)
        get_response = json.loads(get_result.stdout)
        last_response = get_response
        assert get_response["ok"] is True
        task = get_response["result"]["task"]
        status = str(task.get("status", "pending"))

        if status == "completed":
            break

        if status == "failed":
            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT error_json FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()
            error_json = row[0] if row else None
            raise AssertionError(
                f"Task failed unexpectedly. task_id={task_id} error_json={error_json} response={get_response}"
            )

        time.sleep(sleep_seconds)

    assert (
        status == "completed"
    ), f"Task did not complete within timeout. task_id={task_id} last_response={last_response}"

    # Validate deterministic result payload persisted to storage
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT result_json FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

    assert row is not None, f"Task not found in storage for task_id={task_id}"
    result_json = row[0]
    assert result_json is not None, f"Task result_json missing for task_id={task_id}"
    result_payload = json.loads(result_json)
    assert result_payload == {"echo": "test message"}


def test_task_submit_missing_project_id() -> None:
    """Task.submit should return INVALID_ARGUMENT if project_id is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime_dir = Path(tmpdir)
        db_path = runtime_dir / "test.db"

        submit_request = {
            "protocol_version": "1",
            "command": "task.submit",
            "args": {
                "task_type": "plugin.invoke",
                "payload": {"handler": "hello.echo", "input": {"prompt": "test"}},
            },
        }

        submit_result = _run_oc(["oc", "rpc", "--request", json.dumps(submit_request)], db_path, check=False)

        submit_response = json.loads(submit_result.stdout)
        assert submit_response["ok"] is False
        assert submit_response["error"]["error_code"] == "INVALID_ARGUMENT"
        assert "project_id" in submit_response["error"]["message"]


def test_task_submit_invalid_task_type(tmp_path: Path) -> None:
    """Task.submit should return INVALID_TASK_TYPE for handler-as-task-type."""
    db_path = tmp_path / "test.db"

    # Create project
    create_result = _run_oc(["oc", "init-project", "test-project"], db_path)
    project_id = create_result.stdout.strip()

    submit_request = {
        "protocol_version": "1",
        "command": "task.submit",
        "args": {
            "project_id": project_id,
            "task_type": "hello.echo",
            "payload": {},
        },
    }

    submit_result = _run_oc(["oc", "rpc", "--request", json.dumps(submit_request)], db_path, check=False)

    submit_response = json.loads(submit_result.stdout)
    assert submit_response["ok"] is False
    assert submit_response["error"]["error_code"] == "INVALID_TASK_TYPE"
    assert "Invalid task type" in submit_response["error"]["message"]

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(1) FROM tasks").fetchone()
    assert row is not None
    assert row[0] == 0


def test_task_submit_unknown_handler() -> None:
    """Task.submit should return UNKNOWN_HANDLER for unknown plugin.invoke handler."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime_dir = Path(tmpdir)
        db_path = runtime_dir / "test.db"

        # Create project
        create_result = _run_oc(["oc", "init-project", "test-project"], db_path)
        project_id = create_result.stdout.strip()

        submit_request = {
            "protocol_version": "1",
            "command": "task.submit",
            "args": {
                "project_id": project_id,
                "task_type": "plugin.invoke",
                "payload": {"handler": "unknown.handler", "input": {}},
            },
        }

        submit_result = _run_oc(["oc", "rpc", "--request", json.dumps(submit_request)], db_path, check=False)

        submit_response = json.loads(submit_result.stdout)
        assert submit_response["ok"] is False
        assert submit_response["error"]["error_code"] == "UNKNOWN_HANDLER"


def test_task_submit_missing_payload() -> None:
    """Task.submit should return INVALID_ARGUMENT if payload is missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime_dir = Path(tmpdir)
        db_path = runtime_dir / "test.db"

        # Create project
        create_result = _run_oc(["oc", "init-project", "test-project"], db_path)
        project_id = create_result.stdout.strip()

        submit_request = {
            "protocol_version": "1",
            "command": "task.submit",
            "args": {
                "project_id": project_id,
                "task_type": "plugin.invoke",
            },
        }

        submit_result = _run_oc(["oc", "rpc", "--request", json.dumps(submit_request)], db_path, check=False)

        submit_response = json.loads(submit_result.stdout)
        assert submit_response["ok"] is False
        assert submit_response["error"]["error_code"] == "INVALID_ARGUMENT"
        assert "payload" in submit_response["error"]["message"]


def test_task_submit_project_not_found() -> None:
    """Task.submit should return PROJECT_NOT_FOUND for nonexistent projects."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime_dir = Path(tmpdir)
        db_path = runtime_dir / "test.db"

        submit_request = {
            "protocol_version": "1",
            "command": "task.submit",
            "args": {
                "project_id": "nonexistent-project",
                "task_type": "plugin.invoke",
                "payload": {"handler": "hello.echo", "input": {"prompt": "test"}},
            },
        }

        submit_result = _run_oc(["oc", "rpc", "--request", json.dumps(submit_request)], db_path, check=False)

        submit_response = json.loads(submit_result.stdout)
        assert submit_response["ok"] is False
        assert submit_response["error"]["error_code"] == "PROJECT_NOT_FOUND"
