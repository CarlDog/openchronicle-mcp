"""Tests for SqliteStore delete_conversation and delete_memory."""

from __future__ import annotations

from pathlib import Path

import pytest

from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event, Project
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


@pytest.fixture()
def store(tmp_path: Path) -> SqliteStore:
    db_path = tmp_path / "test.db"
    s = SqliteStore(str(db_path))
    s.init_schema()
    # Create a parent project for FK constraints
    p = Project(id="p1", name="test")
    s.add_project(p)
    return s


class TestDeleteConversation:
    def test_cascade_removes_turns_memory_events(self, store: SqliteStore) -> None:
        """delete_conversation removes turns, memory items, and events."""
        convo = Conversation(project_id="p1", title="test")
        store.add_conversation(convo)

        turn = Turn(conversation_id=convo.id, turn_index=0, user_text="hi", assistant_text="hello")
        store.add_turn(turn)

        mem = MemoryItem(content="remember this", project_id="p1", conversation_id=convo.id)
        store.add_memory(mem)

        event = Event(project_id="p1", task_id=convo.id, type="test.event")
        event.compute_hash()
        store.append_event(event)

        deleted = store.delete_conversation(convo.id)

        assert deleted >= 4  # convo + turn + memory + event
        assert store.get_conversation(convo.id) is None
        assert store.list_turns(convo.id) == []
        assert store.list_events(task_id=convo.id) == []

    def test_nonexistent_conversation_returns_zero(self, store: SqliteStore) -> None:
        deleted = store.delete_conversation("nonexistent-id")
        assert deleted == 0

    def test_transaction_integrity(self, store: SqliteStore) -> None:
        """If conversation exists but has no related rows, still deletes the conversation."""
        convo = Conversation(project_id="p1", title="empty")
        store.add_conversation(convo)

        deleted = store.delete_conversation(convo.id)
        assert deleted == 1  # just the conversation row
        assert store.get_conversation(convo.id) is None


class TestDeleteMemory:
    def test_deletes_item_and_cleans_turn_refs(self, store: SqliteStore) -> None:
        """delete_memory removes item and cleans up memory_written_ids in turns."""
        convo = Conversation(project_id="p1", title="test")
        store.add_conversation(convo)

        turn = Turn(conversation_id=convo.id, turn_index=0, user_text="hi", assistant_text="hello")
        store.add_turn(turn)

        mem = MemoryItem(content="remember this", project_id="p1", conversation_id=convo.id)
        store.add_memory(mem)
        store.link_memory_to_turn(turn.id, mem.id)

        linked_turn = store.list_turns(convo.id)[0]
        assert mem.id in linked_turn.memory_written_ids

        result = store.delete_memory(mem.id)

        assert result is True
        assert store.get_memory(mem.id) is None

        updated_turn = store.list_turns(convo.id)[0]
        assert mem.id not in updated_turn.memory_written_ids

    def test_nonexistent_memory_returns_false(self, store: SqliteStore) -> None:
        result = store.delete_memory("nonexistent-id")
        assert result is False

    def test_multiple_memories_linked_to_turn(self, store: SqliteStore) -> None:
        """Deleting one memory doesn't affect the other in memory_written_ids."""
        convo = Conversation(project_id="p1", title="test")
        store.add_conversation(convo)

        turn = Turn(conversation_id=convo.id, turn_index=0, user_text="hi", assistant_text="hello")
        store.add_turn(turn)

        mem1 = MemoryItem(content="first", project_id="p1", conversation_id=convo.id)
        mem2 = MemoryItem(content="second", project_id="p1", conversation_id=convo.id)
        store.add_memory(mem1)
        store.add_memory(mem2)
        store.link_memory_to_turn(turn.id, mem1.id)
        store.link_memory_to_turn(turn.id, mem2.id)

        store.delete_memory(mem1.id)

        updated_turn = store.list_turns(convo.id)[0]
        assert mem1.id not in updated_turn.memory_written_ids
        assert mem2.id in updated_turn.memory_written_ids
