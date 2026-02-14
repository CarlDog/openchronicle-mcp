"""Tests for oc convo delete command."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import create_conversation
from openchronicle.core.domain.models.conversation import Turn
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


class TestConvoDelete:
    def test_without_force_errors(self, container: CoreContainer) -> None:
        convo = create_conversation.execute(
            storage=container.storage,
            convo_store=container.storage,
            emit_event=container.event_logger.append,
        )

        with patch("builtins.print"):
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["convo", "delete", convo.id])

        assert rc == 1

    def test_with_force_deletes(self, container: CoreContainer) -> None:
        convo = create_conversation.execute(
            storage=container.storage,
            convo_store=container.storage,
            emit_event=container.event_logger.append,
        )

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["convo", "delete", convo.id, "--force"])

        assert rc == 0
        output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
        assert "Deleted" in output

        # Verify gone
        assert container.storage.get_conversation(convo.id) is None

    def test_json_force_output(self, container: CoreContainer) -> None:
        convo = create_conversation.execute(
            storage=container.storage,
            convo_store=container.storage,
            emit_event=container.event_logger.append,
        )

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["convo", "delete", convo.id, "--force", "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["command"] == "convo.delete"
        assert payload["result"]["rows_deleted"] >= 1

    def test_nonexistent_conversation_errors(self, container: CoreContainer) -> None:
        with patch("builtins.print"):
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["convo", "delete", "nonexistent", "--force"])

        assert rc == 1

    def test_cascade_verified(self, container: CoreContainer) -> None:
        """After delete, turns/memory/events are all gone."""
        convo = create_conversation.execute(
            storage=container.storage,
            convo_store=container.storage,
            emit_event=container.event_logger.append,
        )
        # Add a turn
        turn = Turn(conversation_id=convo.id, turn_index=0, user_text="hi", assistant_text="hello")
        container.storage.add_turn(turn)

        with patch("builtins.print"):
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["convo", "delete", convo.id, "--force"])

        assert rc == 0
        assert container.storage.list_turns(convo.id) == []
        assert container.storage.list_events(task_id=convo.id) == []
