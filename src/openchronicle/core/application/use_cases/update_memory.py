"""Update an existing memory item's content and/or tags."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MAX_CONTENT_CHARS, MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

if TYPE_CHECKING:
    from openchronicle.core.application.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def execute(
    store: MemoryStorePort,
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    *,
    embedding_service: EmbeddingService | None = None,
) -> MemoryItem:
    if content is None and tags is None:
        raise DomainValidationError("At least one of content or tags must be provided")
    if content is not None and len(content) > MAX_CONTENT_CHARS:
        raise DomainValidationError(
            f"content exceeds maximum length of {MAX_CONTENT_CHARS:,} characters (got {len(content):,})"
        )

    updated = store.update_memory(memory_id, content=content, tags=tags)

    if content is not None:
        # Invalidate BEFORE attempting regeneration, and regardless of
        # whether a provider is configured. The old vector represents
        # content that no longer exists, and the model-string freshness
        # check cannot tell (same model, older content) — so if the
        # regeneration below failed, semantic search kept ranking the old
        # content and backfill skipped the row forever. Missing is
        # honest: hybrid search degrades to FTS5 for this row and the
        # next backfill sees a real candidate.
        store.delete_embedding(memory_id)

    if content is not None and embedding_service is not None:
        try:
            embedding_service.generate_for_memory(memory_id, updated.content, force=True)
        except Exception:
            logger.warning("Failed to regenerate embedding for memory %s", memory_id, exc_info=True)
    return updated
