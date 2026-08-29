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
