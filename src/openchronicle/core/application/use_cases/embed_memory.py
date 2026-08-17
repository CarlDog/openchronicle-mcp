"""Backfill embeddings and shape the caller-facing outcome.

The ok/partial/failed mapping existed verbatim in the MCP tool and the
REST route — the 2026-05 "status=ok with generated=0" bug lived in
exactly this shape, and a per-surface copy is how it recurs. One use
case keeps the surfaces identical by construction (the same reason
``stats_memory`` exists).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openchronicle.core.application.services.embedding_service import EmbeddingService


def execute(service: EmbeddingService | None, *, force: bool = False) -> dict[str, Any]:
    """Run a backfill and return the caller-facing outcome payload."""
    if service is None:
        return {
            "status": "not_configured",
            "message": "Set OC_EMBEDDING_PROVIDER to enable embeddings.",
        }
    result = service.generate_missing(force=force)
    status = service.embedding_status()
    if result.failed == 0:
        outcome = "ok"
    elif result.generated == 0:
        outcome = "failed"
    else:
        outcome = "partial"
    return {
        "status": outcome,
        "generated": result.generated,
        "failed": result.failed,
        "elapsed_ms": result.elapsed_ms,
        "force": force,
        **status,
    }
