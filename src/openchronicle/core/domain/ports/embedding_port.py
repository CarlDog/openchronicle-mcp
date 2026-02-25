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
