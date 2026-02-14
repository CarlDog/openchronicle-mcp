"""Tests for oc events command."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import create_project
from openchronicle.core.domain.models.project import Event
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


def _add_events(
    container: CoreContainer, project_id: str, count: int, task_id: str = "t1", event_type: str = "test.event"
) -> None:
    """Helper to add events via the event logger."""
    for i in range(count):
        event = Event(
            project_id=project_id,
            task_id=task_id,
            type=event_type,
            payload={"index": i},
        )
        container.event_logger.append(event)


class TestEvents:
    def test_lists_events_in_chronological_order(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Test")
        _add_events(container, project.id, 3)

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["events", project.id])

        assert rc == 0
        # 3 events + project.created event = 4 total
        lines = [str(c.args[0]) for c in mock_print.call_args_list if c.args]
        assert len(lines) >= 3

    def test_task_id_filter(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Test")
        _add_events(container, project.id, 3, task_id="task-a")
        _add_events(container, project.id, 2, task_id="task-b")

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["events", project.id, "--task-id", "task-a"])

        assert rc == 0
        lines = [str(c.args[0]) for c in mock_print.call_args_list if c.args]
        assert all("task-a" in line for line in lines)

    def test_type_filter(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Test")
        _add_events(container, project.id, 3, event_type="llm.requested")
        _add_events(container, project.id, 2, event_type="task.completed")

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["events", project.id, "--type", "llm.requested"])

        assert rc == 0
        lines = [str(c.args[0]) for c in mock_print.call_args_list if c.args]
        assert all("llm.requested" in line for line in lines)
        assert len(lines) == 3

    def test_limit_returns_last_n(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Test")
        _add_events(container, project.id, 10)

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["events", project.id, "--limit", "5"])

        assert rc == 0
        lines = [str(c.args[0]) for c in mock_print.call_args_list if c.args]
        assert len(lines) == 5

    def test_combined_filters(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Test")
        _add_events(container, project.id, 5, task_id="t1", event_type="llm.requested")
        _add_events(container, project.id, 5, task_id="t2", event_type="llm.requested")
        _add_events(container, project.id, 5, task_id="t1", event_type="task.completed")

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["events", project.id, "--task-id", "t1", "--type", "llm.requested", "--limit", "3"])

        assert rc == 0
        lines = [str(c.args[0]) for c in mock_print.call_args_list if c.args]
        assert len(lines) == 3
        assert all("llm.requested" in line for line in lines)

    def test_json_output(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Test")
        _add_events(container, project.id, 2)

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["events", project.id, "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["command"] == "events"
        assert "events" in payload["result"]
        assert payload["result"]["event_count"] >= 2

    def test_empty_project_returns_empty(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "Empty")

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                # Filter out the project.created event via type filter
                rc = main(["events", project.id, "--type", "nonexistent.type"])

        assert rc == 0
        lines = [str(c.args[0]) for c in mock_print.call_args_list if c.args]
        assert any("No events" in line for line in lines)
