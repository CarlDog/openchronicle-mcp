from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tests.helpers.subprocess_env import build_env, run_oc_module


def _run_rpc(request: dict[str, object], *, env: dict[str, str]) -> dict[str, Any]:
    result = run_oc_module(["rpc", "--request", json.dumps(request)], env=env)
    return cast(dict[str, Any], json.loads(result.stdout.strip()))


def test_rpc_system_health_ok(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="health.db")
    payload = _run_rpc({"protocol_version": "1", "command": "system.health", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    assert result["ok"] is True

    storage = cast(dict[str, Any], result["storage"])
    assert storage["type"] == "sqlite"
    assert storage["reachable"] is True

    config = cast(dict[str, Any], result["config"])
    assert isinstance(config["config_dir"], str)
    pools = cast(list[str], config["pools"])
    assert pools == sorted(pools)


def test_rpc_system_health_nsfw_unset(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="health.db")
    env.pop("OC_LLM_POOL_NSFW", None)
    payload = _run_rpc({"protocol_version": "1", "command": "system.health", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    config = cast(dict[str, Any], result["config"])
    assert isinstance(config["nsfw_pool_configured"], bool)
    assert config["nsfw_pool_configured"] is False


def test_system_commands_includes_health(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="health.db")
    payload = _run_rpc({"protocol_version": "1", "command": "system.commands", "args": {}}, env=env)
    assert payload["ok"] is True
    result = cast(dict[str, Any], payload["result"])
    commands = cast(list[str], result["commands"])
    assert "system.health" in commands
