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


def execute_background(service: EmbeddingService | None, *, force: bool = False) -> dict[str, Any]:
    """Start a backfill and return immediately (the `background=true` path).

    Exists because a real reindex (a model switch on the NAS corpus) runs
    ~20 minutes — past any MCP host tool timeout, so the synchronous path
    is unusable for exactly the operation the tool advertises. Progress
    is observed in health: `stale` and `missing` count down to zero.
    Must be called from a running event loop.
    """
    if service is None:
        return {
            "status": "not_configured",
            "message": "Set OC_EMBEDDING_PROVIDER to enable embeddings.",
        }
    started = service.start_background_backfill(force=force)
    return {
        "status": "started" if started else "already_running",
        "message": (
            "Backfill running in the background — watch health.embedding_status "
            "(`stale` and `missing` count down to 0)."
        ),
        "force": force,
        **service.embedding_status(),
    }


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
