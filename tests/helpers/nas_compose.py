"""Render ``docker-compose.nas.yml`` through the real Compose CLI.

Compose, not a YAML parser, decides what ``external``, ``name`` and variable
substitution mean, so tests that pin the deployed shape render the file the
way Portainer does. No daemon is needed: ``docker compose config`` only
resolves the file.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

NAS_COMPOSE = Path(__file__).parents[2] / "docker-compose.nas.yml"


def render_nas_compose(tmp_path: Path, env_overrides: dict[str, str]) -> dict[str, Any]:
    """Return the rendered compose model, or skip when Compose is unavailable."""
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker Compose CLI is unavailable")

    docker_config = tmp_path / "docker-config"
    docker_config.mkdir(exist_ok=True)
    # Docker Desktop keeps its bundled Compose plugin beside the CLI,
    # but a clean DOCKER_CONFIG hides that discovery path on Windows.
    plugin_dir = Path(docker).parent.parent / "cli-plugins"
    if plugin_dir.is_dir():
        (docker_config / "config.json").write_text(
            json.dumps({"cliPluginsExtraDirs": [str(plugin_dir)]}), encoding="utf-8"
        )
    env = {"PATH": os.environ.get("PATH", ""), "DOCKER_CONFIG": str(docker_config), **env_overrides}
    for name in ("SystemRoot", "WINDIR", "PATHEXT"):
        if value := os.environ.get(name):
            env[name] = value

    version = subprocess.run([docker, "compose", "version"], capture_output=True, text=True, env=env, timeout=10)
    if version.returncode != 0:
        pytest.skip("Docker Compose CLI is unavailable")

    result = subprocess.run(
        [docker, "compose", "-f", str(NAS_COMPOSE), "config", "--format", "json"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"Docker Compose could not render the NAS file: {result.stderr}"
    rendered: dict[str, Any] = json.loads(result.stdout)
    return rendered
