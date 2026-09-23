"""Backfill embeddings and shape the caller-facing outcome.

The ok/partial/failed mapping existed verbatim in the MCP tool and the
REST route — the 2026-05 "status=ok with generated=0" bug lived in
exactly this shape, and a per-surface copy is how it recurs. One use
case keeps the surfaces identical by construction (the same reason
``stats_memory`` exists).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openchronicle.core.domain.exceptions import RevisionUnknownError

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
            if started
            else "Another backfill is already running, so this request did not start one. "
            "Retry once health.embedding_status.last_background_backfill shows it finished."
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
    try:
        result = service.generate_missing(force=force)
    except RevisionUnknownError as exc:
        # Refused before any candidate was selected (ADR 0005 §7). Reported
        # like a dead provider, as a failed run, not as a transport error.
        return {
            "status": "failed",
            "message": str(exc),
            "generated": 0,
            "failed": 0,
            "tombstoned": 0,
            "elapsed_ms": 0,
            "force": force,
            **service.embedding_status(),
        }
    status = service.embedding_status()
    if result.skipped:
        return {
            "status": "already_running",
            "message": "Another backfill is running — watch health.embedding_status.",
            "force": force,
            **status,
        }
    # Tombstoned rows (ADR 0009) are classified permanent outcomes, not
    # failures: a tombstoned-only run maps to "ok" (failed == 0) and the
    # additive `tombstoned` field carries the count.
    return {
        "status": result.outcome,
        "generated": result.generated,
        "failed": result.failed,
        "tombstoned": result.tombstoned,
        "elapsed_ms": result.elapsed_ms,
        "force": force,
        **status,
    }
