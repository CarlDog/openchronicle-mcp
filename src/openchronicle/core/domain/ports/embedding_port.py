"""Port for generating text embeddings."""

from __future__ import annotations

from abc import ABC, abstractmethod

from openchronicle.core.domain.models.revision_snapshot import RevisionSnapshot


class EmbeddingPort(ABC):
    """Abstract interface for text embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for a single text."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts."""

    @abstractmethod
    def dimensions(self) -> int:
        """Return the dimensionality of embedding vectors."""

    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the embedding model."""

    @abstractmethod
    def provider_name(self) -> str:
        """Return the adapter kind ("openai", "ollama", "stub").

        Half of the embedding-space identity (ADR 0005): two providers
        can share a model label while producing incompatible vector
        spaces, so the model string alone under-determines the space a
        stored vector lives in.
        """

    @abstractmethod
    def model_revision(self) -> str | None:
        """The last verified revision behind the model label, if any.

        Ollama supplies a manifest digest (a mutable tag can be
        re-pulled with different weights under the same name); OpenAI
        and stub have none and return None. Persisted with every
        vector; predicates over the stored column MUST use ``IS``
        matching — ``= NULL`` matches nothing (ADR 0005 rev 2).

        A provider that tracks a revision raises ``RevisionUnknownError``
        here until one is verified, because ``None`` would claim "no
        revision" (ADR 0005 §7). Services read ``revision_snapshot()``,
        which carries both facts in one value.
        """

    @property
    def tracks_revision(self) -> bool:
        """True when the revision can change under the same model name.

        Only then is there anything to verify or re-probe. OpenAI and stub
        have no revision, so their snapshot is fixed.
        """
        return False

    def revision_snapshot(self) -> RevisionSnapshot:
        """The revision as last verified. In memory: never does I/O, never raises.

        The default suits providers that don't track a revision: their
        ``model_revision()`` is a constant.
        """
        return RevisionSnapshot(known=True, value=self.model_revision())

    def refresh_revision(self, *, force: bool = False) -> RevisionSnapshot:
        """Re-verify the revision and return the resulting snapshot.

        The only method here that may do I/O, so callers run it on a
        worker thread, never on the event loop. Without ``force`` a
        provider may skip the probe (the revision is already known, or a
        probe just failed). It never raises; a failed probe shows as an
        unchanged or unknown snapshot.
        """
        return self.revision_snapshot()

    @abstractmethod
    def settings_fingerprint(self) -> str:
        """Canonical hash of every embedding-affecting setting.

        Computed via the ONE shared helper
        (``domain.embedding_fingerprint.settings_fingerprint``) over a
        plain options dict — never a per-adapter serialization, which
        would drift. Any option that changes vector semantics
        (requested dimensions, truncation policy) must be in the dict;
        adding one stales every stored vector by design.
        """
