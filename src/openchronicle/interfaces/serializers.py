"""Shared serializers for domain models → JSON-safe dicts.

Used by both the HTTP API routes and MCP tool handlers to avoid
duplicating conversion logic across interface layers.
"""

from __future__ import annotations

from typing import Any

from openchronicle.core.domain.models.asset import Asset, AssetLink
from openchronicle.core.domain.models.conversation import Conversation, Turn
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
        "conversation_id": m.conversation_id,
        "project_id": m.project_id,
        "source": m.source,
        "created_at": m.created_at.isoformat(),
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def conversation_to_dict(c: Conversation) -> dict[str, Any]:
    return {
        "id": c.id,
        "project_id": c.project_id,
        "title": c.title,
        "mode": c.mode,
        "created_at": c.created_at.isoformat(),
    }


def turn_to_dict(t: Turn) -> dict[str, Any]:
    return {
        "id": t.id,
        "conversation_id": t.conversation_id,
        "turn_index": t.turn_index,
        "user_text": t.user_text,
        "assistant_text": t.assistant_text,
        "provider": t.provider,
        "model": t.model,
        "routing_reasons": t.routing_reasons,
        "created_at": t.created_at.isoformat(),
    }


def assembled_context_to_dict(ctx: Any) -> dict[str, Any]:
    """Serialize an AssembledContext to a JSON-safe dict."""
    return {
        "conversation_id": ctx.conversation_id,
        "conversation_title": ctx.conversation_title,
        "conversation_mode": ctx.conversation_mode,
        "messages": ctx.messages,
        "retrieved_memories": [
            {
                "id": m.id,
                "content": m.content,
                "tags": m.tags,
                "pinned": m.pinned,
                "source": m.source,
            }
            for m in ctx.retrieved_memories
        ],
        "prior_turn_count": ctx.prior_turn_count,
        "last_interaction_at": ctx.last_interaction_at,
        "seconds_since_last_interaction": ctx.seconds_since_last_interaction,
    }


def asset_to_dict(a: Asset) -> dict[str, Any]:
    return {
        "id": a.id,
        "project_id": a.project_id,
        "filename": a.filename,
        "mime_type": a.mime_type,
        "file_path": a.file_path,
        "size_bytes": a.size_bytes,
        "content_hash": a.content_hash,
        "metadata": a.metadata,
        "created_at": a.created_at.isoformat(),
    }


def asset_link_to_dict(link: AssetLink) -> dict[str, Any]:
    return {
        "id": link.id,
        "asset_id": link.asset_id,
        "target_type": link.target_type,
        "target_id": link.target_id,
        "role": link.role,
        "created_at": link.created_at.isoformat(),
    }
