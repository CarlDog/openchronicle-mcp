"""FTS5 search tests for v3 — memory full-text search only.

v2 turn-search FTS coverage was dropped along with the turns table.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest

from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore, _fts5_available


def _store(tmp_path: Any) -> SqliteStore:
    store = SqliteStore(str(tmp_path / "test.db"))
    store.init_schema()
    return store


def _add_memory(
    store: SqliteStore,
    content: str = "test content",
    tags: str = "[]",
    pinned: bool = False,
    project_id: str | None = None,
) -> str:
    mem_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    store._conn.execute(
        """INSERT INTO memory_items (id, content, tags, pinned,
           project_id, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (mem_id, content, tags, int(pinned), project_id, "test", now),
    )
    return mem_id


# ── FTS5 detection ────────────────────────────────────────────────


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

    def test_triggers_created(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        triggers = [
            r[0]
            for r in store._conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()
        ]
        assert "memory_fts_ai" in triggers
        assert "memory_fts_ad" in triggers
        assert "memory_fts_au" in triggers

    def test_idempotent_init(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        store._ensure_fts5()
        assert store._fts5_active is True


# ── FTS5 memory search ───────────────────────────────────────────


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
        assert store.search_memory("Haskell", include_pinned=False) == []

    def test_pinned_always_included(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Standing rule: use black", pinned=True)
        _add_memory(store, content="Python is great")

        results = store.search_memory("Python", include_pinned=True)
        pinned = [r for r in results if r.pinned]
        assert len(pinned) >= 1

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

    def test_top_k_limit(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        for i in range(5):
            _add_memory(store, content=f"Python example {i}")
        results = store.search_memory("Python", include_pinned=False, top_k=3)
        assert len(results) == 3


# ── FTS5 query escaping ──────────────────────────────────────────


class TestFTS5QueryEscaping:
    def test_special_chars_dont_crash(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python is great")
        # Various FTS5-special tokens that would otherwise raise
        for query in ('AND', 'OR', 'NOT', '*', '^', 'NEAR', ':', '"'):
            store.search_memory(query, include_pinned=False)

    def test_fts5_operators_neutralized(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _add_memory(store, content="Python is great")
        # An OR-like query that contains the literal token "OR" should not error
        results = store.search_memory("Python OR JavaScript", include_pinned=False)
        # Tokens are escaped + OR-joined so the literal "Python" still matches
        assert len(results) == 1
