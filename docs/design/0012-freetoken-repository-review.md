# FreeToken repository review for OpenChronicle

**Recorded:** 2026-09-09 UTC. **Status:** completed comparative review;
recommendations unratified, measurement-gated, and unscheduled. This is a
research document, not an ADR accepting a provider or a runtime change.
[CODEBASE_ASSESSMENT.md](../CODEBASE_ASSESSMENT.md) remains authoritative for
current state; [V3_PLAN.md](../V3_PLAN.md) remains the backlog.

**Work item:** `CarlDog/openchronicle-mcp#freetoken-review-2026-09-09`.

## Source, baseline, and conclusion

Reviewed [`FlashML-org/FreeToken` at `e05cff83`](https://github.com/FlashML-org/FreeToken/tree/e05cff83a04b322fc7823678aa2d05c826aad26c)
against OpenChronicle HEAD
`f1ed05b936123bed105c4ed9d0867ef085238637`. OpenChronicle had pre-existing
uncommitted metrics/exporter work and related design/status updates. This
review preserves that work and its separate local/live acceptance gates.
Target source links below are pinned to the baseline; later working-tree
performance work is not represented as part of that commit.

**FreeToken is not a direct embedding-provider replacement for OpenChronicle.**
The inspected FreeToken server exposes generation protocols, not OpenChronicle's
required embedding API. OpenChronicle's [Ollama adapter][oc-ollama] calls
`/api/embed`, disables truncation, and validates returned vectors. Pointing
that adapter at an OpenAI-compatible generation URL would fail its contract.

The worthwhile transfer is narrower: measure repeated query-embedding work,
then consider a bounded exact-query cache and request coalescing if the measured
benefit justifies their complexity. FreeToken's kernel or MoE speed does not
establish an OpenChronicle bottleneck. No language rewrite or new inference
service is justified by this comparison. The operator's standing priority is
accuracy first, then speed and responsiveness; cache changes must preserve
accuracy before any performance benefit can justify adoption. The concurrent
[memory ecosystem review](0011-memory-ecosystem-review.md) is a separate
research record and retains its own dispositions.

## Recommendation register

| ID | Candidate | Disposition | Trigger / acceptance proof |
| --- | --- | --- | --- |
| OC-FT-01 | Measure duplicate query-embedding calls before changing caching | Open candidate; unscheduled | Observe duplicate rate, embedding share of latency, concurrency, and provider identity on a bounded representative workload |
| OC-FT-02 | Bounded exact-query embedding cache plus singleflight | Parked on OC-FT-01 | Require measurable benefit, full embedding-space identity, strict memory bounds, failure/cancellation tests, and unchanged retrieval quality |
| OC-FT-03 | Resource ownership, truthful capabilities, and measured acceptance | Corroborates existing boundaries; no new batch | Apply only to a demonstrated gap; existing embedding identity, vector validation, observability, and performance gates remain authoritative |
| OC-FT-04 | FreeToken as the current embedding/reranking service | Rejected for this snapshot | Required endpoints and vector contract are absent; generation API compatibility does not supply them |
| OC-FT-05 | GPU prefix/weight cache as a semantic memory cache | Rejected as a transplant | Exact token prefixes and GPU allocation solve a different problem from mutable memory retrieval |
| OC-FT-06 | Add a generation/agent runtime or rewrite OpenChronicle's language | Rejected by scope and evidence | The memory-only application boundary remains; this review measured no justification for either change |

## 1. A query cache is a hypothesis with an explicit identity boundary

At the reviewed baseline, the [semantic-search path][oc-search] calls
`_embed_single(query)` for each search. That is an identifiable place to
measure duplicate work. It is not evidence that duplicates are frequent or
that query embedding dominates end-to-end latency.

FreeToken's [hybrid radix cache][ft-prefix] illustrates explicit reuse boundaries
and bounded scarce resources. It matches token prefixes and supported recurrent
state boundaries; it is not a semantic-similarity response cache. An
OpenChronicle adaptation would cache **embedding vectors for identical effective
provider input**, not FreeToken's internal state or ranked search results.

Before implementation, OC-FT-01 should collect sanitized counts and timing,
without raw private query text: duplicate frequency within candidate windows,
same-query concurrency, provider latency, cacheable working-set size, and the
share of total search latency spent embedding. Stop at a predeclared duration
and sample size. If the saving is small, close the candidate rather than
building a cache because the source project has one.

If the hypothesis clears a later operator-approved gate, OC-FT-02 must satisfy:

- **Complete identity:** effective input and every embedding-space determinant,
  including provider/model, revision, settings/dimensions, and input transforms.
  Reuse the accepted [composite embedding identity](0005-embedding-identity.md)
  contract. A model-name-only key is insufficient.
- **Bounded memory and life:** explicit entry/byte limits, eviction and lifetime;
  oversized inputs cannot consume an unbounded cache. Identity changes cannot
  reuse old vectors.
- **Coalescing without coupled failure:** concurrent identical requests can
  share one in-flight computation; one canceled waiter must not strand peers,
  and provider failure must not become a cached successful empty result.
- **Correct publication:** preserve vector dimension/cardinality/finiteness
  checks and existing embedding fallback/error behavior. Stored-content
  embedding reuse already exists and should not be reimplemented.
- **Search freshness:** cache the query vector only. Ranked results depend on
  mutable memories, filters, deletion, pins, and ranking policy, so this does
  not authorize result caching across mutations.
- **Measured acceptance:** fixed cold/warm and concurrent fixtures show lower
  relevant latency/provider work within a stated memory budget, with the same
  retrieval gold-set results and no regression in failure/cancellation paths.

No TTL, entry limit, or implementation approach is ratified by this review.

## 2. Separate inference measurements from application measurements

FreeToken's [hardware profile][ft-profile] derives execution settings from
overlapped CPU/interconnect behavior. The transferable lesson is to measure the
actual contested resource. It does not establish that faster generation helps
OpenChronicle's embedding provider, SQLite store, or ranker.

The [SQLite store's lock][oc-lock] and the [embedding/search service][oc-search]
have different ownership and latency boundaries. A new inference runtime does
not remove database serialization. Existing [performance measurement work](0010-performance-measurement.md)
must retain its own workload, overhead, RSS, responsiveness, and live gates.
This document performs no NAS load test, exporter acceptance run, benchmark
rerun, or reclassification of those results.

## 3. Source findings relevant to a future service dependency

The full FreeToken review is recorded in that fork's
`docs/fleet-review-2026-09-09.md`. These IDs are upstream findings and adoption
constraints, not newly discovered OpenChronicle defects:

| Source ID | Observation | Relevance here |
| --- | --- | --- |
| FT-01 | [Benchmark operation][ft-benchmark] can overlap an accepted serving start | Any future shared inference dependency needs whole-operation resource ownership |
| FT-02 | [Profile endpoint helper][ft-profile-import] crosses the lightweight dependency boundary | Control/readiness checks should work without model libraries when promised |
| FT-03/04 | [Chat API][ft-chat] silently loses some accepted controls and can echo an unserved model | Preserve explicit capability checks and effective identity; do not infer embedding compatibility from the wire envelope |
| FT-05 | [Sampling fallback][ft-sampling] bypasses the chat server output default | Generation budget behavior cannot be assumed from other protocol adapters |
| FT-06 | Nonstreaming chat lacks the streaming disconnect wrapper | A client timeout does not prove remote resource release |
| FT-07 | [Publication workflow][ft-release] lacks a test-suite gate | A successful image/wheel build is not runtime acceptance |

The accounting outbox and separate daemon process are useful patterns, but no
OpenChronicle receipt-loss or lifecycle defect was demonstrated that warrants
new persistence here. Existing idempotency and shutdown contracts should be
checked before proposing another mechanism.

## Explicit non-adoptions

- Keep the current embedding-provider configuration; no `/api/embed` to chat
  endpoint substitution or unsupported provider declaration.
- No new generation, agent orchestration, or trading/story responsibility in
  OpenChronicle.
- No semantic answer cache based on similar query text. Similarity is not a
  correctness-preserving cache key.
- No GPU weight-format, KV-cache, or scheduler transplant into SQLite storage.
- No assertion that Python is the measured bottleneck, or that FreeToken's
  decode benchmarks predict OpenChronicle's performance.
- No changes to the uncommitted exporter work, metrics defaults, or production
  acceptance status as a consequence of this research receipt.

## Verification and completion boundary

This was source-grounded comparative research. The FreeToken review parsed
463 Python files; successful daemon-test selections totaled 29 passes and two
POSIX-only skips after a temporary-directory recovery. Two ASGI probes used
fake manager/process collaborators; API probes isolated original source
functions with inference collaborators replaced. No full GPU runtime, embedding
pilot, new gold-set run, target application test suite, or production change
was performed in this recording pass.

Research is complete when this assessment and its discovery/status links are
recorded and documentation checks pass. The cache measurement and any later
implementation remain separate operator decisions. No issue status is inferred
or changed, and the documentation working-tree state is not a release claim.

[oc-ollama]: https://github.com/CarlDog/openchronicle-mcp/blob/f1ed05b936123bed105c4ed9d0867ef085238637/src/openchronicle/core/infrastructure/embedding/ollama_adapter.py#L83-L99
[oc-search]: https://github.com/CarlDog/openchronicle-mcp/blob/f1ed05b936123bed105c4ed9d0867ef085238637/src/openchronicle/core/application/services/embedding_service.py#L733-L753
[oc-lock]: https://github.com/CarlDog/openchronicle-mcp/blob/f1ed05b936123bed105c4ed9d0867ef085238637/src/openchronicle/core/infrastructure/persistence/sqlite_store.py#L263
[ft-prefix]: https://github.com/FlashML-org/FreeToken/blob/e05cff83a04b322fc7823678aa2d05c826aad26c/python/freetoken/kvcache/hybrid_radix_cache.py#L75
[ft-profile]: https://github.com/FlashML-org/FreeToken/blob/e05cff83a04b322fc7823678aa2d05c826aad26c/python/freetoken/moe/bench_profile.py#L149
[ft-benchmark]: https://github.com/FlashML-org/FreeToken/blob/e05cff83a04b322fc7823678aa2d05c826aad26c/python/freetoken/daemon/app.py#L338-L381
[ft-profile-import]: https://github.com/FlashML-org/FreeToken/blob/e05cff83a04b322fc7823678aa2d05c826aad26c/python/freetoken/daemon/app.py#L61-L69
[ft-chat]: https://github.com/FlashML-org/FreeToken/blob/e05cff83a04b322fc7823678aa2d05c826aad26c/python/freetoken/server/openai_api.py#L147-L228
[ft-sampling]: https://github.com/FlashML-org/FreeToken/blob/e05cff83a04b322fc7823678aa2d05c826aad26c/python/freetoken/server/generation.py#L151-L187
[ft-release]: https://github.com/FlashML-org/FreeToken/blob/e05cff83a04b322fc7823678aa2d05c826aad26c/.github/workflows/release.yml
