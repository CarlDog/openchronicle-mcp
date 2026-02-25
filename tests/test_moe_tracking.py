"""Tests for MoE usage tracking — storage, recording helper, moe_stats tool."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

mcp_mod = pytest.importorskip("mcp")  # noqa: F841

from openchronicle.core.application.use_cases.ask_conversation import _record_moe_usage  # noqa: E402
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore  # noqa: E402

# ── Helpers ───────────────────────────────────────────────────────


def _make_expert(
    provider: str = "openai",
    model: str = "gpt-4",
    *,
    latency_ms: int = 100,
    input_tokens: int = 10,
    output_tokens: int = 20,
    total_tokens: int = 30,
    consensus_score: float = 0.8,
    error: str | None = None,
) -> MagicMock:
    expert = MagicMock()
    expert.provider = provider
    expert.model = model
    expert.latency_ms = latency_ms
    expert.consensus_score = consensus_score
    expert.error = error
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.total_tokens = total_tokens
    expert.usage = None if error else usage
    return expert


def _make_moe_result(
    experts: list[Any] | None = None,
    agreement_ratio: float = 0.75,
) -> MagicMock:
    result = MagicMock()
    if experts is None:
        experts = [
            _make_expert("openai", "gpt-4", consensus_score=0.9),
            _make_expert("anthropic", "claude", consensus_score=0.7),
            _make_expert("ollama", "llama", consensus_score=0.6),
        ]
    result.experts = experts
    result.winner = experts[0]
    result.agreement_ratio = agreement_ratio
    return result


def _store(tmp_path: Any) -> SqliteStore:
    store = SqliteStore(str(tmp_path / "test.db"))
    store.init_schema()
    return store


def _insert_sample(store: SqliteStore, **overrides: Any) -> None:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4().hex,
        "conversation_id": "convo-1",
        "expert_count": 3,
        "successful_count": 3,
        "agreement_ratio": 0.75,
        "winner_provider": "openai",
        "winner_model": "gpt-4",
        "winner_consensus_score": 0.9,
        "total_latency_ms": 200,
        "total_input_tokens": 30,
        "total_output_tokens": 60,
        "total_tokens": 90,
        "failure_count": 0,
        "created_at": datetime.now(UTC).isoformat(),
    }
    defaults.update(overrides)
    store.insert_moe_usage(**defaults)


# ── Storage: SQLite roundtrip ────────────────────────────────────


class TestStorageMoEUsage:
    def test_insert_and_query(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _insert_sample(store)
        stats = store.get_moe_stats()
        assert len(stats) == 1
        assert stats[0]["winner_provider"] == "openai"
        assert stats[0]["winner_model"] == "gpt-4"
        assert stats[0]["run_count"] == 1
        assert stats[0]["avg_agreement_ratio"] == 0.75

    def test_groups_by_winner(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _insert_sample(store, winner_provider="openai", winner_model="gpt-4")
        _insert_sample(store, winner_provider="openai", winner_model="gpt-4")
        _insert_sample(store, winner_provider="anthropic", winner_model="claude")
        stats = store.get_moe_stats()
        assert len(stats) == 2
        by_provider = {s["winner_provider"]: s for s in stats}
        assert by_provider["openai"]["run_count"] == 2
        assert by_provider["anthropic"]["run_count"] == 1

    def test_filter_by_winner_provider(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _insert_sample(store, winner_provider="openai", winner_model="gpt-4")
        _insert_sample(store, winner_provider="anthropic", winner_model="claude")
        stats = store.get_moe_stats(winner_provider="anthropic")
        assert len(stats) == 1
        assert stats[0]["winner_provider"] == "anthropic"

    def test_filter_by_since(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _insert_sample(store, created_at="2020-01-01T00:00:00+00:00", winner_provider="old")
        _insert_sample(store, created_at="2026-01-01T00:00:00+00:00", winner_provider="new")
        stats = store.get_moe_stats(since="2025-01-01T00:00:00+00:00")
        assert len(stats) == 1
        assert stats[0]["winner_provider"] == "new"

    def test_empty_table(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        assert store.get_moe_stats() == []

    def test_total_tokens_reflects_all_experts(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        # 3 experts × 30 tokens each = 90 total
        _insert_sample(store, total_tokens=90, expert_count=3)
        stats = store.get_moe_stats()
        assert stats[0]["avg_total_tokens"] == 90


# ── Recording helper ─────────────────────────────────────────────


class TestRecordMoeUsage:
    def test_computes_correct_totals(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        moe_result = _make_moe_result()
        _record_moe_usage(store, moe_result, "convo-1")
        stats = store.get_moe_stats()
        assert len(stats) == 1
        assert stats[0]["run_count"] == 1
        assert stats[0]["avg_total_tokens"] == 90  # 3 × 30
        assert stats[0]["total_failures"] == 0

    def test_handles_failed_experts(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        experts = [
            _make_expert("openai", "gpt-4", consensus_score=0.9),
            _make_expert("anthropic", "claude", error="TIMEOUT"),
        ]
        moe_result = _make_moe_result(experts=experts, agreement_ratio=0.0)
        _record_moe_usage(store, moe_result, "convo-1")
        stats = store.get_moe_stats()
        assert len(stats) == 1
        assert stats[0]["total_failures"] == 1
        # Only 1 successful expert's tokens counted
        assert stats[0]["avg_total_tokens"] == 30

    def test_persistence_failure_swallowed(self) -> None:
        storage = MagicMock()
        storage.insert_moe_usage.side_effect = RuntimeError("db gone")
        moe_result = _make_moe_result()
        # Should not raise — tracking must never break a turn
        _record_moe_usage(storage, moe_result, "convo-1")


# ── Integration: moe_stats tool ──────────────────────────────────


class TestMoeStatsTool:
    def test_returns_data(self, tmp_path: Any) -> None:
        store = _store(tmp_path)
        _insert_sample(store)

        container = MagicMock()
        container.storage = store
        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"container": container}

        from openchronicle.interfaces.mcp.tools.system import register

        mcp_server = MagicMock()
        registered: dict[str, Any] = {}
        mcp_server.tool.return_value = lambda fn: registered.update({fn.__name__: fn}) or fn
        register(mcp_server)

        result = registered["moe_stats"](ctx=ctx)
        assert len(result) == 1
        assert result[0]["winner_provider"] == "openai"
        assert result[0]["run_count"] == 1
