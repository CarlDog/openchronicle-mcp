"""Port for generating text embeddings."""

from __future__ import annotations

from abc import ABC, abstractmethod


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
        """Provider revision behind the model label, when one exists.

        Ollama supplies a manifest digest (a mutable tag can be
        re-pulled with different weights under the same name); OpenAI
        and stub have none and return None. Persisted with every
        vector; predicates over the stored column MUST use ``IS``
        matching — ``= NULL`` matches nothing (ADR 0005 rev 2).
        """

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
