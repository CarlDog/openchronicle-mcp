from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def src_path() -> Path:
    return repo_root() / "src"


def build_env(
    tmp_path: Path,
    *,
    db_name: str,
    extra_env: dict[str, str] | None = None,
    ensure_dirs: bool = True,
) -> dict[str, str]:
    env = os.environ.copy()
    env["OC_DB_PATH"] = str(tmp_path / db_name)
    env["OC_CONFIG_DIR"] = str(tmp_path / "config")
    env["OC_PLUGIN_DIR"] = str(tmp_path / "plugins")
    env["OC_OUTPUT_DIR"] = str(tmp_path / "output")

    if ensure_dirs:
        Path(env["OC_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)
        Path(env["OC_PLUGIN_DIR"]).mkdir(parents=True, exist_ok=True)
        Path(env["OC_OUTPUT_DIR"]).mkdir(parents=True, exist_ok=True)

    pythonpath = str(src_path())
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = pythonpath if not existing else pythonpath + os.pathsep + existing

    if extra_env:
        env.update(extra_env)

    return env


def oc_command(args: Iterable[str]) -> list[str]:
    return [sys.executable, "-m", "openchronicle.interfaces.cli.main", *args]


def run_oc_module(
    args: list[str],
    *,
    env: dict[str, str],
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        oc_command(args),
        input=input_text,
        text=True,
        capture_output=True,
        env=env,
        cwd=repo_root(),
        check=False,
    )
