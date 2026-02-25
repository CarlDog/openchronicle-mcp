"""Contract tests for EmbeddingPort — exercised against StubEmbeddingAdapter."""

from __future__ import annotations

import math

from openchronicle.core.infrastructure.embedding.stub_adapter import StubEmbeddingAdapter


def _magnitude(vec: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vec))


def test_stub_returns_correct_dimensions() -> None:
    adapter = StubEmbeddingAdapter(dims=128)
    vec = adapter.embed("hello")
    assert len(vec) == 128


def test_stub_default_dimensions() -> None:
    adapter = StubEmbeddingAdapter()
    vec = adapter.embed("hello")
    assert len(vec) == 384
    assert adapter.dimensions() == 384


def test_stub_is_deterministic() -> None:
    adapter = StubEmbeddingAdapter()
    v1 = adapter.embed("the quick brown fox")
    v2 = adapter.embed("the quick brown fox")
    assert v1 == v2


def test_stub_vectors_are_normalized() -> None:
    adapter = StubEmbeddingAdapter()
    vec = adapter.embed("test normalization")
    mag = _magnitude(vec)
    assert abs(mag - 1.0) < 1e-6


def test_stub_embed_batch_returns_correct_count() -> None:
    adapter = StubEmbeddingAdapter()
    texts = ["alpha", "beta", "gamma"]
    results = adapter.embed_batch(texts)
    assert len(results) == 3
    for vec in results:
        assert len(vec) == 384


def test_stub_different_text_different_vectors() -> None:
    adapter = StubEmbeddingAdapter()
    v1 = adapter.embed("hello world")
    v2 = adapter.embed("goodbye world")
    assert v1 != v2


def test_stub_empty_text() -> None:
    adapter = StubEmbeddingAdapter()
    vec = adapter.embed("")
    assert len(vec) == 384
    mag = _magnitude(vec)
    assert abs(mag - 1.0) < 1e-6


def test_stub_model_name() -> None:
    adapter = StubEmbeddingAdapter()
    assert adapter.model_name() == "stub"
