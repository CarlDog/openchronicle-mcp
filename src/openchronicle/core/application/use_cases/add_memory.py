from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from openchronicle.core.domain.exceptions import RevisionUnknownError
from openchronicle.core.domain.exceptions import ValidationError as DomainValidationError
from openchronicle.core.domain.models.memory_item import MAX_CONTENT_CHARS, MemoryItem
from openchronicle.core.domain.ports.memory_store_port import MemoryStorePort
from openchronicle.core.domain.time_utils import require_utc

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
    # Blank content was refused only by the MCP driver: REST's min_length=1
    # accepted whitespace, and the CLI accepted "" (MemoryItem's default).
    if not item.content.strip():
        raise DomainValidationError("content must be non-empty")
    # Enforced here, not per-driver: the CLI and any future caller reach
    # the store through this use case, and the two drivers that hand-rolled
    # their own check left `oc memory add` unbounded.
    if len(item.content) > MAX_CONTENT_CHARS:
        raise DomainValidationError(
            f"content exceeds maximum length of {MAX_CONTENT_CHARS:,} characters (got {len(item.content):,})"
        )
    item.created_at = require_utc(item.created_at, field="created_at")
    if item.updated_at is not None:
        item.updated_at = require_utc(item.updated_at, field="updated_at")
    store.add_memory(item)
    if embedding_service is not None:
        try:
            embedding_service.generate_for_memory(item.id, item.content)
        except RevisionUnknownError:
            # Refused, not failed (ADR 0005 §7): the memory is saved, and
            # reconciliation embeds it once the revision is verified. The
            # adapter already warns about the unverified revision.
            logger.debug("Embedding for memory %s deferred: model revision not verified", item.id)
        except Exception:
            logger.warning("Failed to generate embedding for memory %s", item.id, exc_info=True)
    return item
