from __future__ import annotations

import json
import subprocess
from pathlib import Path

from tests.helpers.subprocess_env import build_env, oc_command, repo_root, run_oc_module


def test_rpc_stdout_purity(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="purity.db")
    request = json.dumps({"command": "system.ping", "args": {}})
    result = run_oc_module(["rpc", "--request", request], env=env)
    assert result.returncode == 0

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    assert payload["result"] == {"pong": True}


def test_serve_stdout_purity(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="purity.db")
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

    ping = json.dumps({"command": "system.ping", "args": {}})
    shutdown = json.dumps({"command": "system.shutdown", "args": {}})

    proc.stdin.write(ping + "\n")
    proc.stdin.flush()
    line1 = proc.stdout.readline()

    proc.stdin.write(shutdown + "\n")
    proc.stdin.flush()
    line2 = proc.stdout.readline()
    proc.stdin.close()

    payload1 = json.loads(line1.strip())
    payload2 = json.loads(line2.strip())
    assert payload1["ok"] is True
    assert payload2["ok"] is True

    proc.wait(timeout=5)
    remaining = proc.stdout.read()
    assert remaining.strip() == ""
