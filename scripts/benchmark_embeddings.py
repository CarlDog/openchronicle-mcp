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
hybrid), backfill wall time (= full-reindex duration), embed failure
count (the `truncate:false` long-input leg — the corpus has multi-10k
char rows), measured dimensions, and query latency. An FTS5-only
baseline runs once: a candidate that can't beat it adds nothing.

Searches run with `include_pinned=False`, so the pin-float policy
(keyword-matched, provider-independent) can't mask ranking quality.

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


@dataclass
class ChannelMetrics:
    results: list[QueryResult] = field(default_factory=list)

    def summarize(self) -> dict[str, Any]:
        n = len(self.results)
        ranks = [r.rank for r in self.results]
        lat = [r.latency for r in self.results]

        def recall_at(k: int) -> float:
            return sum(1 for r in ranks if r is not None and r <= k) / n

        mrr = sum(1.0 / r for r in ranks if r is not None) / n
        return {
            "recall@1": round(recall_at(1), 3),
            "recall@5": round(recall_at(5), 3),
            "recall@10": round(recall_at(10), 3),
            "mrr@10": round(mrr, 3),
            "latency_mean_s": round(statistics.mean(lat), 3),
            "latency_p95_s": round(sorted(lat)[int(0.95 * n)], 3),
            "misses": [i for i, r in enumerate(ranks) if r is None],
        }


def load_fixture(corpus_path: Path, gold_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    gold = json.loads(gold_path.read_text(encoding="utf-8"))["queries"]
    # Resolve gold-set id prefixes against the corpus, loudly.
    ids = [m["id"] for m in corpus]
    for entry in gold:
        resolved = []
        for prefix in entry["relevant"]:
            matches = [i for i in ids if i.startswith(prefix)]
            if len(matches) != 1:
                raise SystemExit(f"gold-set prefix {prefix!r} resolves to {len(matches)} corpus ids")
            resolved.append(matches[0])
        entry["relevant_ids"] = resolved
    return corpus, gold


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


def run_candidate(
    name: str,
    adapter: EmbeddingPort,
    corpus: list[dict[str, Any]],
    gold: list[dict[str, Any]],
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        store = build_store(corpus, db_path=str(Path(tmp) / "bench.db"))
        try:
            service = EmbeddingService(adapter, store)
            t0 = time.perf_counter()
            backfill = service.generate_missing()
            backfill_s = time.perf_counter() - t0

            semantic, hybrid = ChannelMetrics(), ChannelMetrics()
            for entry in gold:
                relevant = entry["relevant_ids"]
                # include_pinned=True + pinned_limit=0 is the measurement
                # configuration, arrived at the hard way — both defaults are
                # policy, not relevance, and each one broke a run:
                #   - include_pinned=False doesn't just skip the pin-float, it
                #     excludes pinned rows from results entirely → the 10
                #     pinned gold targets were structurally unreachable and
                #     every candidate "missed" exactly them.
                #   - include_pinned=True with the default pinned_limit (10,
                #     == top_k) floats keyword-matched pins ahead of ALL
                #     ranked results → with 149 corpus pins, every candidate
                #     scored byte-identically because the top-10 was pins.
                # pinned_limit=0 disables the float while leaving pins
                # eligible in both ranking channels — pure ranking quality.
                t = time.perf_counter()
                hits = service.search_semantic(entry["q"], top_k=TOP_K, include_pinned=True, pinned_limit=0)
                semantic.results.append(QueryResult(best_rank(hits, relevant), time.perf_counter() - t))
                t = time.perf_counter()
                hits = service.search_hybrid(entry["q"], top_k=TOP_K, include_pinned=True, pinned_limit=0)
                hybrid.results.append(QueryResult(best_rank(hits, relevant), time.perf_counter() - t))

            return {
                "candidate": name,
                "dimensions_measured": store.stored_embedding_dimensions(),
                "backfill_s": round(backfill_s, 1),
                "embedded": backfill.generated,
                "embed_failures": backfill.failed,
                "semantic": semantic.summarize(),
                "hybrid": hybrid.summarize(),
            }
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
                metrics.results.append(QueryResult(rank, time.perf_counter() - t))
            return {"candidate": "fts5-only (baseline)", "keyword": metrics.summarize()}
        finally:
            store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--corpus", default=str(root / "data/embedding_benchmark/corpus.json"))
    parser.add_argument("--gold", default=str(root / "data/embedding_benchmark/gold_set.json"))
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
    print(f"corpus: {len(corpus)} memories · gold set: {len(gold)} queries", flush=True)

    results: list[dict[str, Any]] = [run_fts5_baseline(corpus, gold)]
    print(json.dumps(results[0], indent=None), flush=True)

    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        from openchronicle.core.infrastructure.embedding.ollama_adapter import OllamaEmbeddingAdapter

        print(f"\n=== ollama/{model} ===", flush=True)
        try:
            result = run_candidate(
                f"ollama/{model}", OllamaEmbeddingAdapter(model=model, timeout_seconds=args.timeout), corpus, gold
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
            result = run_candidate(label, adapter, corpus, gold)
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
                )
            except Exception as exc:
                result = {"candidate": f"openai/{args.openai_model}", "error": f"{type(exc).__name__}: {exc}"}
            print(json.dumps(result, indent=None), flush=True)
            results.append(result)

    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nresults written to {args.out}", flush=True)


if __name__ == "__main__":
    main()
