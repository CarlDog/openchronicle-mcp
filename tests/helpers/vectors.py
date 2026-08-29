"""Test helper: store a vector for an existing memory under CAS.

``save_embedding`` is compare-and-swap since ADR 0005 — it requires the
provider identity and the hash of the memory's CURRENT content. Tests
that just want "this memory has this vector" go through here so the
identity plumbing lives in one place instead of twenty call sites.
"""

from __future__ import annotations

from openchronicle.core.domain.content_hash import hash_content
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore


def save_vec(
    store: SqliteStore,
    memory_id: str,
    vec: list[float],
    *,
    model: str = "test-model",
    provider: str = "test-provider",
    fingerprint: str = "test-fp",
    model_revision: str | None = None,
) -> bool:
    """CAS-save ``vec`` for ``memory_id``, hashing its stored content."""
    item = store.get_memory(memory_id)
    assert item is not None, f"save_vec: memory {memory_id!r} must exist before saving a vector"
    return store.save_embedding(
        memory_id,
        vec,
        model=model,
        provider=provider,
        content_hash=hash_content(item.content),
        settings_fingerprint=fingerprint,
        model_revision=model_revision,
    )
