from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort

if TYPE_CHECKING:
    from openchronicle.core.application.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


def execute(
    store: MemoryStorePort,
    item: MemoryItem,
    *,
    embedding_service: EmbeddingService | None = None,
) -> MemoryItem:
    if item.project_id is None:
        raise DomainValidationError("project_id is required")
    store.add_memory(item)
    if embedding_service is not None:
        try:
            embedding_service.generate_for_memory(item.id, item.content)
        except Exception:
            logger.warning("Failed to generate embedding for memory %s", item.id, exc_info=True)
    return item
