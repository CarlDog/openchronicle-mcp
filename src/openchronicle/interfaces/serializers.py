"""Shared serializers for domain models → JSON-safe dicts."""

from __future__ import annotations

from typing import Any

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project


def project_to_dict(p: Project) -> dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "metadata": p.metadata,
        "created_at": p.created_at.isoformat(),
    }


def memory_to_dict(m: MemoryItem) -> dict[str, Any]:
    return {
        "id": m.id,
        "content": m.content,
        "tags": m.tags,
        "pinned": m.pinned,
        "project_id": m.project_id,
        "source": m.source,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }
