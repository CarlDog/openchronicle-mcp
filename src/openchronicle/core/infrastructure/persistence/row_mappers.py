"""Pure data mappers: sqlite3.Row → domain model."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def row_to_project(row: sqlite3.Row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        metadata=json.loads(row["metadata"] or "{}"),
        created_at=_parse_dt(row["created_at"]),
    )


def row_to_memory_item(row: sqlite3.Row) -> MemoryItem:
    tags_raw = row["tags"] or "[]"
    updated_at_raw = row["updated_at"]
    return MemoryItem(
        id=row["id"],
        content=row["content"],
        tags=json.loads(tags_raw) if tags_raw else [],
        created_at=_parse_dt(row["created_at"]),
        pinned=bool(row["pinned"]),
        project_id=row["project_id"],
        source=row["source"],
        updated_at=_parse_dt(updated_at_raw) if updated_at_raw else None,
    )
