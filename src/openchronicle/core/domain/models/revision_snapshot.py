"""What an embedding model's revision is known to be (ADR 0005 §7).

Until v3.4.0 the Ollama adapter cached a failed revision probe as ``None``.
Under ADR 0005 ``None`` means "this provider has no revision", so one
transient failure blanked semantic search and re-embedded the whole corpus
twice (design 0014 §1.1). ``known`` separates the two meanings.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RevisionSnapshot:
    """The model revision as last verified, as one immutable value.

    ``known=False`` means nothing has verified a revision yet, which is not
    the same as "no revision". ``known=True`` with ``value=None`` is a
    provider that genuinely has none: OpenAI, stub, or an Ollama model
    listed without a digest.

    Callers take one snapshot per operation, before the provider call, and
    use it for the currency check, the stamp and the search filter. An
    adapter swaps in a new snapshot with a single assignment, so a reader
    never sees a state paired with the wrong value.
    """

    known: bool
    value: str | None = None
    verified_at: datetime | None = None

    @property
    def state(self) -> str:
        """Health's ``model_revision_state``: ``known``, ``none`` or ``unknown``."""
        if not self.known:
            return "unknown"
        return "known" if self.value is not None else "none"


UNKNOWN_REVISION = RevisionSnapshot(known=False)
