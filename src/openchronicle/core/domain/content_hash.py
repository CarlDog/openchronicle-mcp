"""Content identity for stored memory text (ADR 0005).

One function, in the domain layer, because every party to the
embedding-freshness contract must hash identically: the service hashing
what it embeds, the store's compare-and-swap hashing the current row,
and the staleness counters hashing for comparison. ADR 0005 (rev 2)
deliberately hashes the STORED memory content — never a transformed
provider input — so the identity is of the thing being represented;
any future input transform belongs to the embedding-space fingerprint
instead (Phase C), and until that field exists, client-side transforms
are forbidden outright.
"""

from __future__ import annotations

import hashlib


def hash_content(content: str) -> str:
    """SHA-256 hex digest of a memory's content string (UTF-8)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
