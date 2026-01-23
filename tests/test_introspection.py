from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tests.helpers.subprocess_env import build_env, run_oc_module


def _run_rpc(request: dict[str, object], *, env: dict[str, str]) -> dict[str, Any]:
    result = run_oc_module(["rpc", "--request", json.dumps(request)], env=env)
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


def test_rpc_system_info(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="rpc.db")
    payload = _run_rpc({"protocol_version": "1", "command": "system.info", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert result["protocol_version"] == "1"


def test_rpc_system_commands(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="rpc.db")
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
