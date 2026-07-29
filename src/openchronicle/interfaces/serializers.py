"""Shared serializers for domain models → JSON-safe dicts.

Both serializers take a `compact` flag. Compact exists because the full
shapes are expensive to browse: one dogfooding session spent 91,372
characters listing 30 memories to answer a question that only needed
their ids and project ids.

The preview length is a module constant rather than a parameter, and
deliberately so. A bool needs no clamping, so MCP and REST can both take
it verbatim; the moment it became an int, the two surfaces would each
need their own range check and those would drift.

Compact **replaces** the large field rather than shortening it in place —
`content` becomes `content_preview` + `content_length`, `metadata`
becomes `metadata_keys` + `metadata_size`. A consumer reading `content`
must never silently receive a truncated string; a renamed key makes the
truncation impossible to miss, and the length tells the caller whether a
follow-up `memory_get` is worth it.
"""

from __future__ import annotations

import json
from typing import Any

from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Project

_COMPACT_PREVIEW_CHARS = 120


def content_preview(text: str) -> str:
    """Shorten text for listings, appending an ellipsis only if it was cut."""
    if len(text) <= _COMPACT_PREVIEW_CHARS:
        return text
    return text[:_COMPACT_PREVIEW_CHARS] + "..."


def project_to_dict(p: Project, *, compact: bool = False) -> dict[str, Any]:
    if compact:
        return {
            "id": p.id,
            "name": p.name,
            "metadata_keys": sorted(p.metadata),
            "metadata_size": len(json.dumps(p.metadata)),
            "created_at": p.created_at.isoformat(),
        }
    return {
        "id": p.id,
        "name": p.name,
        "metadata": p.metadata,
        "created_at": p.created_at.isoformat(),
    }


def memory_to_dict(m: MemoryItem, *, compact: bool = False) -> dict[str, Any]:
    if compact:
        return {
            "id": m.id,
            "content_preview": content_preview(m.content),
            "content_length": len(m.content),
            "tags": m.tags,
            "pinned": m.pinned,
            "project_id": m.project_id,
            "source": m.source,
            "created_at": m.created_at.isoformat(),
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
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
