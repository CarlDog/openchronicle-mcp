"""Gold-set retrieval benchmark for embedding-provider candidates.

The decision instrument named by design docs 0003 and 0006: no provider
switch happens without this. It loads a real-corpus fixture and an
authored query set (both UNTRACKED, under data/ — they contain private
memory content), builds a throwaway OC store per candidate, backfills it
through the candidate's real adapter, and scores retrieval through the
REAL pipeline (`EmbeddingService.search_semantic` / `search_hybrid`,
RRF and all) — not a standalone cosine loop that could drift from what
production does.

Reported per candidate: recall@1/5/10 and MRR@10 (semantic-only and
hybrid), each also split into pinned-target vs unpinned-target subsets
and a deterministic ~60/40 tune/validate split (ADR 0008 §3), backfill
wall time (= full-reindex duration), embed failure count (the
`truncate:false` long-input leg — the corpus has multi-10k char rows),
measured dimensions, and query latency. An FTS5-only baseline runs
once: a candidate that can't beat it adds nothing. When the broad-query
fixture is present, a pin-crowding probe reports pins-in-top-10 per
candidate at production defaults (see `probe_pin_crowding`).

Gold searches run at production configuration — since ADR 0008 the
pin-float is gone and pins are a bounded rank lift inside the ranking
itself (`PIN_RANK_LIFT`, currently 0), so production config IS the
measurement config; the old `pinned_limit=0` special case died with
the float. The crowding probe also runs production defaults; the v4
sweep re-runs both scoring passes per injected lift cell.

The store is built and embedded ONCE per candidate; the scoring passes
are separate functions so the v4 PIN_RANK_LIFT sweep can re-score many
constant cells against the same live store without re-embedding.

`--sweep` IS that sweep (ADR 0008 §3, rollout step 4): ONE candidate,
one embed, seven scored cells — `PIN_RANK_LIFT ∈ {0, 2, 4, 8}` plus a
window-only ablation per nonzero lift (fetch extended by the paired
cell's effective lift, lift itself disabled) so the §2 fetch-depth side
effect and the lift's own effect are separately attributable. The
tuning gates (delta crowding, held-out regression veto, unpinned
non-regression, tune-split deltas) are computed from exact hit counts
and PRINTED, but no winner is chosen — adjudication is the operator's.

Usage:
    python scripts/benchmark_embeddings.py \
        --models nomic-embed-text,embeddinggemma,... \
        [--openai-model text-embedding-3-small]   # needs OPENAI_API_KEY
    python scripts/benchmark_embeddings.py --sweep \
        [--models nomic-embed-text] [--out .../sweep_results.json]

Latency caveat: numbers measured on the authoring machine are
indicative only — the deploy target is the NAS CPU. Accuracy is the
gate; re-measure latency on the NAS before a cutover.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from openchronicle.core.application.services.embedding_service import EmbeddingService  # noqa: E402
from openchronicle.core.domain.models.memory_item import MemoryItem  # noqa: E402
from openchronicle.core.domain.models.project import Project  # noqa: E402
from openchronicle.core.domain.ports.embedding_port import EmbeddingPort  # noqa: E402
from openchronicle.core.infrastructure.persistence.sqlite_store import SqliteStore  # noqa: E402

TOP_K = 10


@dataclass
class QueryResult:
    rank: int | None  # 1-based rank of the best-ranked relevant id, None = miss
    latency: float
    pinned_target: bool = False  # derived at load time from the corpus fixture
    split: str = "tune"  # deterministic tune/validate assignment (ADR 0008 §3)


def _rank_summary(results: list[QueryResult]) -> dict[str, Any]:
    """Recall/MRR over a (possibly empty) subset of query results."""
    n = len(results)
    if n == 0:
        return {"n": 0}
    ranks = [r.rank for r in results]

    def recall_at(k: int) -> float:
        return round(sum(1 for r in ranks if r is not None and r <= k) / n, 3)

    mrr = sum(1.0 / r for r in ranks if r is not None) / n
    return {
        "n": n,
        "recall@1": recall_at(1),
        "recall@5": recall_at(5),
        "recall@10": recall_at(10),
        "mrr@10": round(mrr, 3),
    }


@dataclass
class ChannelMetrics:
    results: list[QueryResult] = field(default_factory=list)

    def summarize(self) -> dict[str, Any]:
        n = len(self.results)
        lat = [r.latency for r in self.results]
        out = _rank_summary(self.results)
        out["latency_mean_s"] = round(statistics.mean(lat), 3)
        out["latency_p95_s"] = round(sorted(lat)[int(0.95 * n)], 3)
        out["misses"] = [i for i, r in enumerate(self.results) if r.rank is None]
        # Pinned-target status comes from the corpus fixture's per-memory
        # `pinned` field, joined at load time (ADR 0008 §3 — a flag stored
        # per gold query would silently drift when the corpus is
        # re-snapshotted). The validate ∩ pinned-target cell is the v4
        # sweep's regression-veto instrument (hybrid R@1 over it).
        out["pinned_target"] = _rank_summary([r for r in self.results if r.pinned_target])
        out["unpinned_target"] = _rank_summary([r for r in self.results if not r.pinned_target])
        out["tune"] = _rank_summary([r for r in self.results if r.split == "tune"])
        out["validate"] = _rank_summary([r for r in self.results if r.split == "validate"])
        out["validate_pinned_target"] = _rank_summary(
            [r for r in self.results if r.split == "validate" and r.pinned_target]
        )
        out["tune_pinned_target"] = _rank_summary([r for r in self.results if r.split == "tune" and r.pinned_target])
        return out


def load_fixture(corpus_path: Path, gold_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))["queries"]
    # Resolve gold-set id prefixes against the corpus, loudly.
    ids = [m["id"] for m in corpus]
    pinned_by_id = {m["id"]: bool(m.get("pinned")) for m in corpus}
    for entry in gold:
        resolved = []
        for prefix in entry["relevant"]:
            matches = [i for i in ids if i.startswith(prefix)]
            if len(matches) != 1:
                raise SystemExit(f"gold-set prefix {prefix!r} resolves to {len(matches)} corpus ids")
            resolved.append(matches[0])
        entry["relevant_ids"] = resolved
        # Derived at load time from the corpus fixture, never stored in
        # the gold set: a stored flag silently drifts when the corpus is
        # re-snapshotted (ADR 0008 §3, rev-3 review finding 15).
        entry["pinned_target"] = any(pinned_by_id[i] for i in resolved)
    assign_split(gold)
    return corpus, gold


def assign_split(gold: list[dict[str, Any]]) -> None:
    """Deterministic ~60/40 tune/validate split (ADR 0008 §3).

    Within each stratum (pinned-target / unpinned-target), sort by
    query text and deal 3 tune : 2 validate in rotation — no RNG,
    stable across runs and machines, insensitive to the order queries
    were appended to the fixture. Stratifying makes the 60/40 ratio
    hold inside the subset the v4 sweep's regression veto actually
    reads (an unstratified deal happened to land 12 of the 20
    pinned-target queries in validate; stratified, 20 pinned-target
    queries yield the ADR's expected ~8 in validate by construction).
    """
    for stratum in (True, False):
        entries = sorted((e for e in gold if e["pinned_target"] is stratum), key=lambda e: str(e["q"]))
        for i, entry in enumerate(entries):
            entry["split"] = "tune" if i % 5 < 3 else "validate"


def build_store(corpus: list[dict[str, Any]], db_path: str) -> SqliteStore:
    store = SqliteStore(db_path=db_path)
    store.init_schema()
    project_ids = {m["project_id"] for m in corpus if m.get("project_id")}
    for pid in project_ids:
        store.add_project(Project(id=pid, name=pid[:8]))
    for m in corpus:
        store.add_memory(
            MemoryItem(
                id=m["id"],
                content=m["content"],
                tags=m.get("tags") or [],
                created_at=datetime.fromisoformat(m["created_at"]),
                pinned=bool(m.get("pinned")),
                project_id=m.get("project_id"),
                source=m.get("source") or "manual",
            )
        )
    return store


def best_rank(hits: list[Any], relevant: list[str]) -> int | None:
    for i, scored in enumerate(hits, start=1):
        if scored.item.id in relevant:
            return i
    return None


def embed_corpus(adapter: EmbeddingPort, store: SqliteStore) -> tuple[EmbeddingService, dict[str, Any]]:
    """Embed the already-built store ONCE per candidate.

    Kept separate from the scoring passes (`score_gold`,
    `probe_pin_crowding`) so the v4 PIN_RANK_LIFT sweep can re-score
    many constant cells — each with its own `EmbeddingService`
    constructed over this same store and these same vectors — without
    re-embedding. Today's benchmark runs each scoring pass once.
    """
    service = EmbeddingService(adapter, store)
    t0 = time.perf_counter()
    backfill = service.generate_missing()
    stats = {
        "backfill_s": round(time.perf_counter() - t0, 1),
        "embedded": backfill.generated,
        "embed_failures": backfill.failed,
    }
    return service, stats


def score_gold(service: EmbeddingService, gold: list[dict[str, Any]]) -> tuple[ChannelMetrics, ChannelMetrics]:
    """One gold-set scoring pass (semantic + hybrid) against a live service.

    Re-runnable: touches nothing but the queries, so it can be called
    repeatedly against the same embedded store.
    """
    semantic, hybrid = ChannelMetrics(), ChannelMetrics()
    for entry in gold:
        relevant = entry["relevant_ids"]
        # Production configuration IS the measurement configuration
        # (ADR 0008): the pin-float that once had to be disabled here
        # (`pinned_limit=0` — include_pinned=False was tried first and
        # made every pinned gold target structurally unreachable) is
        # gone. Pins are a bounded rank lift inside the ranking, and
        # the v4 sweep injects lift cells via the EmbeddingService
        # constructor rather than per-call knobs.
        t = time.perf_counter()
        hits = service.search_semantic(entry["q"], top_k=TOP_K, include_pinned=True)
        semantic.results.append(
            QueryResult(best_rank(hits, relevant), time.perf_counter() - t, entry["pinned_target"], entry["split"])
        )
        t = time.perf_counter()
        hits = service.search_hybrid(entry["q"], top_k=TOP_K, include_pinned=True)
        hybrid.results.append(
            QueryResult(best_rank(hits, relevant), time.perf_counter() - t, entry["pinned_target"], entry["split"])
        )
    return semantic, hybrid


def probe_pin_crowding(service: EmbeddingService, broad_queries: list[str]) -> dict[str, Any]:
    """Pin-crowding probe (ADR 0008 §3) over the broad-query fixture.

    Runs each genuinely-broad query through `search_hybrid` at
    production defaults — top_k=10, include_pinned=True, the service's
    own ranking policy (ADR 0008's rank lift at the constructed lift
    constant) — and counts pins in the top 10. This measures ABSOLUTE
    crowding under the cell's policy; the ADR's tuning gate is a DELTA
    against the LIFT=0 cell, and that comparison arrives with the v4
    sweep, which re-runs this probe per constant cell against the same
    embedded store.
    """
    per_query = []
    for q in broad_queries:
        hits = service.search_hybrid(q, top_k=TOP_K, include_pinned=True)
        per_query.append({"q": q, "pins_in_top_10": sum(1 for s in hits if s.item.pinned)})
    counts = [int(p["pins_in_top_10"]) for p in per_query]
    return {
        "per_query": per_query,
        "mean_pins_in_top_10": round(statistics.mean(counts), 2),
        "max_pins_in_top_10": max(counts),
    }


def run_candidate(
    name: str,
    adapter: EmbeddingPort,
    corpus: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    broad_queries: list[str],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        store = build_store(corpus, db_path=str(Path(tmp) / "bench.db"))
        try:
            service, backfill_stats = embed_corpus(adapter, store)
            semantic, hybrid = score_gold(service, gold)
            result = {
                "candidate": name,
                "dimensions_measured": store.stored_embedding_dimensions(),
                **backfill_stats,
                "semantic": semantic.summarize(),
                "hybrid": hybrid.summarize(),
            }
            if broad_queries:
                result["pin_crowding"] = probe_pin_crowding(service, broad_queries)
            return result
        finally:
            store.close()


def run_fts5_baseline(corpus: list[dict[str, Any]], gold: list[dict[str, Any]]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        store = build_store(corpus, db_path=str(Path(tmp) / "bench.db"))
        try:
            metrics = ChannelMetrics()
            for entry in gold:
                t = time.perf_counter()
                items = store.search_memory(entry["q"], top_k=TOP_K, include_pinned=True)
                rank = None
                for i, item in enumerate(items, start=1):
                    if item.id in entry["relevant_ids"]:
                        rank = i
                        break
                metrics.results.append(
                    QueryResult(rank, time.perf_counter() - t, entry["pinned_target"], entry["split"])
                )
            return {"candidate": "fts5-only (baseline)", "keyword": metrics.summarize()}
        finally:
            store.close()


# ── ADR 0008 §3 tuning sweep (rollout step 4) ───────────────────────

SWEEP_CELLS: tuple[tuple[str, str, int, int | None], ...] = (
    # (cell, role, pin_rank_lift, fetch_extension)
    ("lift0", "baseline", 0, None),
    ("lift2", "candidate", 2, None),
    ("ablate2", "ablation", 0, 2),
    ("lift4", "candidate", 4, None),
    ("ablate4", "ablation", 0, 4),
    ("lift8", "candidate", 8, None),
    ("ablate8", "ablation", 0, 8),
)


class _QueryCachingPort(EmbeddingPort):
    """Delegating wrapper that memoizes ``embed()`` by exact text.

    Sweep-only: all seven cells re-run the same gold + broad queries,
    so caching guarantees every cell scores IDENTICAL query vectors —
    cross-cell deltas are pure ranking policy, never provider jitter —
    and saves ~6/7 of the query-embedding round-trips. Every identity
    method delegates: a divergent identity would silently empty the
    semantic channel (space-scoped ``list_embeddings``) and the run
    would look valid while measuring nothing.
    """

    def __init__(self, inner: EmbeddingPort) -> None:
        self._inner = inner
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        if text not in self._cache:
            self._cache[text] = self._inner.embed(text)
        return self._cache[text]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_batch(texts)

    def dimensions(self) -> int:
        return self._inner.dimensions()

    def model_name(self) -> str:
        return self._inner.model_name()

    def provider_name(self) -> str:
        return self._inner.provider_name()

    def model_revision(self) -> str | None:
        return self._inner.model_revision()

    def settings_fingerprint(self) -> str:
        return self._inner.settings_fingerprint()


def _subset(
    results: list[QueryResult],
    *,
    split: str | None = None,
    pinned_target: bool | None = None,
) -> list[QueryResult]:
    out = results
    if split is not None:
        out = [r for r in out if r.split == split]
    if pinned_target is not None:
        out = [r for r in out if r.pinned_target is pinned_target]
    return out


def _hits_at(results: list[QueryResult], k: int) -> int:
    return sum(1 for r in results if r.rank is not None and r.rank <= k)


def _mrr(results: list[QueryResult]) -> float:
    return sum(1.0 / r.rank for r in results if r.rank is not None) / len(results) if results else 0.0


def _r1_delta(cell: list[QueryResult], base: list[QueryResult]) -> dict[str, Any]:
    """Exact R@1 delta over one query subset, in whole queries.

    Computed from raw hit COUNTS, never the rounded summary rates — the
    gates must be exact. ``noise`` labels a delta at or under one
    query's granularity (ADR 0008 §3); the validate veto deliberately
    ignores the label — any negative validated delta rejects.
    """
    n = len(cell)
    if n != len(base):
        raise SystemExit(f"subset size mismatch: {n} vs {len(base)} — cells scored different query sets")
    hits_cell, hits_base = _hits_at(cell, 1), _hits_at(base, 1)
    delta = hits_cell - hits_base
    return {
        "n": n,
        "baseline_hits": hits_base,
        "cell_hits": hits_cell,
        "delta_queries": delta,
        "delta_rate": round(delta / n, 4) if n else 0.0,
        "granularity": round(1 / n, 4) if n else None,
        "noise": abs(delta) <= 1,
    }


def _crowding_gate(cell_probe: dict[str, Any], base_probe: dict[str, Any]) -> dict[str, Any]:
    """The ADR §3 crowding gate, as a DELTA over the LIFT=0 cell.

    Mean pins-in-top-10 minus the baseline's mean ≤ 1.0 AND max
    per-query increase ≤ 2 — both from exact integer counts (the
    mean condition is evaluated as ``sum_delta <= n``, no floats).
    """
    cell_counts = [int(p["pins_in_top_10"]) for p in cell_probe["per_query"]]
    base_counts = [int(p["pins_in_top_10"]) for p in base_probe["per_query"]]
    increases = [c - b for c, b in zip(cell_counts, base_counts, strict=True)]
    sum_delta = sum(increases)
    n = len(increases)
    return {
        "mean_delta": round(sum_delta / n, 4),
        "max_per_query_increase": max(increases),
        "per_query_increase": increases,
        "pass": bool(sum_delta <= n and max(increases) <= 2),
    }


def compute_gates(
    cell_name: str,
    role: str,
    hybrid: ChannelMetrics,
    semantic: ChannelMetrics,
    probe: dict[str, Any],
    base_hybrid: ChannelMetrics,
    base_semantic: ChannelMetrics,
    base_probe: dict[str, Any],
) -> dict[str, Any]:
    """Every ADR 0008 §3 tuning gate for one cell, vs the LIFT=0 cell.

    Verdicts are computed and printed only — `eligible` means "no gate
    rejects this cell", never "this cell wins". The LIFT=0 cell passes
    by construction (all deltas are zero against itself).
    """
    hy, base_hy = hybrid.results, base_hybrid.results
    crowding = _crowding_gate(probe, base_probe)
    veto = _r1_delta(
        _subset(hy, split="validate", pinned_target=True),
        _subset(base_hy, split="validate", pinned_target=True),
    )
    veto["verdict"] = "REJECTED" if veto["delta_queries"] < 0 else "pass"
    unpinned = _r1_delta(_subset(hy, pinned_target=False), _subset(base_hy, pinned_target=False))
    unpinned["pass"] = bool(unpinned["delta_queries"] >= 0)
    un_cell, un_base = _subset(hy, pinned_target=False), _subset(base_hy, pinned_target=False)

    failed = []
    if not crowding["pass"]:
        failed.append("crowding")
    if veto["verdict"] == "REJECTED":
        failed.append("validate_veto")
    if not unpinned["pass"]:
        failed.append("unpinned_nonregression")
    return {
        "cell": cell_name,
        "role": role,
        "crowding_delta_gate": crowding,
        "validate_pinned_hybrid_r1_veto": veto,
        "tune_pinned_hybrid_r1": _r1_delta(
            _subset(hy, split="tune", pinned_target=True),
            _subset(base_hy, split="tune", pinned_target=True),
        ),
        "tune_overall_hybrid_r1": _r1_delta(_subset(hy, split="tune"), _subset(base_hy, split="tune")),
        "unpinned_hybrid_r1_nonregression": unpinned,
        "unpinned_informational": {
            "hybrid_r5_delta_queries": _hits_at(un_cell, 5) - _hits_at(un_base, 5),
            "hybrid_mrr10_delta": round(_mrr(un_cell) - _mrr(un_base), 4),
            "semantic_r1_delta_queries": _hits_at(_subset(semantic.results, pinned_target=False), 1)
            - _hits_at(_subset(base_semantic.results, pinned_target=False), 1),
        },
        "failed_gates": failed,
        "eligible": not failed,
    }


def _print_gate_table(gates: list[dict[str, Any]]) -> None:
    print(
        f"\n{'cell':<9}{'role':<11}{'crowd mean_d':>13}{'crowd max_inc':>14}"
        f"{'veto dR@1':>11}{'tune-pin dR@1':>15}{'unpin dR@1':>12}  verdict",
        flush=True,
    )
    for g in gates:
        verdict = "eligible" if g["eligible"] else "FAILED: " + ",".join(g["failed_gates"])
        print(
            f"{g['cell']:<9}{g['role']:<11}"
            f"{g['crowding_delta_gate']['mean_delta']:>13}{g['crowding_delta_gate']['max_per_query_increase']:>14}"
            f"{g['validate_pinned_hybrid_r1_veto']['delta_queries']:>11}"
            f"{g['tune_pinned_hybrid_r1']['delta_queries']:>15}"
            f"{g['unpinned_hybrid_r1_nonregression']['delta_queries']:>12}  {verdict}",
            flush=True,
        )


def run_sweep(
    args: argparse.Namespace,
    corpus: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    broad_queries: list[str],
) -> None:
    """ADR 0008 §3 tuning sweep: embed once, score all seven cells."""
    models = [m.strip() for m in args.models.split(",") if m.strip()] or ["nomic-embed-text"]
    if len(models) != 1:
        raise SystemExit("--sweep scores exactly ONE candidate; pass a single --models entry")
    if not broad_queries:
        raise SystemExit("--sweep requires the broad-query fixture: the crowding gate is a delta over LIFT=0")
    model = models[0]
    from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter

    adapter = _QueryCachingPort(OllamaEmbeddingAdapter(model=model, timeout_seconds=args.timeout))
    doc: dict[str, Any] = {
        "sweep": "PIN_RANK_LIFT (ADR 0008 §3, rollout step 4)",
        "candidate": f"ollama/{model}",
        "top_k": TOP_K,
        "counts": {
            "corpus": len(corpus),
            "corpus_pinned": sum(1 for m in corpus if m.get("pinned")),
            "gold": len(gold),
            "gold_pinned_target": sum(1 for e in gold if e["pinned_target"]),
            "validate_pinned_target": sum(1 for e in gold if e["split"] == "validate" and e["pinned_target"]),
            "broad": len(broad_queries),
        },
        "gate_policy": {
            "crowding": "hybrid top_k=10 over the broad fixture: mean pins-in-top-10 delta vs lift0 <= 1.0 "
            "AND max per-query increase <= 2 (ADR 0008 §3)",
            "validate_veto": "hybrid R@1 over validate∩pinned-target vs lift0: ANY negative delta rejects "
            "(deliberately strict — the noise label does not apply)",
            "unpinned_nonregression": "hybrid R@1 over ALL unpinned-target queries vs lift0 must not drop. "
            "ADR ambiguity resolved here: the gate's metric/subset is unstated, so R@1 over the full "
            "unpinned subset gates; R@5/MRR@10/semantic-R@1 deltas are reported informationally",
            "noise_label": "|delta| <= one query's granularity is labeled noise (ADR 0008 §3)",
            "adjudication": "gates computed and printed only — the winning cell is the operator's decision",
        },
        "cells": [],
        "gates": [],
    }

    with tempfile.TemporaryDirectory() as tmp:
        store = build_store(corpus, db_path=str(Path(tmp) / "bench.db"))
        try:
            print(f"\n=== sweep candidate ollama/{model}: embedding once ===", flush=True)
            _service, backfill_stats = embed_corpus(adapter, store)
            doc["backfill"] = backfill_stats
            print(json.dumps(backfill_stats), flush=True)

            base: tuple[ChannelMetrics, ChannelMetrics, dict[str, Any]] | None = None
            for cell_name, role, lift, extension in SWEEP_CELLS:
                print(f"\n=== cell {cell_name} (pin_rank_lift={lift}, fetch_extension={extension}) ===", flush=True)
                service = EmbeddingService(adapter, store, pin_rank_lift=lift, fetch_extension=extension)
                semantic, hybrid = score_gold(service, gold)
                probe = probe_pin_crowding(service, broad_queries)
                doc["cells"].append(
                    {
                        "cell": cell_name,
                        "role": role,
                        "pin_rank_lift": lift,
                        "fetch_extension": extension,
                        "semantic": semantic.summarize(),
                        "hybrid": hybrid.summarize(),
                        "pin_crowding": probe,
                    }
                )
                if base is None:
                    # lift0 anchors every delta; a dead semantic channel
                    # here would zero all cells' semantic terms silently.
                    if doc["cells"][0]["semantic"].get("recall@10", 0) == 0:
                        raise SystemExit("lift0 semantic recall@10 is 0 — space-identity mismatch, not a measurement")
                    base = (semantic, hybrid, probe)
                gates = compute_gates(cell_name, role, hybrid, semantic, probe, base[1], base[0], base[2])
                doc["gates"].append(gates)
                print(
                    json.dumps(
                        {
                            k: gates[k]
                            for k in (
                                "crowding_delta_gate",
                                "validate_pinned_hybrid_r1_veto",
                                "unpinned_hybrid_r1_nonregression",
                                "failed_gates",
                                "eligible",
                            )
                        }
                    ),
                    flush=True,
                )
                # Incremental write: a crash at cell N keeps cells 1..N-1.
                Path(args.out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
        finally:
            store.close()

    _print_gate_table(doc["gates"])
    print(f"\nsweep results written to {args.out}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--corpus", default=str(root / "data/embedding_benchmark/corpus.json"))
    parser.add_argument("--gold", default=str(root / "data/embedding_benchmark/gold_set.json"))
    parser.add_argument(
        "--broad",
        default=str(root / "data/embedding_benchmark/broad_queries.json"),
        help="broad-query fixture for the pin-crowding probe (skipped if missing)",
    )
    parser.add_argument("--models", default="", help="comma-separated Ollama model names")
    parser.add_argument("--openai-model", default="", help="OpenAI model (needs OPENAI_API_KEY)")
    parser.add_argument(
        "--cloud",
        action="append",
        default=[],
        metavar="LABEL|MODEL|BASE_URL|KEY_ENV|DIMS",
        help="OpenAI-compatible cloud leg, repeatable. Empty BASE_URL = api.openai.com; "
        "KEY_ENV names the vault/env var holding the key; DIMS is the dimensions to request.",
    )
    parser.add_argument("--timeout", type=float, default=600.0, help="per-request adapter timeout")
    parser.add_argument("--out", default=str(root / "data/embedding_benchmark/results.json"))
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="ADR 0008 §3 PIN_RANK_LIFT sweep: ONE candidate (--models, default nomic-embed-text), embed once, "
        "score lift cells {0,2,4,8} plus window-only ablations with delta gates vs LIFT=0",
    )
    args = parser.parse_args()

    # Provider keys come from the DPAPI vault (scripts/env_vault.py) when
    # present — decrypted straight into this process's environment, never
    # printed, never in shell history. Shell-set variables still win.
    from env_vault import load_vault

    loaded = load_vault()
    if loaded:
        print(f"vault: loaded {len(loaded)} key(s) into process env", flush=True)

    corpus, gold = load_fixture(Path(args.corpus), Path(args.gold))
    tune = [e for e in gold if e["split"] == "tune"]
    validate = [e for e in gold if e["split"] == "validate"]
    print(
        f"corpus: {len(corpus)} memories · gold set: {len(gold)} queries "
        f"({sum(1 for e in gold if e['pinned_target'])} pinned-target) · "
        f"split: tune {len(tune)} ({sum(1 for e in tune if e['pinned_target'])} pinned-target) / "
        f"validate {len(validate)} ({sum(1 for e in validate if e['pinned_target'])} pinned-target)",
        flush=True,
    )

    broad_path = Path(args.broad)
    broad_queries: list[str] = []
    if broad_path.exists():
        broad_queries = json.loads(broad_path.read_text(encoding="utf-8"))["queries"]
        print(f"broad-query fixture: {len(broad_queries)} queries (pin-crowding probe on)", flush=True)
    else:
        print(f"broad-query fixture not found at {broad_path} — pin-crowding probe skipped", flush=True)

    if args.sweep:
        run_sweep(args, corpus, gold, broad_queries)
        return

    results: list[dict[str, Any]] = [run_fts5_baseline(corpus, gold)]
    print(json.dumps(results[0], indent=None), flush=True)

    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter

        print(f"\n=== ollama/{model} ===", flush=True)
        try:
            result = run_candidate(
                f"ollama/{model}",
                OllamaEmbeddingAdapter(model=model, timeout_seconds=args.timeout),
                corpus,
                gold,
                broad_queries,
            )
        except Exception as exc:  # a dead candidate shouldn't kill the run
            result = {"candidate": f"ollama/{model}", "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(result, indent=None), flush=True)
        results.append(result)
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")

    for spec in args.cloud:
        parts = spec.split("|")
        if len(parts) != 5:
            print(f"bad --cloud spec (need 5 |-fields): {spec}", flush=True)
            continue
        label, model, base_url, key_env, dims = (p.strip() for p in parts)
        key = os.getenv(key_env)
        if not key:
            print(f"\n{label}: {key_env} not in vault/env — skipping", flush=True)
            continue
        from openchronicle.core.infrastructure.embedding.openai_adapter import OpenAIEmbeddingAdapter

        print(f"\n=== {label} ===", flush=True)
        try:
            adapter = OpenAIEmbeddingAdapter(
                model=model,
                dimensions=int(dims) if dims else 1536,
                api_key=key,
                base_url=base_url or None,
                timeout_seconds=args.timeout,
            )
            result = run_candidate(label, adapter, corpus, gold, broad_queries)
        except Exception as exc:
            result = {"candidate": label, "error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(result, indent=None), flush=True)
        results.append(result)
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")

    if args.openai_model:
        if not os.getenv("OPENAI_API_KEY"):
            print("\nOPENAI_API_KEY not set — skipping incumbent leg", flush=True)
        else:
            from openchronicle.core.infrastructure.embedding.openai_adapter import OpenAIEmbeddingAdapter

            print(f"\n=== openai/{args.openai_model} ===", flush=True)
            try:
                result = run_candidate(
                    f"openai/{args.openai_model}",
                    OpenAIEmbeddingAdapter(model=args.openai_model, timeout_seconds=args.timeout),
                    corpus,
                    gold,
                    broad_queries,
                )
            except Exception as exc:
                result = {"candidate": f"openai/{args.openai_model}", "error": f"{type(exc).__name__}: {exc}"}
            print(json.dumps(result, indent=None), flush=True)
            results.append(result)

    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nresults written to {args.out}", flush=True)


if __name__ == "__main__":
    main()
