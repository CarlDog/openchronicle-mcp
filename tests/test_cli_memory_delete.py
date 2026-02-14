"""Tests for oc memory delete command."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from openchronicle.core.application.runtime.container import CoreContainer
from openchronicle.core.application.use_cases import create_conversation, create_project
from openchronicle.core.domain.models.conversation import Turn
from openchronicle.core.domain.models.memory_item import MemoryItem
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


class TestMemoryDelete:
    def test_delete_existing_item(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "test")
        mem = MemoryItem(content="remember this", project_id=project.id, source="manual")
        container.storage.add_memory(mem)

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["memory", "delete", mem.id])

        assert rc == 0
        output = "\n".join(str(c.args[0]) if c.args else "" for c in mock_print.call_args_list)
        assert "Deleted" in output
        assert container.storage.get_memory(mem.id) is None

    def test_json_output(self, container: CoreContainer) -> None:
        project = create_project.execute(container.orchestrator, "test")
        mem = MemoryItem(content="remember this", project_id=project.id, source="manual")
        container.storage.add_memory(mem)

        with patch("builtins.print") as mock_print:
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["memory", "delete", mem.id, "--json"])

        assert rc == 0
        raw = mock_print.call_args_list[0].args[0]
        payload = json.loads(raw)
        assert payload["ok"] is True
        assert payload["command"] == "memory.delete"
        assert payload["result"]["memory_id"] == mem.id

    def test_nonexistent_item_errors(self, container: CoreContainer) -> None:
        with patch("builtins.print"):
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["memory", "delete", "nonexistent"])

        assert rc == 1

    def test_turn_memory_written_ids_cleaned(self, container: CoreContainer) -> None:
        """After deleting memory, turn's memory_written_ids is cleaned up."""
        convo = create_conversation.execute(
            storage=container.storage,
            convo_store=container.storage,
            emit_event=container.event_logger.append,
        )
        turn = Turn(conversation_id=convo.id, turn_index=0, user_text="hi", assistant_text="hello")
        container.storage.add_turn(turn)

        mem = MemoryItem(content="remember this", project_id=convo.project_id, conversation_id=convo.id, source="turn")
        container.storage.add_memory(mem)
        container.storage.link_memory_to_turn(turn.id, mem.id)

        # Verify link exists
        linked_turn = container.storage.list_turns(convo.id)[0]
        assert mem.id in linked_turn.memory_written_ids

        with patch("builtins.print"):
            with patch(
                "openchronicle.interfaces.cli.main._build_container",
                return_value=container,
            ):
                rc = main(["memory", "delete", mem.id])

        assert rc == 0

        # Turn's memory_written_ids should be cleaned
        updated_turn = container.storage.list_turns(convo.id)[0]
        assert mem.id not in updated_turn.memory_written_ids
