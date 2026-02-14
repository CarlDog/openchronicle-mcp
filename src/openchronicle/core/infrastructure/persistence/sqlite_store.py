from __future__ import annotations

import json
import logging
import random
import sqlite3
import string
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openchronicle.core.domain.models.conversation import Conversation, Turn
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import (
    Agent,
    Event,
    LLMUsage,
    Project,
    Resource,
    Span,
    SpanStatus,
    Task,
    TaskStatus,
)
from openchronicle.core.domain.ports.conversation_store_port import ConversationStorePort
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.infrastructure.persistence import schema
from openchronicle.core.infrastructure.persistence.row_mappers import (
    row_to_agent,
    row_to_conversation,
    row_to_event,
    row_to_llm_usage,
    row_to_memory_item,
    row_to_project,
    row_to_resource,
    row_to_span,
    row_to_task,
    row_to_turn,
)

_logger = logging.getLogger(__name__)

_MEMORY_SEARCH_LIMIT = 200

# Application-level retry for BEGIN IMMEDIATE write-lock contention.
# SQLite's busy_timeout (5s) handles short contention internally. These
# parameters add a second retry layer: back off between attempts so the
# lock holder can finish, turning a hard crash into a recoverable wait.
_BEGIN_MAX_RETRIES = 3
_BEGIN_BASE_DELAY = 0.5  # seconds; exponential: 0.5, 1.0, 2.0


class SqliteStore(StoragePort, ConversationStorePort, MemoryStorePort):
    def __init__(self, db_path: str = "data/openchronicle.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.autocommit = True  # type: ignore[attr-defined]  # Python 3.12+
        self._conn.row_factory = sqlite3.Row
        self._transaction_depth = 0
        self._configure_connection()

    def init_schema(self) -> None:
        cur = self._conn.cursor()
        for stmt in schema.ALL_TABLES:
            cur.execute(stmt)
        self._commit_if_needed()
        self._ensure_parent_task_column()
        self._ensure_task_result_columns()
        self._ensure_conversation_mode_column()
        self._ensure_turn_memory_written_column()
        self._ensure_indexes()
        # Ensure crash recovery runs even for reused databases
        self.recover_stale_tasks()

    def _begin_immediate_with_retry(self) -> None:
        """Acquire write lock with application-level retry on contention.

        SQLite's busy_timeout (5s) handles short contention internally.
        This adds a second retry layer for sustained contention: back off
        between attempts so the holder can finish.
        """
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
        """Context manager for SQLite transactions with savepoint nesting."""

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

    # Projects
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

    # Agents
    def add_agent(self, agent: Agent) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO agents (id, project_id, role, name, provider, model, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                agent.id,
                agent.project_id,
                agent.role,
                agent.name,
                agent.provider,
                agent.model,
                json.dumps(agent.tags),
                agent.created_at.isoformat(),
            ),
        )
        self._commit_if_needed()

    def get_agent(self, agent_id: str) -> Agent | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
        return row_to_agent(row) if row else None

    def list_agents(self, project_id: str) -> list[Agent]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM agents WHERE project_id=? ORDER BY created_at ASC, id ASC", (project_id,)
        ).fetchall()
        return [row_to_agent(r) for r in rows]

    # Tasks
    def add_task(self, task: Task) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO tasks (id, project_id, agent_id, parent_task_id, type, payload, status, result_json, error_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.project_id,
                task.agent_id,
                task.parent_task_id,
                task.type,
                json.dumps(task.payload),
                task.status.value,
                task.result_json,
                task.error_json,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ),
        )
        self._commit_if_needed()

    def update_task_status(self, task_id: str, status: str) -> None:
        cur = self._conn.cursor()
        updated_at = datetime.now(UTC).isoformat()
        cur.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
            (status, updated_at, task_id),
        )
        self._commit_if_needed()

    def update_task_result(self, task_id: str, result_json: str, status: str) -> None:
        cur = self._conn.cursor()
        updated_at = datetime.now(UTC).isoformat()
        cur.execute(
            "UPDATE tasks SET result_json=?, status=?, updated_at=? WHERE id=?",
            (result_json, status, updated_at, task_id),
        )
        self._commit_if_needed()

    def update_task_error(self, task_id: str, error_json: str, status: str) -> None:
        cur = self._conn.cursor()
        updated_at = datetime.now(UTC).isoformat()
        cur.execute(
            "UPDATE tasks SET error_json=?, status=?, updated_at=? WHERE id=?",
            (error_json, status, updated_at, task_id),
        )
        self._commit_if_needed()

    def get_task(self, task_id: str) -> Task | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return row_to_task(row) if row else None

    def list_tasks_by_project(self, project_id: str) -> list[Task]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM tasks WHERE project_id=? ORDER BY created_at ASC, id ASC",
            (project_id,),
        ).fetchall()
        return [row_to_task(r) for r in rows]

    # Events
    def append_event(self, event: Event) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO events (id, project_id, task_id, agent_id, type, payload, created_at, prev_hash, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.project_id,
                event.task_id,
                event.agent_id,
                event.type,
                json.dumps(event.payload),
                event.created_at.isoformat(),
                event.prev_hash,
                event.hash,
            ),
        )
        self._commit_if_needed()

    def list_events(self, task_id: str | None = None, *, project_id: str | None = None) -> list[Event]:
        """List events filtered by project and/or task with deterministic ordering.

        Ordering: created_at ASC, then id ASC.
        """
        cur = self._conn.cursor()
        sql = "SELECT * FROM events"
        params: list[str] = []
        conditions: list[str] = []

        if project_id is not None:
            conditions.append("project_id = ?")
            params.append(project_id)
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY created_at ASC, id ASC"
        rows = cur.execute(sql, params).fetchall()
        return [row_to_event(r) for r in rows]

    # Resources
    def add_resource(self, resource: Resource) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO resources (id, project_id, kind, path, content_hash, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                resource.id,
                resource.project_id,
                resource.kind,
                resource.path,
                resource.content_hash,
                json.dumps(resource.metadata),
                resource.created_at.isoformat(),
            ),
        )
        self._commit_if_needed()

    def list_resources(self, project_id: str) -> list[Resource]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT * FROM resources WHERE project_id=?", (project_id,)).fetchall()
        return [row_to_resource(r) for r in rows]

    # Spans
    def add_span(self, span: Span) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """INSERT INTO spans
            (id, task_id, agent_id, name, start_event_id, end_event_id, status, created_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                span.id,
                span.task_id,
                span.agent_id,
                span.name,
                span.start_event_id,
                span.end_event_id,
                span.status.value,
                span.created_at.isoformat(),
                span.ended_at.isoformat() if span.ended_at else None,
            ),
        )
        self._commit_if_needed()

    def update_span(self, span: Span) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """UPDATE spans
            SET end_event_id=?, status=?, ended_at=?
            WHERE id=?""",
            (
                span.end_event_id,
                span.status.value,
                span.ended_at.isoformat() if span.ended_at else None,
                span.id,
            ),
        )
        self._commit_if_needed()

    def list_spans(self, task_id: str) -> list[Span]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT * FROM spans WHERE task_id=? ORDER BY created_at ASC", (task_id,)).fetchall()
        return [row_to_span(r) for r in rows]

    def get_span(self, span_id: str) -> Span | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM spans WHERE id=?", (span_id,)).fetchone()
        return row_to_span(row) if row else None

    # Conversations
    def add_conversation(self, conversation: Conversation) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO conversations (id, project_id, title, mode, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                conversation.id,
                conversation.project_id,
                conversation.title,
                conversation.mode,
                conversation.created_at.isoformat(),
            ),
        )
        self._commit_if_needed()

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        return row_to_conversation(row) if row else None

    def list_conversations(self, limit: int | None = None) -> list[Conversation]:
        cur = self._conn.cursor()
        sql = "SELECT * FROM conversations ORDER BY created_at DESC, id DESC"
        params: list[int] = []

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        rows = cur.execute(sql, params).fetchall()
        return [row_to_conversation(r) for r in rows]

    def get_conversation_mode(self, conversation_id: str) -> str:
        cur = self._conn.cursor()
        row = cur.execute("SELECT mode FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if row is None:
            raise ValueError(f"Conversation not found: {conversation_id}")
        try:
            mode = row["mode"]
        except KeyError:
            mode = None
        return mode or "general"

    def set_conversation_mode(self, conversation_id: str, mode: str) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE conversations SET mode=? WHERE id=?", (mode, conversation_id))
        if cur.rowcount == 0:
            raise ValueError(f"Conversation not found: {conversation_id}")
        self._commit_if_needed()

    def add_turn(self, turn: Turn) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO turns (
                id,
                conversation_id,
                turn_index,
                user_text,
                assistant_text,
                provider,
                model,
                routing_reasons,
                memory_written_ids,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn.id,
                turn.conversation_id,
                turn.turn_index,
                turn.user_text,
                turn.assistant_text,
                turn.provider,
                turn.model,
                json.dumps(turn.routing_reasons, sort_keys=True),
                json.dumps(turn.memory_written_ids, sort_keys=True),
                turn.created_at.isoformat(),
            ),
        )
        self._commit_if_needed()

    def next_turn_index(self, conversation_id: str) -> int:
        cur = self._conn.cursor()
        row = cur.execute(
            "SELECT COALESCE(MAX(turn_index), 0) + 1 AS next_index FROM turns WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
        return int(row["next_index"])

    def list_turns(self, conversation_id: str, limit: int | None = None) -> list[Turn]:
        cur = self._conn.cursor()
        if limit is None:
            rows = cur.execute(
                "SELECT * FROM turns WHERE conversation_id=? ORDER BY turn_index ASC, id ASC",
                (conversation_id,),
            ).fetchall()
            return [row_to_turn(r) for r in rows]

        rows = cur.execute(
            """
            SELECT * FROM turns
            WHERE conversation_id=?
            ORDER BY turn_index DESC, id DESC
            LIMIT ?
            """,
            (conversation_id, limit),
        ).fetchall()
        turns = [row_to_turn(r) for r in rows]
        turns.reverse()
        return turns

    def get_turn_by_index(self, conversation_id: str, turn_index: int) -> Turn | None:
        cur = self._conn.cursor()
        row = cur.execute(
            """
            SELECT * FROM turns
            WHERE conversation_id=? AND turn_index=?
            ORDER BY id ASC
            LIMIT 1
            """,
            (conversation_id, turn_index),
        ).fetchone()
        return row_to_turn(row) if row else None

    def link_memory_to_turn(self, turn_id: str, memory_id: str) -> None:
        with self.transaction():
            cur = self._conn.cursor()
            row = cur.execute("SELECT memory_written_ids FROM turns WHERE id=?", (turn_id,)).fetchone()
            if row is None:
                raise ValueError(f"Turn not found: {turn_id}")
            raw_ids = row["memory_written_ids"] or "[]"
            try:
                memory_ids = json.loads(raw_ids)
            except json.JSONDecodeError:
                memory_ids = []
            if not isinstance(memory_ids, list):
                memory_ids = []
            if memory_id not in memory_ids:
                memory_ids.append(memory_id)
                cur.execute(
                    "UPDATE turns SET memory_written_ids=? WHERE id=?",
                    (json.dumps(memory_ids, sort_keys=True), turn_id),
                )

    def delete_conversation(self, conversation_id: str) -> int:
        """Delete a conversation and all related data (turns, memory items, events).

        Returns total rows deleted across all tables.
        """
        total = 0
        with self.transaction():
            cur = self._conn.cursor()
            # Conversation uses its ID as the task_id for events
            cur.execute("DELETE FROM events WHERE task_id = ?", (conversation_id,))
            total += cur.rowcount
            cur.execute("DELETE FROM memory_items WHERE conversation_id = ?", (conversation_id,))
            total += cur.rowcount
            cur.execute("DELETE FROM turns WHERE conversation_id = ?", (conversation_id,))
            total += cur.rowcount
            cur.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            total += cur.rowcount
        return total

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory item and clean up turn memory_written_ids references.

        Returns True if deleted, False if not found.
        """
        with self.transaction():
            cur = self._conn.cursor()
            # Check existence
            row = cur.execute("SELECT id FROM memory_items WHERE id = ?", (memory_id,)).fetchone()
            if row is None:
                return False

            # Clean up turn references — memory_written_ids is a JSON array
            # UUID format means LIKE won't produce false positives
            turns_with_ref = cur.execute(
                "SELECT id, memory_written_ids FROM turns WHERE memory_written_ids LIKE ?",
                (f"%{memory_id}%",),
            ).fetchall()

            for turn_row in turns_with_ref:
                try:
                    ids = json.loads(turn_row["memory_written_ids"] or "[]")
                except json.JSONDecodeError:
                    ids = []
                if memory_id in ids:
                    ids.remove(memory_id)
                    cur.execute(
                        "UPDATE turns SET memory_written_ids = ? WHERE id = ?",
                        (json.dumps(ids, sort_keys=True), turn_row["id"]),
                    )

            cur.execute("DELETE FROM memory_items WHERE id = ?", (memory_id,))
            return True

    # Memory
    def add_memory(self, item: MemoryItem) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO memory_items (id, content, tags, created_at, pinned, conversation_id, project_id, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.content,
                json.dumps(item.tags, sort_keys=True),
                item.created_at.isoformat(),
                1 if item.pinned else 0,
                item.conversation_id,
                item.project_id,
                item.source,
            ),
        )
        self._commit_if_needed()

    def get_memory(self, memory_id: str) -> MemoryItem | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM memory_items WHERE id=?", (memory_id,)).fetchone()
        return row_to_memory_item(row) if row else None

    def list_memory(self, limit: int | None = None, pinned_only: bool = False) -> list[MemoryItem]:
        cur = self._conn.cursor()
        sql = "SELECT * FROM memory_items"
        params: list[int] = []

        if pinned_only:
            sql += " WHERE pinned=1"

        sql += " ORDER BY pinned DESC, created_at DESC, id DESC"

        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        rows = cur.execute(sql, params).fetchall()
        return [row_to_memory_item(r) for r in rows]

    def set_pinned(self, memory_id: str, pinned: bool) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "UPDATE memory_items SET pinned=? WHERE id=?",
            (1 if pinned else 0, memory_id),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Memory not found: {memory_id}")
        self._commit_if_needed()

    def search_memory(
        self,
        query: str,
        *,
        top_k: int = 8,
        conversation_id: str | None = None,
        project_id: str | None = None,
        include_pinned: bool = True,
    ) -> list[MemoryItem]:
        q_tokens = self._normalize_tokens(query)

        cur = self._conn.cursor()
        params: list[Any] = []
        if conversation_id is not None:
            if include_pinned:
                sql = """
                    SELECT * FROM memory_items
                    WHERE conversation_id=? OR pinned=1
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                """
                params = [conversation_id, _MEMORY_SEARCH_LIMIT]
            else:
                sql = """
                    SELECT * FROM memory_items
                    WHERE conversation_id=?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                """
                params = [conversation_id, _MEMORY_SEARCH_LIMIT]
        elif project_id is not None:
            if include_pinned:
                sql = """
                    SELECT * FROM memory_items
                    WHERE project_id=? OR pinned=1
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                """
                params = [project_id, _MEMORY_SEARCH_LIMIT]
            else:
                sql = """
                    SELECT * FROM memory_items
                    WHERE project_id=?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                """
                params = [project_id, _MEMORY_SEARCH_LIMIT]
        else:
            if include_pinned:
                sql = """
                    SELECT * FROM memory_items
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                """
                params = [_MEMORY_SEARCH_LIMIT]
            else:
                sql = """
                    SELECT * FROM memory_items
                    WHERE pinned=0
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                """
                params = [_MEMORY_SEARCH_LIMIT]

        rows = cur.execute(sql, params).fetchall()
        items = [row_to_memory_item(r) for r in rows]

        pinned_items = [i for i in items if i.pinned] if include_pinned else []
        non_pinned_items = [i for i in items if not i.pinned]

        pinned_items.sort(key=lambda i: (i.created_at, i.id), reverse=True)

        def _score(item: MemoryItem) -> tuple[int, int, datetime, str]:
            tag_matches = self._tag_match_count(item.tags, q_tokens)
            keyword_matches = self._keyword_match_count(item.content, q_tokens)
            return (tag_matches, keyword_matches, item.created_at, item.id)

        non_pinned_items.sort(key=_score, reverse=True)

        results: list[MemoryItem] = []
        if include_pinned:
            results.extend(pinned_items)

        remaining = max(top_k - len(results), 0)
        results.extend(non_pinned_items[:remaining])
        return results

    # ---- helpers ----
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

    def _configure_connection(self) -> None:
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._conn.execute("PRAGMA busy_timeout = 5000;")

    def _commit_if_needed(self) -> None:
        if self._transaction_depth == 0:
            self._conn.commit()

    def _ensure_parent_task_column(self) -> None:
        cur = self._conn.cursor()
        columns = [row[1] for row in cur.execute("PRAGMA table_info(tasks)").fetchall()]
        if "parent_task_id" not in columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN parent_task_id TEXT")
            self._commit_if_needed()

    def _ensure_task_result_columns(self) -> None:
        """Migrate existing databases to add result_json and error_json columns."""
        cur = self._conn.cursor()
        columns = [row[1] for row in cur.execute("PRAGMA table_info(tasks)").fetchall()]
        if "result_json" not in columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN result_json TEXT")
        if "error_json" not in columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN error_json TEXT")
        self._commit_if_needed()

    def _ensure_turn_memory_written_column(self) -> None:
        cur = self._conn.cursor()
        columns = [row[1] for row in cur.execute("PRAGMA table_info(turns)").fetchall()]
        if "memory_written_ids" not in columns:
            cur.execute("ALTER TABLE turns ADD COLUMN memory_written_ids TEXT NOT NULL DEFAULT '[]'")
            self._commit_if_needed()

    def _ensure_conversation_mode_column(self) -> None:
        cur = self._conn.cursor()
        columns = [row[1] for row in cur.execute("PRAGMA table_info(conversations)").fetchall()]
        if "mode" not in columns:
            cur.execute("ALTER TABLE conversations ADD COLUMN mode TEXT NOT NULL DEFAULT 'general'")
            self._commit_if_needed()

    def _ensure_indexes(self) -> None:
        """Create indexes for query performance optimization."""
        cur = self._conn.cursor()
        for index_stmt in schema.INDEXES:
            cur.execute(index_stmt)
        self._commit_if_needed()

    def _append_event_with_hash(self, event: Event) -> None:
        existing = self.list_events(task_id=event.task_id) if event.task_id else []
        if existing:
            event.prev_hash = existing[-1].hash
        event.compute_hash()
        self.append_event(event)

    def recover_stale_tasks(self, emit_event: Callable[[Event], None] | None = None) -> list[str]:
        """Mark lingering running tasks as failed and close their spans."""

        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM tasks WHERE status=? ORDER BY created_at ASC, id ASC",
            (TaskStatus.RUNNING.value,),
        ).fetchall()

        recovered: list[str] = []
        for row in rows:
            task = row_to_task(row)
            failure_event = Event(
                project_id=task.project_id,
                task_id=task.id,
                agent_id=task.agent_id,
                type="task_failed",
                payload={
                    "reason": "crash_recovery",
                    "message": "Task marked failed after unexpected termination",
                },
            )

            with self.transaction():
                if emit_event:
                    emit_event(failure_event)
                else:
                    self._append_event_with_hash(failure_event)

                error_json = json.dumps(
                    {
                        "reason": "crash_recovery",
                        "message": "Task marked failed after unexpected termination",
                        "failed_event_id": failure_event.id,
                    }
                )
                updated_at = failure_event.created_at.isoformat()
                cur.execute(
                    "UPDATE tasks SET status=?, error_json=?, updated_at=? WHERE id=?",
                    (TaskStatus.FAILED.value, error_json, updated_at, task.id),
                )

                spans = self.list_spans(task.id)
                for span in spans:
                    if span.end_event_id is None or span.status == SpanStatus.STARTED:
                        span.status = SpanStatus.FAILED
                        span.end_event_id = failure_event.id
                        span.ended_at = failure_event.created_at
                        self.update_span(span)

                recovered.append(task.id)

        return recovered

    # LLM Usage
    def insert_llm_usage(self, usage: LLMUsage) -> None:
        """Record an LLM API call for usage tracking and budget enforcement."""
        cur = self._conn.cursor()
        # Handle both datetime and string created_at
        created_at_str = usage.created_at if isinstance(usage.created_at, str) else usage.created_at.isoformat()
        cur.execute(
            """
            INSERT INTO llm_usage (
                id, created_at, project_id, task_id, agent_id, provider, model,
                request_id, input_tokens, output_tokens, total_tokens, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usage.id,
                created_at_str,
                usage.project_id,
                usage.task_id,
                usage.agent_id,
                usage.provider,
                usage.model,
                usage.request_id,
                usage.input_tokens,
                usage.output_tokens,
                usage.total_tokens,
                usage.latency_ms,
            ),
        )
        self._commit_if_needed()

    def list_llm_usage_by_project(self, project_id: str, limit: int | None = None, offset: int = 0) -> list[LLMUsage]:
        """List LLM usage records for a project, ordered by created_at DESC then id."""
        cur = self._conn.cursor()
        sql = """
            SELECT * FROM llm_usage
            WHERE project_id = ?
            ORDER BY created_at DESC, id DESC
        """
        params: list[str | int] = [project_id]

        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        rows = cur.execute(sql, params).fetchall()
        return [row_to_llm_usage(r) for r in rows]

    def sum_tokens_by_task(self, task_id: str) -> dict[str, int]:
        """Sum token usage for a task. Returns dict with input/output/total counts."""
        cur = self._conn.cursor()
        row = cur.execute(
            """
            SELECT
                COALESCE(SUM(input_tokens), 0) as input,
                COALESCE(SUM(output_tokens), 0) as output,
                COALESCE(SUM(total_tokens), 0) as total
            FROM llm_usage
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

        return {
            "input_tokens": row["input"],
            "output_tokens": row["output"],
            "total_tokens": row["total"],
        }

    def sum_tokens_by_project(self, project_id: str, since: str | None = None) -> dict[str, int]:
        """Sum token usage for a project with optional time window."""
        cur = self._conn.cursor()

        sql = """
            SELECT
                COALESCE(SUM(input_tokens), 0) as input,
                COALESCE(SUM(output_tokens), 0) as output,
                COALESCE(SUM(total_tokens), 0) as total
            FROM llm_usage
            WHERE project_id = ?
        """
        params: list[str] = [project_id]

        if since:
            sql += " AND created_at >= ?"
            params.append(since)

        row = cur.execute(sql, params).fetchone()

        return {
            "input_tokens": row["input"],
            "output_tokens": row["output"],
            "total_tokens": row["total"],
        }

    # Task tree query helpers
    def list_child_tasks(self, parent_task_id: str) -> list[Task]:
        """List all child tasks for a given parent task, ordered deterministically."""
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM tasks WHERE parent_task_id=? ORDER BY created_at ASC, id ASC",
            (parent_task_id,),
        ).fetchall()
        return [row_to_task(r) for r in rows]

    def get_task_latest_routing(self, task_id: str) -> dict[str, Any] | None:
        """Get the latest routing decision for a task from llm.routed events."""
        cur = self._conn.cursor()
        row = cur.execute(
            """
            SELECT payload FROM events
            WHERE task_id=? AND type='llm.routed'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()

        if not row:
            return None

        payload = json.loads(row["payload"])
        return {
            "provider": payload.get("provider_selected") or payload.get("provider"),
            "model": payload.get("model_selected") or payload.get("model"),
            "mode": payload.get("mode"),
            "reasons": payload.get("reasons", []),
        }

    def get_task_usage_totals(self, task_id: str) -> dict[str, Any]:
        """Get aggregated LLM usage totals for a task."""
        cur = self._conn.cursor()
        row = cur.execute(
            """
            SELECT
                COUNT(*) as calls,
                COALESCE(SUM(input_tokens), 0) as input_tokens,
                COALESCE(SUM(output_tokens), 0) as output_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(AVG(latency_ms), 0) as avg_latency_ms
            FROM llm_usage
            WHERE task_id = ?
            """,
            (task_id,),
        ).fetchone()

        return {
            "calls": row["calls"],
            "input_tokens": row["input_tokens"],
            "output_tokens": row["output_tokens"],
            "total_tokens": row["total_tokens"],
            "avg_latency_ms": int(row["avg_latency_ms"]),
        }

    def get_task_worker_plan(self, task_id: str) -> dict[str, Any] | None:
        """Get the worker plan from supervisor.worker_plan event for a task."""
        cur = self._conn.cursor()
        row = cur.execute(
            """
            SELECT payload FROM events
            WHERE task_id=? AND type='supervisor.worker_plan'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (task_id,),
        ).fetchone()

        if not row:
            return None

        payload = json.loads(row["payload"])
        return {
            "worker_modes": payload.get("worker_modes", []),
            "rationale": payload.get("rationale"),
            "worker_count": payload.get("worker_count"),
        }
