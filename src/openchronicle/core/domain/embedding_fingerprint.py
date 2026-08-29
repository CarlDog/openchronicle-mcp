"""Canonical fingerprint of embedding-affecting settings (ADR 0005, Phase C).

ONE implementation, in the domain layer, deliberately not "computed by
the adapter": three independent canonicalizations would drift (bool
formatting, None handling, separators) and different fingerprints for
identical settings mean false staleness and spurious full reindexes —
the exact failure the adversarial review of ADR 0005 rev 1 named.
Adapters supply a plain options dict; this function owns the format.

Canonical form: JSON with sorted keys, compact separators, JSON
booleans/nulls, UTF-8 — then SHA-256. Changing this format (or an
adapter's option set) changes every fingerprint and therefore stales
every stored vector, forcing a full reindex. That consequence is
accepted and must accompany any such change in its migration note.
"""

from __future__ import annotations

import hashlib
import json


def settings_fingerprint(options: dict[str, object]) -> str:
    """SHA-256 hex digest of the canonical serialization of ``options``."""
    canonical = json.dumps(options, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
