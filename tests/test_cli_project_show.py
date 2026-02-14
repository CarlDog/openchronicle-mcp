"""Tests for oc show-project command."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import create_project, register_agent
from openchronicle.interfaces.cli.main import main


@pytest.fixture()
def _stub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OC_LLM_PROVIDER", "stub")


@pytest.fixture()
def container(tmp_path: Path, _stub_env: None) -> Iterator[CoreContainer]:
    db_path = tmp_path / "test.db"
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("OC_DB_PATH", str(db_path))
    c = CoreContainer()
    yield c
    monkeypatch.undo()


class TestShowProject:
    def test_shows_project_detail(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Test Project")
        register_agent.execute(container.orchestrator, project.id, "Agent1", "worker")

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["show-project", project.id])

        assert rc == 0
        output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
        assert "Test Project" in output
        assert "Agent1" in output

    def test_json_output(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "JSON Project")

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["show-project", project.id, "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["command"] == "show-project"
        result = payload["result"]
        assert result["name"] == "JSON Project"
        assert "agents" in result
        assert "task_status_counts" in result
        assert "conversation_count" in result

    def test_nonexistent_project_returns_error(self, container: CoreContainer) -> None:
        with patch("builtins.print"):
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["show-project", "nonexistent-id"])

        assert rc == 1

    def test_empty_project_shows_zero_counts(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Empty Project")

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["show-project", project.id, "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        result = payload["result"]
        assert result["total_tasks"] == 0
        assert result["conversation_count"] == 0
        assert result["agents"] == []
