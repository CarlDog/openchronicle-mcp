from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

from tests.helpers.subprocess_env import build_env, oc_command, repo_root, run_oc_module


def test_rpc_request_id_echo(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="request_id.db")
    request = json.dumps({"command": "system.ping", "request_id": "abc", "args": {}})
    result = run_oc_module(["rpc", "--request", request], env=env)
    assert result.returncode == 0

    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))
    assert payload["ok"] is True
    assert payload["request_id"] == "abc"


def test_serve_request_id_dedupe(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="request_id.db")
    proc = subprocess.Popen(
        oc_command(["serve"]),
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=repo_root(),
    )
    assert proc.stdin is not None
    assert proc.stdout is not None

    request = json.dumps({"protocol_version": "1", "command": "system.ping", "args": {}, "request_id": "dup1"})
    shutdown = json.dumps({"protocol_version": "1", "command": "system.shutdown", "args": {}})

    proc.stdin.write(request + "\n")
    proc.stdin.flush()
    line1 = proc.stdout.readline().strip()

    proc.stdin.write(request + "\n")
    proc.stdin.flush()
    line2 = proc.stdout.readline().strip()

    proc.stdin.write(shutdown + "\n")
    proc.stdin.flush()
    proc.stdout.readline()
    proc.stdin.close()

    assert line1
    assert line2
    assert line2 == line1

    proc.wait(timeout=5)


def test_rpc_invalid_request_id(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="request_id.db")
    request = json.dumps({"command": "system.ping", "request_id": 123, "args": {}})
    result = run_oc_module(["rpc", "--request", request], env=env)
    assert result.returncode == 0

    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))
    assert payload["ok"] is False
    error = cast(dict[str, Any], payload["error"])
    assert error["error_code"] == "INVALID_REQUEST"
