from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from openchronicle.core.domain.models.project import Agent, Event, Project, Resource, Span, SpanStatus, Task, TaskStatus
from openchronicle.core.domain.ports.storage_port import StoragePort
from openchronicle.core.infrastructure.persistence import schema


class SqliteStore(StoragePort):
    def __init__(self, db_path: str = "data/openchronicle.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        cur = self._conn.cursor()
        for stmt in schema.ALL_TABLES:
            cur.execute(stmt)
        self._conn.commit()
        self._ensure_parent_task_column()

    # Projects
    def add_project(self, project: Project) -> None:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO projects (id, name, metadata, created_at) VALUES (?, ?, ?, ?)",
            (project.id, project.name, json.dumps(project.metadata), project.created_at.isoformat()),
        )
        self._conn.commit()

    def list_projects(self) -> list[Project]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [self._row_to_project(r) for r in rows]

    def get_project(self, project_id: str) -> Project | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        return self._row_to_project(row) if row else None

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
        self._conn.commit()

    def list_agents(self, project_id: str) -> list[Agent]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM agents WHERE project_id=? ORDER BY created_at ASC, id ASC", (project_id,)
        ).fetchall()
        return [self._row_to_agent(r) for r in rows]

    # Tasks
    def add_task(self, task: Task) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO tasks (id, project_id, agent_id, parent_task_id, type, payload, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.project_id,
                task.agent_id,
                task.parent_task_id,
                task.type,
                json.dumps(task.payload),
                task.status.value,
                task.created_at.isoformat(),
                task.updated_at.isoformat(),
            ),
        )
        self._conn.commit()

    def update_task_status(self, task_id: str, status: str) -> None:
        cur = self._conn.cursor()
        updated_at = datetime.now(UTC).isoformat()
        cur.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
            (status, updated_at, task_id),
        )
        self._conn.commit()

    def get_task(self, task_id: str) -> Task | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

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
        self._conn.commit()

    def list_events(self, task_id: str) -> list[Event]:
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT * FROM events WHERE task_id=? ORDER BY created_at ASC, id ASC",
            (task_id,),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

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
        self._conn.commit()

    def list_resources(self, project_id: str) -> list[Resource]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT * FROM resources WHERE project_id=?", (project_id,)).fetchall()
        return [self._row_to_resource(r) for r in rows]

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
        self._conn.commit()

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
        self._conn.commit()

    def list_spans(self, task_id: str) -> list[Span]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT * FROM spans WHERE task_id=? ORDER BY created_at ASC", (task_id,)).fetchall()
        return [self._row_to_span(r) for r in rows]

    def get_span(self, span_id: str) -> Span | None:
        cur = self._conn.cursor()
        row = cur.execute("SELECT * FROM spans WHERE id=?", (span_id,)).fetchone()
        return self._row_to_span(row) if row else None

    # ---- helpers ----
    def _row_to_project(self, row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=self._parse_dt(row["created_at"]),
        )

    def _row_to_agent(self, row: sqlite3.Row) -> Agent:
        return Agent(
            id=row["id"],
            project_id=row["project_id"],
            role=row["role"],
            name=row["name"],
            provider=row["provider"],
            model=row["model"],
            tags=json.loads(row["tags"] or "[]"),
            created_at=self._parse_dt(row["created_at"]),
        )

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            project_id=row["project_id"],
            agent_id=row["agent_id"],
            parent_task_id=row["parent_task_id"],
            type=row["type"],
            payload=json.loads(row["payload"] or "{}"),
            status=TaskStatus(row["status"]),
            created_at=self._parse_dt(row["created_at"]),
            updated_at=self._parse_dt(row["updated_at"]),
        )

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        return Event(
            id=row["id"],
            project_id=row["project_id"],
            task_id=row["task_id"],
            agent_id=row["agent_id"],
            type=row["type"],
            payload=json.loads(row["payload"] or "{}"),
            created_at=self._parse_dt(row["created_at"]),
            prev_hash=row["prev_hash"],
            hash=row["hash"],
        )

    def _row_to_resource(self, row: sqlite3.Row) -> Resource:
        return Resource(
            id=row["id"],
            project_id=row["project_id"],
            kind=row["kind"],
            path=row["path"],
            content_hash=row["content_hash"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=self._parse_dt(row["created_at"]),
        )

    def _row_to_span(self, row: sqlite3.Row) -> Span:
        return Span(
            id=row["id"],
            task_id=row["task_id"],
            agent_id=row["agent_id"],
            name=row["name"],
            start_event_id=row["start_event_id"],
            end_event_id=row["end_event_id"],
            status=SpanStatus(row["status"]),
            created_at=self._parse_dt(row["created_at"]),
            ended_at=self._parse_dt(row["ended_at"]) if row["ended_at"] else None,
        )

    def _parse_dt(self, value: str) -> datetime:
        return datetime.fromisoformat(value)

    def _ensure_parent_task_column(self) -> None:
        cur = self._conn.cursor()
        columns = [row[1] for row in cur.execute("PRAGMA table_info(tasks)").fetchall()]
        if "parent_task_id" not in columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN parent_task_id TEXT")
            self._conn.commit()
