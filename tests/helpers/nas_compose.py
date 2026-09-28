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
import sys
from pathlib import Path
from typing import Any, NoReturn

import pytest

NAS_COMPOSE = Path(__file__).parents[2] / "docker-compose.nas.yml"

# Variables the compose file substitutes, or that steer Compose itself. They are
# stripped from the inherited environment so a developer's shell cannot change
# what the tests render; everything else passes through, because the Windows
# CLI finds its Compose plugin through variables such as ProgramData.
_STRIPPED_PREFIXES = ("DOCKER_", "COMPOSE_", "OC_", "HOST_", "PROMETHEUS_", "OLLAMA_", "OPENAI_")


def _unavailable(reason: str) -> NoReturn:
    """Skip locally; fail on Linux CI, the leg that must provide coverage."""
    if os.environ.get("CI") and sys.platform.startswith("linux"):
        pytest.fail(f"Docker Compose is required on Linux CI: {reason}")
    pytest.skip(f"Docker Compose CLI is unavailable: {reason}")


def render_nas_compose(tmp_path: Path, env_overrides: dict[str, str]) -> dict[str, Any]:
    """Return the rendered compose model, or skip when Compose is unavailable."""
    docker = shutil.which("docker")
    if docker is None:
        _unavailable("no docker executable on PATH")

    docker_config = tmp_path / "docker-config"
    docker_config.mkdir(exist_ok=True)
    # Docker Desktop keeps its bundled Compose plugin beside the CLI,
    # but a clean DOCKER_CONFIG hides that discovery path on Windows.
    plugin_dir = Path(docker).parent.parent / "cli-plugins"
    if plugin_dir.is_dir():
        (docker_config / "config.json").write_text(
            json.dumps({"cliPluginsExtraDirs": [str(plugin_dir)]}), encoding="utf-8"
        )
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(_STRIPPED_PREFIXES)}
    env.update({"DOCKER_CONFIG": str(docker_config), **env_overrides})

    version = subprocess.run([docker, "compose", "version"], capture_output=True, text=True, env=env, timeout=10)
    if version.returncode != 0:
        _unavailable(version.stderr.strip() or f"exit {version.returncode}")

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
