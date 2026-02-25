"""Tests for MoE execution strategy: consensus scoring, execute_moe, edge cases."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from openchronicle.core.application.routing.pool_config import ProviderCandidate
from openchronicle.core.application.services.moe_execution import (
    _jaccard_similarity,
    _tokenize,
    compute_consensus_scores,
    execute_moe,
)
from openchronicle.core.domain.errors.error_codes import MOE_INSUFFICIENT_EXPERTS
from openchronicle.core.domain.models.moe_result import MoEExpertResult
from openchronicle.core.domain.ports.llm_port import LLMProviderError, LLMResponse, LLMUsage

# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_basic(self) -> None:
        assert _tokenize("Hello World") == {"hello", "world"}

    def test_punctuation(self) -> None:
        assert _tokenize("Hello, World!") == {"hello", "world"}

    def test_case_folding(self) -> None:
        assert _tokenize("FOO Bar baz") == {"foo", "bar", "baz"}

    def test_empty_string(self) -> None:
        assert _tokenize("") == set()

    def test_whitespace_only(self) -> None:
        assert _tokenize("   \t\n  ") == set()

    def test_numbers(self) -> None:
        assert _tokenize("test 123 abc") == {"test", "123", "abc"}


# ---------------------------------------------------------------------------
# Jaccard Similarity
# ---------------------------------------------------------------------------


class TestJaccardSimilarity:
    def test_identical(self) -> None:
        s = {"a", "b", "c"}
        assert _jaccard_similarity(s, s) == 1.0

    def test_disjoint(self) -> None:
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self) -> None:
        # intersection = {b}, union = {a, b, c} => 1/3
        result = _jaccard_similarity({"a", "b"}, {"b", "c"})
        assert abs(result - 1 / 3) < 1e-9

    def test_both_empty(self) -> None:
        assert _jaccard_similarity(set(), set()) == 1.0

    def test_one_empty(self) -> None:
        assert _jaccard_similarity({"a"}, set()) == 0.0
        assert _jaccard_similarity(set(), {"a"}) == 0.0


# ---------------------------------------------------------------------------
# Consensus Scoring
# ---------------------------------------------------------------------------


class TestComputeConsensusScores:
    def test_three_experts_known_texts(self) -> None:
        """Two experts agree, third diverges. Agreeing experts should score higher."""
        e1 = MoEExpertResult(provider="a", model="m1", content="the cat sat on the mat")
        e2 = MoEExpertResult(provider="b", model="m2", content="the cat sat on the mat today")
        e3 = MoEExpertResult(provider="c", model="m3", content="completely different output here")

        scored = compute_consensus_scores([e1, e2, e3])

        # e1 and e2 should have higher scores than e3
        assert scored[0].consensus_score > scored[-1].consensus_score
        # e1 and e2 are the top two (either order)
        top_providers = {scored[0].provider, scored[1].provider}
        assert top_providers == {"a", "b"}

    def test_single_expert(self) -> None:
        e = MoEExpertResult(provider="a", model="m1", content="hello")
        scored = compute_consensus_scores([e])
        assert scored[0].consensus_score == 1.0

    def test_empty_list(self) -> None:
        scored = compute_consensus_scores([])
        assert scored == []

    def test_weight_tiebreak(self) -> None:
        """When consensus scores are equal, higher weight wins."""
        e1 = MoEExpertResult(provider="a", model="m1", content="identical text", weight=50)
        e2 = MoEExpertResult(provider="b", model="m2", content="identical text", weight=100)

        scored = compute_consensus_scores([e1, e2])

        # Both have identical content so equal consensus scores
        assert scored[0].consensus_score == scored[1].consensus_score
        # Higher weight should be first
        assert scored[0].provider == "b"

    def test_sort_stability(self) -> None:
        """With equal scores and weights, original order is preserved (stable sort)."""
        experts = [
            MoEExpertResult(provider="z", model="m1", content="same text", weight=100),
            MoEExpertResult(provider="a", model="m2", content="same text", weight=100),
        ]
        scored = compute_consensus_scores(experts)
        # Equal score, equal weight — stable sort preserves original order
        assert scored[0].provider == "z"


# ---------------------------------------------------------------------------
# execute_moe
# ---------------------------------------------------------------------------


def _make_mock_llm(responses: dict[str, str]) -> AsyncMock:
    """Create a mock LLMPort. responses maps 'provider:model' to content."""
    mock = AsyncMock()

    async def complete_async(
        messages: list[dict[str, Any]],
        model: str,
        provider: str,
        **kwargs: Any,
    ) -> LLMResponse:
        key = f"{provider}:{model}"
        if key not in responses:
            raise LLMProviderError(f"Provider {key} unavailable", error_code="PROVIDER_ERROR")
        return LLMResponse(
            content=responses[key],
            provider=provider,
            model=model,
            usage=LLMUsage(input_tokens=10, output_tokens=20, total_tokens=30),
            latency_ms=100,
        )

    mock.complete_async = AsyncMock(side_effect=complete_async)
    return mock


class TestExecuteMoe:
    @pytest.mark.asyncio
    async def test_three_experts_success(self) -> None:
        llm = _make_mock_llm(
            {
                "openai:gpt-4o": "The answer is 42, according to the guide.",
                "anthropic:claude": "The answer is 42 from the hitchhiker guide.",
                "google:gemini": "The answer is 42 as stated in the guide.",
            }
        )
        candidates = [
            ProviderCandidate(provider="openai", model="gpt-4o"),
            ProviderCandidate(provider="anthropic", model="claude"),
            ProviderCandidate(provider="google", model="gemini"),
        ]
        result = await execute_moe(
            llm=llm,
            candidates=candidates,
            messages=[{"role": "user", "content": "What is the answer?"}],
        )
        assert result.winner is not None
        assert result.winner.error is None
        assert len(result.experts) == 3
        assert result.agreement_ratio > 0.0
        assert all(e.error is None for e in result.experts)

    @pytest.mark.asyncio
    async def test_parallel_calls(self) -> None:
        """Verify all experts are called (parallel execution)."""
        llm = _make_mock_llm(
            {
                "a:m1": "response one",
                "b:m2": "response two",
                "c:m3": "response three",
            }
        )
        candidates = [
            ProviderCandidate(provider="a", model="m1"),
            ProviderCandidate(provider="b", model="m2"),
            ProviderCandidate(provider="c", model="m3"),
        ]
        await execute_moe(
            llm=llm,
            candidates=candidates,
            messages=[{"role": "user", "content": "test"}],
        )
        assert llm.complete_async.call_count == 3

    @pytest.mark.asyncio
    async def test_moe_result_structure(self) -> None:
        llm = _make_mock_llm(
            {
                "a:m1": "hello world",
                "b:m2": "hello world friend",
            }
        )
        candidates = [
            ProviderCandidate(provider="a", model="m1"),
            ProviderCandidate(provider="b", model="m2"),
        ]
        result = await execute_moe(
            llm=llm,
            candidates=candidates,
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result.winner.content in ("hello world", "hello world friend")
        assert result.winner.usage is not None
        assert result.winner.latency_ms is not None
        assert 0.0 <= result.agreement_ratio <= 1.0

    @pytest.mark.asyncio
    async def test_partial_failure(self) -> None:
        """1 of 3 experts fails, still succeeds with min_experts=2."""
        llm = _make_mock_llm(
            {
                "a:m1": "good response here",
                "b:m2": "good response here too",
                # c:m3 not in map -> will fail
            }
        )
        candidates = [
            ProviderCandidate(provider="a", model="m1"),
            ProviderCandidate(provider="b", model="m2"),
            ProviderCandidate(provider="c", model="m3"),
        ]
        result = await execute_moe(
            llm=llm,
            candidates=candidates,
            messages=[{"role": "user", "content": "test"}],
            min_experts=2,
        )
        assert result.winner.error is None
        failed = [e for e in result.experts if e.error is not None]
        assert len(failed) == 1
        assert failed[0].provider == "c"

    @pytest.mark.asyncio
    async def test_all_fail(self) -> None:
        """All experts fail -> raises MOE_INSUFFICIENT_EXPERTS."""
        llm = _make_mock_llm({})  # no responses -> all fail
        candidates = [
            ProviderCandidate(provider="a", model="m1"),
            ProviderCandidate(provider="b", model="m2"),
        ]
        with pytest.raises(LLMProviderError) as exc_info:
            await execute_moe(
                llm=llm,
                candidates=candidates,
                messages=[{"role": "user", "content": "test"}],
            )
        assert exc_info.value.error_code == MOE_INSUFFICIENT_EXPERTS

    @pytest.mark.asyncio
    async def test_below_min_experts(self) -> None:
        """2 of 3 fail with min_experts=2 -> raises."""
        llm = _make_mock_llm(
            {
                "a:m1": "only one succeeds",
                # b and c fail
            }
        )
        candidates = [
            ProviderCandidate(provider="a", model="m1"),
            ProviderCandidate(provider="b", model="m2"),
            ProviderCandidate(provider="c", model="m3"),
        ]
        with pytest.raises(LLMProviderError) as exc_info:
            await execute_moe(
                llm=llm,
                candidates=candidates,
                messages=[{"role": "user", "content": "test"}],
                min_experts=2,
            )
        assert exc_info.value.error_code == MOE_INSUFFICIENT_EXPERTS

    @pytest.mark.asyncio
    async def test_too_few_candidates(self) -> None:
        """Fewer candidates than min_experts -> raises immediately."""
        llm = _make_mock_llm({"a:m1": "hello"})
        candidates = [ProviderCandidate(provider="a", model="m1")]
        with pytest.raises(LLMProviderError) as exc_info:
            await execute_moe(
                llm=llm,
                candidates=candidates,
                messages=[{"role": "user", "content": "test"}],
                min_experts=2,
            )
        assert exc_info.value.error_code == MOE_INSUFFICIENT_EXPERTS
