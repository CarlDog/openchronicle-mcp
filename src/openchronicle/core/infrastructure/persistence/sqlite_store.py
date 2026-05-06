"""SQLite-backed memory + project storage for v3."""

from __future__ import annotations

import json
import logging
import os
import random
import sqlite3
import string
import struct
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openchronicle.core.domain.errors.error_codes import MEMORY_NOT_FOUND
from openchronicle.core.domain.exceptions import NotFoundError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.infrastructure.persistence import migrator
from openchronicle.core.infrastructure.persistence.row_mappers import (
    row_to_memory_item,
    row_to_project,
)

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
        self._transaction_depth = 0
        self._configure_connection()
        self._fts5_user_enabled = os.getenv("OC_SEARCH_FTS5_ENABLED", "1").lower() in {"1", "true", "yes", "on"}
        self._fts5_active: bool = False

    def close(self) -> None:
        self._conn.close()

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

    def add_project(self, project: Project) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            (project.id, project.name, json.dumps(project.metadata), project.created_at.isoformat()),
        )
        self._commit_if_needed()

    def list_projects(self) -> list[Project]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [row_to_project(r) for r in rows]

    def get_project(self, project_id: str) -> Project | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return row_to_project(row) if row else None

    # ── Memory ──────────────────────────────────────────────────────

    def add_memory(self, item: MemoryItem) -> None:
        cur = self._conn.cursor()
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
        self._commit_if_needed()

    def get_memory(self, memory_id: str) -> MemoryItem | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM memory_items WHERE id=?", (memory_id,)).fetchone()
        return row_to_memory_item(row) if row else None

    def list_memory(self, limit: int | None = None, pinned_only: bool = False, offset: int = 0) -> list[MemoryItem]:
        cur = self._conn.cursor()
        sql = "SELECT * FROM memory_items"
        params: list[int] = []
        if pinned_only:
            sql += " WHERE pinned=1"
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

    def list_memory_by_source(self, source: str, project_id: str | None = None) -> list[MemoryItem]:
        cur = self._conn.cursor()
        if project_id is not None:
            sql = "SELECT * FROM memory_items WHERE source = ? AND project_id = ? ORDER BY created_at DESC"
            rows = cur.execute(sql, (source, project_id)).fetchall()
        else:
            sql = "SELECT * FROM memory_items WHERE source = ? ORDER BY created_at DESC"
            rows = cur.execute(sql, (source,)).fetchall()
        return [row_to_memory_item(r) for r in rows]

    def set_pinned(self, memory_id: str, pinned: bool) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE memory_items SET pinned=? WHERE id=?",
            (1 if pinned else 0, memory_id),
        )
        if cur.rowcount == 0:
            raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)
        self._commit_if_needed()

    def update_memory(
        self,
        memory_id: str,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        now_iso = datetime.now(UTC).isoformat()
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

    def delete_memory(self, memory_id: str) -> None:
        with self.transaction():
            cur = self._conn.cursor()
            cur.execute("DELETE FROM memory_items WHERE id = ?", (memory_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"Memory not found: {memory_id}", code=MEMORY_NOT_FOUND)

    # ── Embedding storage ───────────────────────────────────────────

    def save_embedding(
        self,
        memory_id: str,
        embedding: list[float],
        model: str,
        dimensions: int,
    ) -> None:
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
            (memory_id, blob, model, dimensions, datetime.now(UTC).isoformat()),
        )
        self._commit_if_needed()

    def get_embedding(self, memory_id: str) -> list[float] | None:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT embedding, dimensions FROM memory_embeddings WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        if row is None:
            return None
        return list(struct.unpack(f"{row['dimensions']}f", row["embedding"]))

    def list_embeddings(
        self,
        memory_ids: list[str] | None = None,
    ) -> dict[str, list[float]]:
        cur = self._conn.cursor()
        if memory_ids is not None:
            placeholders = ",".join("?" for _ in memory_ids)
            rows = cur.execute(
                f"SELECT memory_id, embedding, dimensions FROM memory_embeddings WHERE memory_id IN ({placeholders})",
                memory_ids,
            ).fetchall()
        else:
            rows = cur.execute("SELECT memory_id, embedding, dimensions FROM memory_embeddings").fetchall()
        result: dict[str, list[float]] = {}
        for row in rows:
            result[row["memory_id"]] = list(struct.unpack(f"{row['dimensions']}f", row["embedding"]))
        return result

    def delete_embedding(self, memory_id: str) -> None:
        cur = self._conn.cursor()
        cur.execute("DELETE FROM memory_embeddings WHERE memory_id = ?", (memory_id,))
        self._commit_if_needed()

    def count_embeddings(self) -> int:
        cur = self._conn.cursor()
        row = cur.execute("SELECT COUNT(*) AS cnt FROM memory_embeddings").fetchone()
        return row["cnt"] if row else 0

    def count_stale_embeddings(self, current_model: str) -> int:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT COUNT(*) AS cnt FROM memory_embeddings WHERE model != ?",
            (current_model,),
        ).fetchone()
        return row["cnt"] if row else 0

    def get_embedding_model(self, memory_id: str) -> str | None:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT model FROM memory_embeddings WHERE memory_id = ?",
            (memory_id,),
        ).fetchone()
        return row["model"] if row else None

    # ── Search ──────────────────────────────────────────────────────

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
    ) -> list[MemoryItem]:
        escaped = self._fts5_escape(query)
        if not escaped:
            return []
        cur = self._conn.cursor()
        params: list[Any] = [escaped]
        scope_clause = ""
        if project_id is not None:
            scope_clause = "AND m.project_id = ?"
            params.append(project_id)
        fetch_limit = limit * 4 if tags else limit
        params.append(fetch_limit)
        sql = f"""
            SELECT m.* FROM memory_fts fts
            JOIN memory_items m ON m.rowid = fts.rowid
            WHERE memory_fts MATCH ?
            AND m.pinned = 0
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
    ) -> list[MemoryItem]:
        q_tokens = self._normalize_tokens(query)
        cur = self._conn.cursor()
        params: list[Any] = []
        if project_id is not None:
            sql = """
                SELECT * FROM memory_items
                WHERE project_id=? AND pinned=0
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """
            params = [project_id, _MEMORY_SEARCH_LIMIT]
        else:
            sql = """
                SELECT * FROM memory_items
                WHERE pinned=0
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            """
            params = [_MEMORY_SEARCH_LIMIT]
        items = [row_to_memory_item(r) for r in cur.execute(sql, params).fetchall()]
        if tags:
            items = [i for i in items if all(t in i.tags for t in tags)]

        def _score(item: MemoryItem) -> tuple[int, int, datetime, str]:
            tag_matches = self._tag_match_count(item.tags, q_tokens)
            keyword_matches = self._keyword_match_count(item.content, q_tokens)
            return (tag_matches, keyword_matches, item.created_at, item.id)

        items.sort(key=_score, reverse=True)
        return items[:limit]

    def search_memory(
        self,
        query: str,
        *,
        top_k: int = 8,
        project_id: str | None = None,
        include_pinned: bool = True,
        tags: list[str] | None = None,
        offset: int = 0,
    ) -> list[MemoryItem]:
        effective_top_k = top_k + offset
        pinned_items: list[MemoryItem] = []
        if include_pinned:
            pinned_items = self.pinned_items(project_id)
            if tags:
                pinned_items = [i for i in pinned_items if all(t in i.tags for t in tags)]
        if self._fts5_active:
            non_pinned = self._fts5_search_memory(query, effective_top_k, project_id, tags=tags)
        else:
            non_pinned = self._fallback_search_memory(query, effective_top_k, project_id, tags=tags)
        pinned_ids = {i.id for i in pinned_items}
        non_pinned = [i for i in non_pinned if i.id not in pinned_ids]
        non_pinned_page = non_pinned[offset : offset + top_k]
        if offset == 0:
            return list(pinned_items) + non_pinned_page
        return non_pinned_page

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
    def _fts5_escape(query: str) -> str:
        if not query or not query.strip():
            return ""
        tokens = query.split()
        escaped = []
        for token in tokens:
            clean = token.replace('"', "")
            if clean:
                escaped.append(f'"{clean}"')
        return " OR ".join(escaped)

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
