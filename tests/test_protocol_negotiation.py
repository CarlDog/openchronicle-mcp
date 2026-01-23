from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.helpers.subprocess_env import build_env, oc_command, repo_root, run_oc_module


def test_rpc_supported_protocol_version(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="negotiation.db")
    request = json.dumps({"protocol_version": "1", "command": "system.ping", "args": {}})
    result = run_oc_module(["rpc", "--request", request], env=env)
    assert result.returncode == 0

    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is True
    assert payload["protocol_version"] == "1"


def test_rpc_unsupported_protocol_version(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="negotiation.db")
    request = json.dumps({"protocol_version": "999", "command": "system.ping", "args": {}})
    result = run_oc_module(["rpc", "--request", request], env=env)
    assert result.returncode == 0

    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    error = payload["error"]
    assert error["error_code"] == "UNSUPPORTED_PROTOCOL_VERSION"
    assert "details" in error


def test_serve_unsupported_protocol_version(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="negotiation.db")
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

    bad_request = json.dumps({"protocol_version": "999", "command": "system.ping", "args": {}})
    shutdown = json.dumps({"protocol_version": "1", "command": "system.shutdown", "args": {}})

    proc.stdin.write(bad_request + "\n")
    proc.stdin.flush()
    line1 = proc.stdout.readline()

    proc.stdin.write(shutdown + "\n")
    proc.stdin.flush()
    line2 = proc.stdout.readline()
    proc.stdin.close()

    payload1 = json.loads(line1.strip())
    assert payload1["ok"] is False
    error = payload1["error"]
    assert error["error_code"] == "UNSUPPORTED_PROTOCOL_VERSION"
    assert "details" in error

    payload2 = json.loads(line2.strip())
    assert payload2["ok"] is True
    assert payload2["protocol_version"] == "1"

    proc.wait(timeout=5)
