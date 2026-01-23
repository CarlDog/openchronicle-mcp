from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.helpers.subprocess_env import build_env, run_oc_module


def _run_rpc(
    args: list[str], *, input_text: str | None = None, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    return run_oc_module(["rpc", *args], input_text=input_text, env=env)


def test_rpc_ping_request_arg(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="rpc.db")
    request = json.dumps({"protocol_version": "1", "command": "system.ping", "args": {}})
    result = _run_rpc(["--request", request], env=env)
    assert result.returncode == 0

    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is True
    assert payload["result"] == {"pong": True}
    assert payload["protocol_version"] == "1"


def test_rpc_ping_stdin(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="rpc.db")
    request = json.dumps({"protocol_version": "1", "command": "system.ping", "args": {}})
    result = _run_rpc([], input_text=request + "\n", env=env)
    assert result.returncode == 0

    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is True
    assert payload["result"] == {"pong": True}
    assert payload["protocol_version"] == "1"


def test_rpc_invalid_json(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="rpc.db")
    result = _run_rpc(["--request", "{not json"], env=env)
    assert result.returncode == 0

    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    error = payload["error"]
    assert error["error_code"] == "INVALID_JSON"
    assert "details" in error


def test_rpc_invalid_request(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="rpc.db")
    request = json.dumps({"protocol_version": "1", "args": {}})
    result = _run_rpc(["--request", request], env=env)
    assert result.returncode == 0

    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    error = payload["error"]
    assert error["error_code"] == "INVALID_REQUEST"
    assert "details" in error


def test_rpc_unsupported_protocol_version(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="rpc.db")
    request = json.dumps({"protocol_version": "999", "command": "system.ping", "args": {}})
    result = _run_rpc(["--request", request], env=env)
    assert result.returncode == 0

    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    error = payload["error"]
    assert error["error_code"] == "UNSUPPORTED_PROTOCOL_VERSION"
    assert "details" in error
