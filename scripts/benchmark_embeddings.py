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

Usage:
    python scripts/benchmark_embeddings.py \
        --models nomic-embed-text,embeddinggemma,... \
        [--openai-model text-embedding-3-small]   # needs OPENAI_API_KEY

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
