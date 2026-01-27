from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tests.helpers.subprocess_env import build_env, run_oc_module


def test_selftest_cli_json(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="selftest-cli.db")
    result = run_oc_module(
        ["selftest", "--json", "--dir", str(tmp_path / "selftest")],
        env=env,
    )
    assert result.returncode == 0

    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))
    assert payload["ok"] is True

    result_payload = cast(dict[str, Any], payload["result"])
    assert result_payload["ok"] is True
    assert result_payload.get("conversation_id")
    assert result_payload.get("turn_id")
    assert result_payload.get("export_path")

    workspace = cast(dict[str, Any], result_payload.get("workspace"))
    assert workspace.get("base_dir")
    assert workspace.get("data_dir")
    assert workspace.get("plugins_dir")
    assert workspace.get("output_dir")


def test_selftest_cli_json_with_telemetry_self_report(tmp_path: Path) -> None:
    env = build_env(tmp_path, db_name="selftest-cli-telemetry.db")
    result = run_oc_module(
        [
            "selftest",
            "--json",
            "--telemetry-self-report",
            "--dir",
            str(tmp_path / "selftest-telemetry"),
        ],
        env=env,
    )
    assert result.returncode == 0

    payload = cast(dict[str, Any], json.loads(result.stdout.strip()))
    assert payload["ok"] is True
