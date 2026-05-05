"""Tests for FTS5 full-text search — detection, memory search, turn search, triggers."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

mcp_mod = pytest.importorskip("mcp")  # noqa: F841

from openchronicle.core.infrastructure.persistence.sqlite_store import (  # noqa: E402
    SqliteStore,
    _fts5_available,
)

# ── Helpers ───────────────────────────────────────────────────────


def _store(tmp_path: Any) -> SqliteStore:
    """Create a fresh SqliteStore with FTS5 enabled."""
    store = SqliteStore(str(tmp_path / "test.db"))
    store.init_schema()
    return store


def _add_memory(
    store: SqliteStore,
    content: str = "test content",
    tags: str = "[]",
    pinned: bool = False,
    conversation_id: str | None = None,
    project_id: str | None = None,
) -> str:
    """Insert a memory item directly and return its id."""
    mem_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    store._conn.execute(
        """INSERT INTO memory_items (id, content, tags, pinned, conversation_id,
           project_id, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (mem_id, content, tags, int(pinned), conversation_id, project_id, "test", now),
    )
    return mem_id


def _add_turn(
    store: SqliteStore,
    user_text: str = "hello",
    assistant_text: str = "hi there",
    conversation_id: str = "convo-1",
    turn_index: int = 0,
) -> str:
    """Insert a turn directly and return its id."""
    turn_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    store._conn.execute(
        """INSERT INTO turns (id, conversation_id, turn_index, user_text,
           assistant_text, provider, model, routing_reasons, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            turn_id,
            conversation_id,
            turn_index,
            user_text,
            assistant_text,
            "stub",
            "stub-model",
            "[]",
            now,
        ),
    )
    return turn_id


def _add_conversation(store: SqliteStore, convo_id: str = "convo-1") -> str:
    """Insert a conversation directly."""
    now = datetime.now(UTC).isoformat()
    proj_id = str(uuid.uuid4())
    store._conn.execute(
        "INSERT OR IGNORE INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
        (proj_id, "test", "{}", now),
    )
    store._conn.execute(
        """INSERT INTO conversations (id, project_id, title, created_at)
           VALUES (?, ?, ?, ?)""",
        (convo_id, proj_id, "test convo", now),
    )
    return convo_id


# ── FTS5 Detection ────────────────────────────────────────────────


class TestFTS5Detection:
    def test_fts5_available_returns_true(self, tmp_path: Any) -> None:
        conn = sqlite3.connect(str(tmp_path / "probe.db"))
        assert _fts5_available(conn) is True
        conn.close()

    def test_fts5_active_after_init(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        assert store._fts5_active is True

    def test_fts5_disabled_by_env(self, tmp_path: Any) -> None:
        with patch.dict("os.environ", {"OC_SEARCH_FTS5_ENABLED": "0"}):
            store = SqliteStore(str(tmp_path / "test.db"))
            store.init_schema()
        assert store._fts5_active is False

    def test_virtual_tables_created(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        tables = [
            r[0]
            for r in store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts'"
            ).fetchall()
        ]
        assert "memory_fts" in tables
        assert "turns_fts" in tables

    def test_triggers_created(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        triggers = [r[0] for r in store._conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()]
        assert "memory_fts_ai" in triggers
        assert "memory_fts_ad" in triggers
        assert "memory_fts_au" in triggers
        assert "turns_fts_ai" in triggers
        assert "turns_fts_ad" in triggers
        assert "turns_fts_au" in triggers

    def test_idempotent_init(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        # Re-run should not raise
        store._ensure_fts5()
        assert store._fts5_active is True


# ── FTS5 Memory Search ───────────────────────────────────────────


class TestFTS5MemorySearch:
    def test_basic_match(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python is a great language")
        _add_memory(store, content="JavaScript is also popular")

        results = store.search_memory("Python", include_pinned=False)
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_no_match(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python is great")

        results = store.search_memory("Haskell", include_pinned=False)
        assert len(results) == 0

    def test_bm25_ranking(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        # Item with more Python mentions should rank higher
        _add_memory(store, content="Python Python Python programming language")
        _add_memory(store, content="Python is okay")
        _add_memory(store, content="JavaScript is great")

        results = store.search_memory("Python", include_pinned=False, top_k=10)
        assert len(results) == 2
        # Both should contain Python
        assert all("Python" in r.content for r in results)

    def test_pinned_always_included(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Standing rule: use black", pinned=True)
        _add_memory(store, content="Python is great")

        results = store.search_memory("Python", include_pinned=True)
        pinned = [r for r in results if r.pinned]
        assert len(pinned) >= 1
        assert "Standing rule" in pinned[0].content

    def test_pinned_dedup(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python convention", pinned=True)

        results = store.search_memory("Python", include_pinned=True, top_k=10)
        ids = [r.id for r in results]
        assert len(ids) == len(set(ids)), "Duplicate items in results"

    def test_scope_filter_project(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        now = datetime.now(UTC).isoformat()
        store._conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            ("proj-a", "A", "{}", now),
        )
        store._conn.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            ("proj-b", "B", "{}", now),
        )
        _add_memory(store, content="Python in project A", project_id="proj-a")
        _add_memory(store, content="Python in project B", project_id="proj-b")

        results = store.search_memory("Python", include_pinned=False, project_id="proj-a")
        assert len(results) == 1
        assert results[0].project_id == "proj-a"

    def test_scope_filter_conversation(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "c1")
        _add_conversation(store, "c2")
        _add_memory(store, content="Python discussed here", conversation_id="c1")
        _add_memory(store, content="Python discussed there", conversation_id="c2")

        results = store.search_memory("Python", include_pinned=False, conversation_id="c1")
        assert len(results) == 1
        assert results[0].conversation_id == "c1"

    def test_empty_query(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python is great")

        results = store.search_memory("", include_pinned=False)
        assert len(results) == 0

    def test_top_k_limit(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        for i in range(5):
            _add_memory(store, content=f"Python example {i}")

        results = store.search_memory("Python", include_pinned=False, top_k=3)
        assert len(results) == 3

    def test_tag_search(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Some note", tags='["python", "convention"]')
        _add_memory(store, content="Other note", tags='["javascript"]')

        results = store.search_memory("convention", include_pinned=False)
        assert len(results) == 1
        assert "Some note" in results[0].content

    def test_pinned_items_do_not_crowd_search_results(self, tmp_path: Any) -> None:
        """Pinned items must not reduce the budget for non-pinned search results."""
        store = _store(tmp_path)
        # Create many pinned items (more than top_k)
        for i in range(20):
            _add_memory(store, content=f"Pinned convention #{i}", pinned=True)
        # Create a searchable non-pinned item
        _add_memory(store, content="Carl Ashcombe is a bookstore owner")

        # Search with top_k smaller than pinned count
        results = store.search_memory("Ashcombe", include_pinned=True, top_k=5)
        non_pinned = [r for r in results if not r.pinned]
        assert len(non_pinned) >= 1, "Non-pinned search result should not be crowded out by pinned items"
        assert any("Ashcombe" in r.content for r in non_pinned)

    def test_pinned_crowding_with_tag_filter(self, tmp_path: Any) -> None:
        """When tag filter excludes pinned items, search results fill the full budget."""
        store = _store(tmp_path)
        # Pinned items with different tags
        for i in range(10):
            _add_memory(store, content=f"Pinned rule #{i}", pinned=True, tags='["convention"]')
        # Non-pinned items with story tags
        _add_memory(store, content="Character profile: Carl", tags='["story", "character"]')
        _add_memory(store, content="Character profile: Max", tags='["story", "character"]')

        # Search with tags that exclude all pinned items
        results = store.search_memory("Character", include_pinned=True, top_k=5, tags=["story", "character"])
        assert len(results) == 2
        assert all("Character" in r.content for r in results)
        assert not any(r.pinned for r in results)


# ── FTS5 Fallback Search ─────────────────────────────────────────


class TestFTS5FallbackSearch:
    def test_fallback_when_disabled(self, tmp_path: Any) -> None:
        with patch.dict("os.environ", {"OC_SEARCH_FTS5_ENABLED": "0"}):
            store = SqliteStore(str(tmp_path / "test.db"))
            store.init_schema()

        assert store._fts5_active is False
        _add_memory(store, content="Python is great")

        results = store.search_memory("Python", include_pinned=False)
        assert len(results) == 1

    def test_fallback_pinned_still_included(self, tmp_path: Any) -> None:
        with patch.dict("os.environ", {"OC_SEARCH_FTS5_ENABLED": "0"}):
            store = SqliteStore(str(tmp_path / "test.db"))
            store.init_schema()

        _add_memory(store, content="Always remember this", pinned=True)
        _add_memory(store, content="Python is great")

        results = store.search_memory("Python", include_pinned=True)
        pinned = [r for r in results if r.pinned]
        assert len(pinned) >= 1

    def test_fallback_scoring_prefers_keyword_matches(self, tmp_path: Any) -> None:
        with patch.dict("os.environ", {"OC_SEARCH_FTS5_ENABLED": "0"}):
            store = SqliteStore(str(tmp_path / "test.db"))
            store.init_schema()

        _add_memory(store, content="Python Python Python")
        _add_memory(store, content="Java is popular")

        results = store.search_memory("Python", include_pinned=False, top_k=10)
        assert len(results) >= 1
        assert "Python" in results[0].content


# ── FTS5 Turn Search ─────────────────────────────────────────────


class TestFTS5TurnSearch:
    def test_user_text_match(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        _add_turn(store, user_text="Tell me about Python", assistant_text="Sure!")

        results = store.search_turns("Python")
        assert len(results) == 1
        assert "Python" in results[0].user_text

    def test_assistant_text_match(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        _add_turn(store, user_text="Tell me something", assistant_text="Python is great")

        results = store.search_turns("Python")
        assert len(results) == 1
        assert "Python" in results[0].assistant_text

    def test_conversation_filter(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        _add_conversation(store, "convo-2")
        _add_turn(store, user_text="Python here", conversation_id="convo-1")
        _add_turn(
            store,
            user_text="Python there",
            conversation_id="convo-2",
            turn_index=0,
        )

        results = store.search_turns("Python", conversation_id="convo-1")
        assert len(results) == 1
        assert results[0].conversation_id == "convo-1"

    def test_no_match(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        _add_turn(store, user_text="Hello", assistant_text="Hi")

        results = store.search_turns("Python")
        assert len(results) == 0

    def test_empty_query(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        _add_turn(store, user_text="Python stuff")

        results = store.search_turns("")
        assert len(results) == 0

    def test_top_k(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        for i in range(5):
            _add_turn(
                store,
                user_text=f"Python example {i}",
                conversation_id="convo-1",
                turn_index=i,
            )

        results = store.search_turns("Python", top_k=3)
        assert len(results) == 3

    def test_disabled_returns_empty(self, tmp_path: Any) -> None:
        with patch.dict("os.environ", {"OC_SEARCH_FTS5_ENABLED": "0"}):
            store = SqliteStore(str(tmp_path / "test.db"))
            store.init_schema()

        _add_conversation(store, "convo-1")
        _add_turn(store, user_text="Python stuff")

        results = store.search_turns("Python")
        assert len(results) == 0

    def test_bm25_ranking(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        _add_turn(
            store,
            user_text="Python Python Python",
            assistant_text="yes",
            turn_index=0,
        )
        _add_turn(
            store,
            user_text="Python once",
            assistant_text="ok",
            turn_index=1,
        )

        results = store.search_turns("Python", top_k=10)
        assert len(results) == 2


# ── FTS5 Trigger Sync ────────────────────────────────────────────


class TestFTS5TriggerSync:
    def test_insert_then_search_finds_it(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Rust programming language")

        results = store.search_memory("Rust", include_pinned=False)
        assert len(results) == 1

    def test_delete_then_search_gone(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        mem_id = _add_memory(store, content="Rust programming language")

        # Delete via SQL (simulating delete_memory cascade)
        store._conn.execute("DELETE FROM memory_items WHERE id = ?", (mem_id,))

        results = store.search_memory("Rust", include_pinned=False)
        assert len(results) == 0

    def test_update_reflected_in_search(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        mem_id = _add_memory(store, content="Rust programming")

        # Update content
        store._conn.execute(
            "UPDATE memory_items SET content = ? WHERE id = ?",
            ("Go programming", mem_id),
        )

        assert len(store.search_memory("Rust", include_pinned=False)) == 0
        assert len(store.search_memory("Go", include_pinned=False)) == 1

    def test_turn_delete_trigger(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_conversation(store, "convo-1")
        turn_id = _add_turn(store, user_text="Rust is fast")

        assert len(store.search_turns("Rust")) == 1

        store._conn.execute("DELETE FROM turns WHERE id = ?", (turn_id,))

        assert len(store.search_turns("Rust")) == 0


# ── FTS5 Query Escaping ──────────────────────────────────────────


class TestFTS5QueryEscaping:
    def test_special_chars_dont_crash(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python is great")

        # These should not raise
        store.search_memory("AND OR NOT", include_pinned=False)
        store.search_memory("foo*bar", include_pinned=False)
        store.search_memory('hello "world"', include_pinned=False)
        store.search_memory("NEAR(a, b)", include_pinned=False)

    def test_fts5_operators_neutralized(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python AND Java")

        # Searching for literal "AND" should work, not be treated as operator
        results = store.search_memory("AND", include_pinned=False)
        assert len(results) == 1

    def test_empty_and_whitespace(self, tmp_path: Any) -> None:
        assert SqliteStore._fts5_escape("") == ""
        assert SqliteStore._fts5_escape("   ") == ""

