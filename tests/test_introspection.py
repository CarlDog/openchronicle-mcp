from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def _rpc_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["OC_DB_PATH"] = str(tmp_path / "rpc.db")
    env["OC_CONFIG_DIR"] = str(tmp_path / "config")
    env["OC_PLUGIN_DIR"] = str(tmp_path / "plugins")
    env["OC_OUTPUT_DIR"] = str(tmp_path / "output")
    return env


def _run_rpc(request: dict[str, object], *, env: dict[str, str]) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "openchronicle.interfaces.cli.main",
            "rpc",
            "--request",
            json.dumps(request),
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


def test_rpc_system_info(tmp_path: Path) -> None:
    env = _rpc_env(tmp_path)
    payload = _run_rpc({"protocol_version": "1", "command": "system.info", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert result["protocol_version"] == "1"


def test_rpc_system_commands(tmp_path: Path) -> None:
    env = _rpc_env(tmp_path)
    payload = _run_rpc({"protocol_version": "1", "command": "system.commands", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    commands = result["commands"]
    assert commands == sorted(commands)
    assert "system.ping" in commands
    assert "system.shutdown" in commands
    assert "convo.export" in commands
    assert "system.info" in commands
    assert "system.commands" in commands
