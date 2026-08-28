"""SQLite-backed memory + project storage for v3."""

from __future__ import annotations

import functools
import json
import logging
import os
import random
import sqlite3
import string
import struct
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Concatenate, Literal

from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND, PROJECT_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.memory_store_port import DEFAULT_PINNED_LIMIT, MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.domain.time_utils import utc_now
from openchronicle.core.infrastructure.persistence import migrator
from openchronicle.core.infrastructure.persistence.backup import backup_from_connection
from openchronicle.core.infrastructure.persistence.row_mappers import (
    row_to_memory_item,
    row_to_project,
)

_LIKE_ESCAPE = "\\"

# How a search query treats pinned rows. Search asks two independent
# questions about a pin — may it FLOAT (policy: standing rules lead) and
# may it RANK (visibility: does it compete on relevance) — and these
# three modes are every combination that means anything:
#
#   "exclude" — neither. The caller passed include_pinned=False.
#               Scope is strict, matching list_memory.
#   "include" — rank but do not float. Pins compete on their merits.
#               Scope is with-global for pinned rows only: a standing
#               rule belonging to no project still applies inside one.
#   "only"    — the float query itself: which pins match this query.
#               Scope is with-global, same reason.
_PinnedMode = Literal["exclude", "include", "only"]


def _pinned_clauses(mode: _PinnedMode, project_id: str | None, alias: str = "") -> tuple[str, str, list[Any]]:
    """Return (pinned_clause, scope_clause, params) for a search query.

    Centralized because these two clauses have to agree across four
    call sites (FTS5 + the fallback's two branches + the float query);
    when they were inlined, the scope rule and the pinned rule drifted
    apart and pins became unreachable.
    """
    p = f"{alias}." if alias else ""
    params: list[Any] = []
    if mode == "exclude":
        pinned_clause = f"AND {p}pinned = 0"
        scope_clause = ""
        if project_id is not None:
            scope_clause = f"AND {p}project_id = ?"
            params.append(project_id)
        return pinned_clause, scope_clause, params

    pinned_clause = f"AND {p}pinned = 1" if mode == "only" else ""
    scope_clause = ""
    if project_id is not None:
        if mode == "only":
            scope_clause = f"AND ({p}project_id = ? OR {p}project_id IS NULL)"
        else:
            scope_clause = f"AND ({p}project_id = ? OR ({p}pinned = 1 AND {p}project_id IS NULL))"
        params.append(project_id)
    return pinned_clause, scope_clause, params


def _escape_like(value: str) -> str:
    """Escape LIKE metacharacters so a caller's string matches literally.

    Without this a project named "100%" would match every row, and "_"
    would match any single character. The escape character is substituted
    first so it doesn't double-escape the ones added after it.
    """
    for ch in (_LIKE_ESCAPE, "%", "_"):
        value = value.replace(ch, _LIKE_ESCAPE + ch)
    return value


_MEMORY_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    content, tags,
    content='memory_items', content_rowid='rowid'
)
"""

_MEMORY_FTS_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS memory_fts_ai AFTER INSERT ON memory_items BEGIN
        INSERT INTO memory_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
    END""",
    """CREATE TRIGGER IF NOT EXISTS memory_fts_ad AFTER DELETE ON memory_items BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content, tags)
            VALUES('delete', old.rowid, old.content, old.tags);
    END""",
    """CREATE TRIGGER IF NOT EXISTS memory_fts_au AFTER UPDATE ON memory_items BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content, tags)
            VALUES('delete', old.rowid, old.content, old.tags);
        INSERT INTO memory_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
    END""",
]

_logger = logging.getLogger(__name__)
_MEMORY_SEARCH_LIMIT = 200

# Application-level retry for BEGIN IMMEDIATE write-lock contention.
_BEGIN_MAX_RETRIES = 3
_BEGIN_BASE_DELAY = 0.5  # seconds


def _locked[**P, R](method: Callable[Concatenate[SqliteStore, P], R]) -> Callable[Concatenate[SqliteStore, P], R]:
    """Serialize a store method on the store's re-entrant lock.

    One SqliteStore holds one sqlite3.Connection shared across Starlette's
    sync-handler threadpool and maintenance worker threads. Without
    serialization, a statement issued by one thread lands inside another
    thread's open transaction on the same connection. Every method that
    touches ``self._conn`` must hold ``self._lock``; the RLock keeps
    same-thread nesting (e.g. ``update_project`` → ``get_project``, or
    nested ``transaction()`` savepoints) working.
    """

    @functools.wraps(method)
    def wrapper(self: SqliteStore, *args: P.args, **kwargs: P.kwargs) -> R:
        with self._lock:
            return method(self, *args, **kwargs)

    return wrapper


def _fts5_available(conn: sqlite3.Connection) -> bool:
    """Probe whether the SQLite build includes FTS5."""
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS _fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


class SqliteStore(StoragePort, MemoryStorePort):
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        # Serializes ALL use of the shared connection across threads
        # (request threadpool + maintenance workers). Guards
        # _transaction_depth and prevents cross-thread statement
        # interleaving inside an open transaction. See _locked.
        self._lock = threading.RLock()
        self._transaction_depth = 0
        self._configure_connection()
        # Empty means unset (compose ${VAR:-} injects "" for blank stack
        # env) — without the `or "1"` an empty var silently disabled FTS5.
        fts5_env = os.getenv("OC_SEARCH_FTS5_ENABLED", "").strip() or "1"
        self._fts5_user_enabled = fts5_env.lower() in {"1", "true", "yes", "on"}
        self._fts5_active: bool = False

    @_locked
    def close(self) -> None:
        self._conn.close()

    @_locked
    def init_schema(self) -> None:
        # Apply versioned migrations first — establishes projects,
        # memory_items, memory_embeddings, schema_version (idempotent).
        migrator.apply_pending(self._conn)
        # FTS5 is runtime-detected (not all SQLite builds have it), so it
        # lives outside the migrator and is set up conditionally here.
        self._ensure_fts5()

    def _begin_immediate_with_retry(self) -> None:
        for attempt in range(_BEGIN_MAX_RETRIES + 1):
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt >= _BEGIN_MAX_RETRIES:
                    raise
                delay = _BEGIN_BASE_DELAY * (2**attempt)
                jitter = delay * random.random() * 0.25
                total = delay + jitter
                _logger.warning(
                    "BEGIN IMMEDIATE failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    _BEGIN_MAX_RETRIES,
                    total,
                    exc,
                )
                time.sleep(total)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        # The lock is held for the WHOLE transaction (not just BEGIN), so a
        # second thread blocks until COMMIT/ROLLBACK instead of nesting a
        # BEGIN or landing statements inside this transaction. Same-thread
        # nesting re-enters the RLock and takes the savepoint path.
        with self._lock:
            is_outer = self._transaction_depth == 0
            savepoint_name = None
            if is_outer:
                self._begin_immediate_with_retry()
            else:
                savepoint_name = f"sp_{self._transaction_depth + 1}"
                self._conn.execute(f"SAVEPOINT {savepoint_name}")
            self._transaction_depth += 1
            try:
                yield self._conn
                if is_outer:
                    self._conn.execute("COMMIT")
                else:
                    self._conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
            except Exception:
                if is_outer:
                    self._conn.execute("ROLLBACK")
                else:
                    self._conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                    self._conn.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                raise
            finally:
                self._transaction_depth -= 1

    # ── Projects ────────────────────────────────────────────────────

    @_locked
    def add_project(self, project: Project) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            (project.id, project.name, json.dumps(project.metadata), project.created_at.isoformat()),
        )
        self._commit_if_needed()

    @_locked
    def list_projects(self, name_contains: str | None = None) -> list[Project]:
        cur = self._conn.cursor()
        if name_contains is not None:
            rows = cur.execute(
                "SELECT * FROM projects WHERE name LIKE ? ESCAPE ? ORDER BY created_at DESC",
                (f"%{_escape_like(name_contains)}%", _LIKE_ESCAPE),
            ).fetchall()
        else:
            rows = cur.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [row_to_project(r) for r in rows]

    @_locked
    def get_project(self, project_id: str) -> Project | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return row_to_project(row) if row else None

    @_locked
    def delete_project(self, project_id: str) -> int:
        with self.transaction():
            cur = self._conn.cursor()
            proj_row = cur.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone()
            if proj_row is None:
                raise NotFoundError(f"Project not found: {project_id}", code=PROJECT_NOT_FOUND)
            count_row = cur.execute(
                "SELECT COUNT(*) AS cnt FROM memory_items WHERE project_id=?",
                (project_id,),
            ).fetchone()
            deleted_memories = int(count_row["cnt"]) if count_row else 0
            cur.execute("DELETE FROM memory_items WHERE project_id=?", (project_id,))
            cur.execute("DELETE FROM projects WHERE id=?", (project_id,))
            return deleted_memories

    @_locked
    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Project:
        if name is None and metadata is None:
            raise ValueError("update_project requires at least one of name or metadata")
        cur = self._conn.cursor()
        set_clauses: list[str] = []
        params: list[Any] = []
        if name is not None:
            set_clauses.append("name = ?")
            params.append(name)
        if metadata is not None:
            set_clauses.append("metadata = ?")
            params.append(json.dumps(metadata))
        params.append(project_id)
        sql = f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?"
        cur.execute(sql, params)
        if cur.rowcount == 0:
            raise NotFoundError(f"Project not found: {project_id}", code=PROJECT_NOT_FOUND)
        self._commit_if_needed()
        updated = self.get_project(project_id)
        assert updated is not None  # row exists — we just updated it
        return updated

    # ── Memory ──────────────────────────────────────────────────────

    @_locked
    def add_memory(self, item: MemoryItem) -> None:
        cur = self._conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO memory_items (id, content, tags, created_at, pinned, project_id, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.content,
                    json.dumps(item.tags, sort_keys=True),
                    item.created_at.isoformat(),
                    1 if item.pinned else 0,
                    item.project_id,
                    item.source,
                    item.updated_at.isoformat() if item.updated_at else None,
                ),
            )
        except sqlite3.IntegrityError as exc:
            # The only FK on this table is project_id → projects. Translate
            # here (infrastructure is the layer that knows sqlite3) so a
            # wrong project id answers 404 / "Project not found" instead of
            # a raw "FOREIGN KEY constraint failed" surfacing as a 500 —
            # CLAUDE.md warns "freeform strings will fail", and they used
            # to fail with the worst possible message.
            if "FOREIGN KEY" in str(exc).upper():
                raise NotFoundError(
                    f"Project not found: {item.project_id}",
                    code=PROJECT_NOT_FOUND,
                ) from exc
            raise
        self._commit_if_needed()

    @_locked
    def get_memory(self, memory_id: str) -> MemoryItem | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM memory_items WHERE id=?", (memory_id,)).fetchone()
        return row_to_memory_item(row) if row else None

    @_locked
    def list_memory(
        self,
        limit: int | None = None,
        pinned_only: bool = False,
        offset: int = 0,
        project_id: str | None = None,
    ) -> list[MemoryItem]:
        cur = self._conn.cursor()
        where_clauses: list[str] = []
        params: list[Any] = []
        if pinned_only:
            where_clauses.append("pinned = 1")
        if project_id is not None:
            where_clauses.append("project_id = ?")
            params.append(project_id)
        sql = "SELECT * FROM memory_items"
        if where_clauses:
            sql += f" WHERE {' AND '.join(where_clauses)}"
        sql += " ORDER BY pinned DESC, created_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        if offset > 0:
            if limit is None:
                sql += " LIMIT -1"
            sql += " OFFSET ?"
            params.append(offset)
        rows = cur.execute(sql, params).fetchall()
        return [row_to_memory_item(r) for r in rows]

    @_locked
    def count_memory(self, project_id: str | None = None) -> int:
        cur = self._conn.cursor()
        if project_id is not None:
            row = cur.execute(
                "SELECT COUNT(*) AS cnt FROM memory_items WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        else:
            row = cur.execute("SELECT COUNT(*) AS cnt FROM memory_items").fetchone()
        return row["cnt"] if row else 0

    @_locked
    def list_memory_by_source(self, source: str, project_id: str | None = None) -> list[MemoryItem]:
        cur = self._conn.cursor()
        if project_id is not None:
            sql = "SELECT * FROM memory_items WHERE source = ? AND project_id = ? ORDER BY created_at DESC"
            rows = cur.execute(sql, (source, project_id)).fetchall()
        else:
            sql = "SELECT * FROM memory_items WHERE source = ? ORDER BY created_at DESC"
            rows = cur.execute(sql, (source,)).fetchall()
        return [row_to_memory_item(r) for r in rows]

    @_locked
    def set_pinned(self, memory_id: str, pinned: bool) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE memory_items SET pinned=? WHERE id=?",
            (1 if pinned else 0, memory_id),
        )
        if cur.rowcount == 0:
            raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
        self._commit_if_needed()

    @_locked
    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        now_iso = utc_now().isoformat()
        cur = self._conn.cursor()
        set_clauses: list[str] = ["updated_at = ?"]
        params: list[Any] = [now_iso]
        if content is not None:
            set_clauses.append("content = ?")
            params.append(content)
        if tags is not None:
            set_clauses.append("tags = ?")
            params.append(json.dumps(tags, sort_keys=True))
        params.append(memory_id)
        sql = f"UPDATE memory_items SET {', '.join(set_clauses)} WHERE id = ?"
        cur.execute(sql, params)
        if cur.rowcount == 0:
            raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
        self._commit_if_needed()
        return self.get_memory(memory_id)  # type: ignore[return-value]

    @_locked
    def delete_memory(self, memory_id: str) -> None:
        with self.transaction():
            cur = self._conn.cursor()
            cur.execute("DELETE FROM memory_items WHERE id = ?", (memory_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)

    # ── Embedding storage ───────────────────────────────────────────

    @staticmethod
    def _unpack_embedding(blob: bytes) -> list[float]:
        """Decode a float32 blob by its own length (4 bytes per float)."""
        return list(struct.unpack(f"{len(blob) // 4}f", blob))

    @_locked
    def save_embedding(
        self,
        memory_id: str,
        embedding: list[float],
        model: str,
    ) -> None:
        # The dimensions column records the FACT (length of the stored
        # vector), never a caller-supplied claim. Adapters can't always
        # control actual output length (Ollama returns whatever the model
        # returns regardless of the configured default), and a mismatched
        # claim made every subsequent read raise struct.error.
        blob = struct.pack(f"{len(embedding)}f", *embedding)
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO memory_embeddings (memory_id, embedding, model, dimensions, generated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                embedding = excluded.embedding,
                model = excluded.model,
                dimensions = excluded.dimensions,
                generated_at = excluded.generated_at
            """,
            (memory_id, blob, model, len(embedding), utc_now().isoformat()),
        )
        self._commit_if_needed()

    @_locked
    def get_embedding(self, memory_id: str) -> list[float] | None:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT embedding FROM memory_embeddings WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if row is None:
            return None
        # Unpack from the blob's own length, not the dimensions column —
        # heals any pre-existing row whose recorded claim disagrees.
        return self._unpack_embedding(row["embedding"])

    @_locked
    def list_embeddings(
        self,
        memory_ids: list[str] | None = None,
        model: str | None = None,
    ) -> dict[str, list[float]]:
        """List embeddings, optionally filtered by memory ids and/or model.

        Semantic search MUST pass ``model`` — vectors from different
        models live in different spaces, so mixing them either crashes
        the matmul (different dims) or silently corrupts ranking (same
        dims, meaningless cross-space similarities).
        """
        cur = self._conn.cursor()
        clauses: list[str] = []
        params: list[Any] = []
        if memory_ids is not None:
            placeholders = ",".join("?" for _ in memory_ids)
            clauses.append(f"memory_id IN ({placeholders})")
            params.extend(memory_ids)
        if model is not None:
            clauses.append("model = ?")
            params.append(model)
        sql = "SELECT memory_id, embedding FROM memory_embeddings"
        if clauses:
            sql += f" WHERE {' AND '.join(clauses)}"
        rows = cur.execute(sql, params).fetchall()
        result: dict[str, list[float]] = {}
        for row in rows:
            result[row["memory_id"]] = self._unpack_embedding(row["embedding"])
        return result

    @_locked
    def count_embeddings(self) -> int:
        cur = self._conn.cursor()
        row = cur.execute("SELECT COUNT(*) AS cnt FROM memory_embeddings").fetchone()
        return row["cnt"] if row else 0

    @_locked
    def count_stale_embeddings(self, current_model: str) -> int:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT COUNT(*) AS cnt FROM memory_embeddings WHERE model != ?",
            (current_model,),
        ).fetchone()
        return row["cnt"] if row else 0

    @_locked
    def get_embedding_model(self, memory_id: str) -> str | None:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT model FROM memory_embeddings WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        return row["model"] if row else None

    # ── Search ──────────────────────────────────────────────────────

    @_locked
    def pinned_items(
        self,
        project_id: str | None = None,
    ) -> list[MemoryItem]:
        cur = self._conn.cursor()
        params: list[Any] = []
        if project_id is not None:
            sql = """
                SELECT * FROM memory_items
                WHERE pinned=1 AND (project_id=? OR project_id IS NULL)
                ORDER BY created_at DESC, id DESC
            """
            params = [project_id]
        else:
            sql = """
                SELECT * FROM memory_items
                WHERE pinned=1
                ORDER BY created_at DESC, id DESC
            """
        return [row_to_memory_item(r) for r in cur.execute(sql, params).fetchall()]

    def _fts5_search_memory(
        self,
        query: str,
        limit: int,
        project_id: str | None = None,
        tags: list[str] | None = None,
        phrase: bool = False,
        pinned_mode: _PinnedMode = "exclude",
    ) -> list[MemoryItem]:
        escaped = self._fts5_escape(query, phrase=phrase)
        if not escaped:
            return []
        cur = self._conn.cursor()
        pinned_clause, scope_clause, scope_params = _pinned_clauses(pinned_mode, project_id, alias="m")
        params: list[Any] = [escaped, *scope_params]
        fetch_limit = limit * 4 if tags else limit
        params.append(fetch_limit)
        sql = f"""
            SELECT m.* FROM memory_fts fts
            JOIN memory_items m ON m.rowid = fts.rowid
            WHERE memory_fts MATCH ?
            {pinned_clause}
            {scope_clause}
            ORDER BY fts.rank, m.created_at DESC, m.id ASC
            LIMIT ?
        """
        items = [row_to_memory_item(r) for r in cur.execute(sql, params).fetchall()]
        if tags:
            items = [i for i in items if all(t in i.tags for t in tags)]
        return items[:limit]

    def _fallback_search_memory(
        self,
        query: str,
        limit: int,
        project_id: str | None = None,
        tags: list[str] | None = None,
        phrase: bool = False,
        pinned_mode: _PinnedMode = "exclude",
    ) -> list[MemoryItem]:
        q_tokens = self._normalize_tokens(query)
        cur = self._conn.cursor()
        pinned_clause, scope_clause, scope_params = _pinned_clauses(pinned_mode, project_id)
        params: list[Any] = [*scope_params, _MEMORY_SEARCH_LIMIT]
        sql = f"""
            SELECT * FROM memory_items
            WHERE 1=1
            {pinned_clause}
            {scope_clause}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
        """
        items = [row_to_memory_item(r) for r in cur.execute(sql, params).fetchall()]
        if tags:
            items = [i for i in items if all(t in i.tags for t in tags)]

        if phrase:
            # Fallback phrase semantics: case-insensitive substring of the
            # whitespace-normalized query — the closest analogue of the
            # FTS5 adjacent-tokens phrase match.
            needle = " ".join(query.split()).casefold()
            if not needle:
                return []
            items = [i for i in items if needle in " ".join(i.content.split()).casefold()]
            return items[:limit]

        def _score(item: MemoryItem) -> tuple[int, int, datetime, str]:
            tag_matches = self._tag_match_count(item.tags, q_tokens)
            keyword_matches = self._keyword_match_count(item.content, q_tokens)
            return (tag_matches, keyword_matches, item.created_at, item.id)

        items.sort(key=_score, reverse=True)
        return items[:limit]

    def _ranked_search(
        self,
        query: str,
        limit: int,
        project_id: str | None,
        tags: list[str] | None,
        phrase: bool,
        pinned_mode: _PinnedMode,
    ) -> list[MemoryItem]:
        """Dispatch to FTS5 or the fallback scorer.

        Deliberately NOT ``@_locked``: every caller already holds the
        store lock. Calling a locked method from inside another would
        rely on the lock being reentrant.
        """
        if self._fts5_active:
            return self._fts5_search_memory(query, limit, project_id, tags=tags, phrase=phrase, pinned_mode=pinned_mode)
        return self._fallback_search_memory(query, limit, project_id, tags=tags, phrase=phrase, pinned_mode=pinned_mode)

    @_locked
    def search_pinned(
        self,
        query: str,
        *,
        limit: int = DEFAULT_PINNED_LIMIT,
        project_id: str | None = None,
        tags: list[str] | None = None,
        phrase: bool = False,
    ) -> list[MemoryItem]:
        """Pinned items that MATCH the query — the float set.

        Distinct from ``pinned_items``, which enumerates every pin
        regardless of the query. Scope is with-global (see
        ``_pinned_clauses``).
        """
        if limit <= 0:
            return []
        return self._ranked_search(query, limit, project_id, tags, phrase, "only")[:limit]

    @_locked
    def search_memory(
        self,
        query: str,
        *,
        top_k: int = 8,
        project_id: str | None = None,
        include_pinned: bool = True,
        tags: list[str] | None = None,
        offset: int = 0,
        phrase: bool = False,
        exclude_ids: set[str] | None = None,
    ) -> list[MemoryItem]:
        # Pure ranking. The pinned FLOAT is application policy and lives
        # in the caller (see search_memory use case / EmbeddingService),
        # which passes the floated ids as exclude_ids so a floated pin
        # cannot also consume a slot in the ranking.
        effective_top_k = top_k + offset
        # Over-fetch by the exclusion size so removing floated rows
        # cannot shrink the page below top_k.
        fetch = effective_top_k + len(exclude_ids or ())
        ranked = self._ranked_search(query, fetch, project_id, tags, phrase, "include" if include_pinned else "exclude")
        if exclude_ids:
            ranked = [i for i in ranked if i.id not in exclude_ids]
        return ranked[offset : offset + top_k]

    # ── helpers ─────────────────────────────────────────────────────

    def _normalize_tokens(self, text: str) -> list[str]:
        cleaned = text.lower().translate(str.maketrans("", "", string.punctuation))
        return [token for token in cleaned.split() if token]

    def _tag_match_count(self, tags: list[str], q_tokens: list[str]) -> int:
        if not tags or not q_tokens:
            return 0
        count = 0
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in q_tokens:
                count += 1
                continue
            if any(token in tag_lower for token in q_tokens):
                count += 1
        return count

    def _keyword_match_count(self, content: str, q_tokens: list[str]) -> int:
        if not content or not q_tokens:
            return 0
        content_lower = content.lower()
        return sum(1 for token in q_tokens if token in content_lower)

    @staticmethod
    def _fts5_escape(query: str, *, phrase: bool = False) -> str:
        """Neutralize user input for FTS5 MATCH.

        Default: each whitespace token individually quoted and OR-joined
        (any-token match). ``phrase=True``: the whole query becomes ONE
        quoted FTS5 phrase, matching the tokens adjacently in order —
        "does the content literally contain this phrase" (Q21; before
        2026-08-17 this was not expressible at all).
        """
        if not query or not query.strip():
            return ""
        if phrase:
            clean = " ".join(query.replace('"', "").split())
            return f'"{clean}"' if clean else ""
        tokens = query.split()
        escaped = []
        for token in tokens:
            clean_token = token.replace('"', "")
            if clean_token:
                escaped.append(f'"{clean_token}"')
        return " OR ".join(escaped)

    # ── maintenance operations ──────────────────────────────────────
    # Exposed so maintenance jobs and the CLI never touch self._conn
    # directly — these must hold the store lock so VACUUM/backup can
    # never interleave another thread's open transaction.

    @_locked
    def vacuum(self) -> None:
        """WAL-checkpoint then VACUUM the database."""
        self._conn.execute("PRAGMA wal_checkpoint(FULL)")
        self._conn.execute("VACUUM")

    @_locked
    def integrity_check(self) -> str:
        """Run PRAGMA integrity_check; returns 'ok' when healthy."""
        return str(self._conn.execute("PRAGMA integrity_check").fetchone()[0])

    @_locked
    def schema_version(self) -> int:
        """Highest applied migration version."""
        return migrator.current_version(self._conn)

    @property
    def fts5_active(self) -> bool:
        """Whether search is running on FTS5 rather than the Python fallback.

        Worth surfacing on the health payload: search degrades silently, so
        without this a caller can't tell "results are poor" from "the fast
        path is unavailable".
        """
        return self._fts5_active

    @_locked
    def backup_to(self, dest: Path | str) -> Path:
        """Online backup to `dest` (atomic .tmp → rename).

        Holds the store lock for the whole copy so no other thread's
        statements interleave the page iteration. Blocks writers for
        the duration — acceptable at this deployment's DB size.
        """
        return backup_from_connection(self._conn, dest)

    # ── connection / migrations ─────────────────────────────────────

    def _configure_connection(self) -> None:
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._conn.execute("PRAGMA busy_timeout = 5000;")

    def _commit_if_needed(self) -> None:
        if self._transaction_depth == 0:
            self._conn.commit()

    def _ensure_fts5(self) -> None:
        if not self._fts5_user_enabled:
            _logger.info("FTS5 disabled by OC_SEARCH_FTS5_ENABLED")
            self._fts5_active = False
            return
        if not _fts5_available(self._conn):
            _logger.info("FTS5 not available in this SQLite build — using fallback search")
            self._fts5_active = False
            return

        cur = self._conn.cursor()
        cur.execute(_MEMORY_FTS_TABLE)
        for stmt in _MEMORY_FTS_TRIGGERS:
            cur.execute(stmt)
        self._commit_if_needed()

        (count,) = cur.execute("SELECT COUNT(*) FROM memory_fts").fetchone()
        if count == 0:
            _logger.info("FTS5 table memory_fts empty — rebuilding index")
            cur.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
        self._commit_if_needed()
        self._fts5_active = True
        _logger.info("FTS5 full-text search enabled")
