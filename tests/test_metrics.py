from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

from tests.helpers.subprocess_env import build_env, oc_command, repo_root


def _send(proc: subprocess.Popen[str], request: dict[str, object]) -> dict[str, Any]:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line
    return cast(dict[str, Any], json.loads(line))


def test_system_metrics_snapshot(tmp_path: Path) -> None:
    env = build_env(
        tmp_path,
        db_name="metrics.db",
        extra_env={"OC_LLM_PROVIDER": "stub"},
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
        snapshot1 = _send(proc, {"command": "system.metrics", "args": {}})
        result1 = cast(dict[str, Any], snapshot1["result"])
        requests1 = cast(dict[str, Any], result1["requests"])
        assert requests1["total"] >= 1
        assert requests1["ok"] >= 1
        assert "system.metrics" in requests1["by_command"]
        assert result1["uptime_seconds"] >= 0

        bad_response = _send(proc, {"command": "nope", "args": {}})
        assert bad_response["ok"] is False

        snapshot2 = _send(proc, {"command": "system.metrics", "args": {}})
        result2 = cast(dict[str, Any], snapshot2["result"])
        requests2 = cast(dict[str, Any], result2["requests"])
        assert requests2["error"] >= requests1["error"] + 1
        assert "UNKNOWN_COMMAND" in requests2["by_error_code"]

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
