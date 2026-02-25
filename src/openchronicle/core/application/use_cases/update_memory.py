"""Update an existing memory item's content and/or tags."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.models.project import Event
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

if TYPE_CHECKING:
    from openchronicle.core.application.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def execute(
    store: MemoryStorePort,
    emit_event: Callable[[Event], None],
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    *,
    embedding_service: EmbeddingService | None = None,
) -> MemoryItem:
    if content is None and tags is None:
        raise DomainValidationError("At least one of content or tags must be provided")

    updated = store.update_memory(memory_id, content=content, tags=tags)

    updated_fields = [f for f in ("content", "tags") if locals()[f] is not None]
    emit_event(
        Event(
            type="memory.updated",
            project_id=updated.project_id or "",
            payload={"memory_id": memory_id, "updated_fields": updated_fields},
        )
    )
    if content is not None and embedding_service is not None:
        try:
            embedding_service.generate_for_memory(memory_id, updated.content, force=True)
        except Exception:
            logger.warning("Failed to regenerate embedding for memory %s", memory_id, exc_info=True)
    return updated
