"""Deterministic stub embedding adapter for testing."""

from __future__ import annotations

import hashlib
import math
import struct

from openchronicle.core.domain.ports.embedding_port import EmbeddingPort


class StubEmbeddingAdapter(EmbeddingPort):
    """Hash-based deterministic embeddings — no external calls.

    Given the same text, always produces the same normalized vector.
    Useful for unit tests and as the default when no provider is configured.
    """

    def __init__(self, dims: int = 384) -> None:
        self._dims = dims

    def embed(self, text: str) -> list[float]:
        # Use SHA-256 to seed a deterministic sequence of floats
        digest = hashlib.sha256(text.encode()).digest()
        # Expand hash to fill all dimensions (re-hash with counter)
        raw: list[float] = []
        counter = 0
        while len(raw) < self._dims:
            block = hashlib.sha256(digest + struct.pack(">I", counter)).digest()
            # Each 4 bytes -> one float in [-1, 1]
            for i in range(0, len(block), 4):
                if len(raw) >= self._dims:
                    break
                val = struct.unpack(">I", block[i : i + 4])[0]
                raw.append((val / 0xFFFFFFFF) * 2 - 1)
            counter += 1
        return _normalize(raw)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    def dimensions(self) -> int:
        return self._dims

    def model_name(self) -> str:
        return "stub"


def _normalize(vec: list[float]) -> list[float]:
    mag = math.sqrt(sum(x * x for x in vec))
    if mag == 0:
        return vec
    return [x / mag for x in vec]
