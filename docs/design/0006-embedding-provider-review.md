# Embedding Provider Review

**Status:** Benchmark RUN (see results below) — the local option cleared
the gate; the switch decision is with the operator, pending the NAS
latency leg · **Date:** 2026-08-29

**Requested by the operator** at the close of ADR 0005's
implementation, which is what makes this review timely: provider
switching used to risk silent mixed-vector-space corruption, and now
cannot (the space identity makes a foreign vector invisible, and the
batched reindex makes a full re-embed a ~1-minute operation). The
question "should we switch?" is finally separable from "is switching
safe?" — it is safe; this review is about whether it is *worth it*.

## Live facts (probed 2026-08-29)

| Fact | Value |
|---|---|
| Current provider | `openai` / `text-embedding-3-small` / 1536 dims (NAS stack env) |
| Corpus | 862 memories, ~859 embedded, DB 10.9 MB |
| Full-reindex cost at current pricing | **~$0.02 or less** (corpus ≈ well under 1M tokens; 3-small is $0.02/1M — verify price at decision time) |
| Steady-state cost | Cents per month (a handful of saves + searches per day) |
| NAS Ollama (stack 155) | **32 models, zero with the `embedding` capability** — local embedding requires a pull first |
| Ollama Cloud | Zero embedding models hosted (baseline 2026-08-28; quarterly re-check stands) |
| Adapter readiness | The Ollama adapter is now contract-truthful (ADR 0005 Phase C): fail-visible truncation, validated responses, digest-based revision — it was the weakest link and no longer is |

## The four dimensions that actually differ

**Cost — a non-argument.** At this corpus, the entire annual OpenAI
embedding spend is likely under a dollar. Nothing here justifies any
engineering hour on cost grounds; ignore every argument of this shape.

**Privacy — the real argument for local.** Every `memory_save` sends
the memory's full content to OpenAI, and every hybrid/semantic search
sends the query. V3_PLAN's own words call the corpus
"sometimes secrets-adjacent," and the cloud-backup design (0001) went
to age-encryption lengths to keep this same content unreadable at a
cloud provider — while the embedding path ships it to a different
cloud provider in plaintext API calls on every write. That asymmetry
is the strongest standing argument in this review. It is tempered by:
OpenAI's API-data policy (not used for training, retention-limited —
verify terms at decision time), and the fact that the *queries* often
matter as much as the stored content.

**Quality — unbenchmarked, and the gate.** `text-embedding-3-small`
is a strong general-purpose model; the plausible local candidates
(`embeddinggemma`, `qwen3-embedding`, `all-minilm`, and the adapter's
default `nomic-embed-text`) range from competitive to clearly weaker,
and 0003 was explicit that an upstream recommendation is not evidence.
**No switch happens without the 0003 gold-set benchmark**: a query set
built from real memories, recall@k and rank-of-known-relevant, hybrid
vs semantic-only, long-input behavior under `truncate:false`, index +
query latency on the NAS CPU, and full-reindex duration. The fleet's
NAS rules note embedding models are exempt from the size gates —
they're small (nomic ≈ 137M params) and CPU-fast — so hardware is not
the blocker; unmeasured quality is.

**Reliability — a wash, differently shaped.** OpenAI adds an internet
and vendor dependency; its failure mode is well-handled (hybrid degrades
to FTS5, health now shows `failure_count`/`last_failure_op` since
v3.1.0). Local Ollama removes the internet dependency but adds a
same-host service dependency (one more thing a NAS reboot must bring
back, one more RAM resident) — and its failure mode is identical
FTS5 degradation. Neither direction wins outright.

## Options

| Option | Verdict |
|---|---|
| **Keep `text-embedding-3-small`** (current) | **Default. Recommended today.** Proven in daily retrieval, trivial cost, degradation well-instrumented. The privacy asymmetry is real but pre-existing and knowingly accepted (same posture as the trusted-LAN auth decision) |
| Switch to `text-embedding-3-large` | No demonstrated retrieval-quality gap to close; 3072 dims doubles vector storage for an unmeasured gain. Not recommended without a benchmark showing 3-small failing |
| **Local Ollama** (`embeddinggemma` / `qwen3-embedding` / `nomic-embed-text`) | **The credible challenger, gated on the benchmark.** Closes the privacy asymmetry outright; switching is now config + pull + ~1-minute reindex, and the identity machinery makes a botched switch impossible to *silently* get wrong. Pull and benchmark before any cutover — never switch on vibes |
| Ollama Cloud | Non-option: hosts zero embedding models. Quarterly re-check stands; if that changes it inherits the same benchmark gate *and* the same privacy posture as OpenAI |
| Atlas Cloud | Non-option today: 65 Text models, all chat/completion, zero embeddings (probed 2026-08-29). Watched on the same quarterly clock; would be config-only to adopt via `OPENAI_BASE_URL` if an OpenAI-compatible embeddings endpoint appears |
| Dual/fallback providers | Rejected — a second active provider is a second vector space and a second failure surface; the FTS5 fallback already covers outages. The identity machinery would keep it *correct*, but nothing needs it |

## Cloud-provider support (added 2026-08-29, operator-directed)

**Every major cloud LLM provider is usable as OC's embedding provider
today, through one mechanism** — no per-provider adapters. The
`openai` adapter is the generic OpenAI-compatible client:
`OPENAI_BASE_URL` (already a Portainer-overridable compose var) points
it at any `/v1/embeddings` host, the provider's key goes in
`OC_EMBEDDING_API_KEY`, its model name in `OC_EMBEDDING_MODEL`. The
endpoint is part of the embedding-space fingerprint (ADR 0005), so
vectors from different hosts can never silently mix and any switch
triggers the standard reindex.

| Provider | Path | Notes (verify URLs/compat at switch time) |
|---|---|---|
| OpenAI | native (current) | — |
| **Anthropic** | **no embeddings API exists** | Verified 2026-08-29 against Anthropic's own docs: "Anthropic does not offer its own embedding model" — it recommends Voyage AI. Watched in the quarterly sweep in case a first-party API ships |
| Voyage AI | **blocked on the compat path today** | Live 400 (2026-08-29 benchmark): "Argument 'dimensions' is not supported" — our openai adapter always sends it. Needs the dimensions-optional adapter change AND (for full quality) the `input_type` dedicated adapter; both trigger-gated on actually choosing Voyage |
| Google Gemini | `.../v1beta/openai` compat endpoint | `gemini-embedding-001` family |
| Mistral | **blocked on the compat path today** | Live 422 (2026-08-29 benchmark): `extra_forbidden` on `dimensions` — strict schema rejects the param our adapter always sends. Same dimensions-optional fix would unblock it |
| Cohere | `https://api.cohere.ai/compatibility/v1` | `embed-v4.0`; endpoint accepted our requests but the trial key's 100 calls/min 429'd the backfill — needs a production key or throttling to benchmark |
| Together / Fireworks / DeepInfra / etc. | their OpenAI-compat base URLs | Host the open models (`qwen3-embedding`, `bge-m3`, ...) as cloud endpoints |
| Azure OpenAI | needs auth-path check | Deployment-scoped URLs + `api-key` header differ from the Bearer scheme; verify before promising |
| Ollama Cloud / Atlas Cloud | watched (zero embedding models) | Sweep legs above |

Every cloud provider here shares OpenAI's privacy posture (content
leaves the LAN) and the same benchmark gate. The matrix exists so
"can we use X?" is a lookup, not a project.

**Egress notice (shipped 2026-08-29, rev 141):** choosing any of these
is warned at startup — a WARNING log naming the remote endpoint and
the consequence, plus `content_egress: "remote"` in health — so cloud
embedding is always a made choice. The operator's accompanying
priority statement is recorded here as standing direction: **the
notice does not discharge the duty to secure embedding activity;
locking down internal (LAN-local Ollama) embedding remains the
priority path.** That sharpens reopen-trigger (a) below: the local
option is not merely a challenger, it is the stated destination
pending the benchmark.

## Recommendation

**Superseded 2026-08-29 by the benchmark results above.** The original
recommendation (stay on 3-small; build the benchmark; reopen on a
benchmark showing a local model within tolerance) executed exactly as
written: the benchmark was built, run, and its reopen-trigger fired —
`nomic-embed-text` is at parity with the best cloud models on this
corpus while closing the privacy asymmetry the operator has named the
priority path.

**Current recommendation: switch to LAN-local Ollama
`nomic-embed-text`, gated only on the NAS latency leg** (pull the
model on the NAS, measure query latency + reindex on its CPU — the
one number this benchmark could not produce). The switch itself is
stack-env config + one backfill; ADR 0005 makes it safe by
construction. The decision is the operator's.

Bookkeeping: the quarterly sweep below continues unchanged; the fleet
NAS rules' MoE caveat was re-confirmed by `nomic-embed-text-v2-moe`'s
disqualification.

## Gold-set benchmark results (2026-08-29)

The 0003 gold-set benchmark was built and run
(`scripts/benchmark_embeddings.py`): 868-memory real-corpus fixture
(full NAS snapshot), 40 authored paraphrase queries with one
known-relevant target each (fixtures untracked under
`data/embedding_benchmark/` — they contain private memory content),
scored through the REAL pipeline (`EmbeddingService.search_semantic` /
`search_hybrid`, RRF included) per candidate in a throwaway store.
Measurement config `include_pinned=True, pinned_limit=0` — both pin
defaults are policy, not relevance, and each silently broke a run
before this was understood (the second failure is now a V3_PLAN
punch-list item: the pin-float can consume the entire response on a
pin-heavy corpus).

Semantic-only recall/MRR, sorted; hybrid shown for the production mode.
`fails` = rows rejected under `truncate:false` (context-window honesty
— those rows stay FTS5-only). Latency measured on the authoring
machine, NOT the NAS; accuracy is the gate.

| Candidate | sem R@1 | sem R@10 | sem MRR | hyb R@1 | hyb R@10 | fails | reindex |
|---|---|---|---|---|---|---|---|
| **ollama/nomic-embed-text** (adapter default!) | **0.950** | **1.000** | **0.959** | 0.750 | 1.000 | 9 | 142s |
| openai/text-embedding-3-large | 0.925 | 0.975 | 0.946 | 0.700 | 0.975 | 1 | 25s |
| gemini/gemini-embedding-001 | 0.900 | 0.975 | 0.924 | 0.700 | 1.000 | 0 | 13s |
| ollama/bge-m3 | 0.875 | 1.000 | 0.923 | 0.725 | 1.000 | 19 | 338s |
| ollama/embeddinggemma | 0.850 | 1.000 | 0.908 | 0.725 | 1.000 | 13 | 156s |
| openai/text-embedding-3-small (incumbent) | 0.825 | 1.000 | 0.888 | 0.700 | 1.000 | 1 | 25s |
| ollama/snowflake-arctic-embed2 | 0.775 | 0.975 | 0.859 | 0.750 | 1.000 | 19 | 341s |
| ollama/qwen3-embedding:8b | 0.750 | 1.000 | 0.859 | 0.775 | 1.000 | 0 | 1673s |
| ollama/qwen3-embedding:4b | 0.675 | 0.950 | 0.784 | 0.700 | 0.975 | 0 | 311s |
| ollama/qwen3-embedding:0.6b | 0.625 | 0.850 | 0.718 | 0.700 | 0.975 | 0 | 82s |
| ollama/mxbai-embed-large | 0.550 | 0.550 | 0.550 | 0.425 | 0.875 | **353** | 342s |
| ollama/nomic-embed-text-v2-moe | 0.500 | 0.500 | 0.500 | 0.375 | 0.900 | **383** | 435s |
| fts5-only (baseline) | — | — | — | 0.600 | 0.850 | — | — |

**Findings:**

1. **`nomic-embed-text` — the adapter default — tops the table**,
   at/above parity with every cloud model including 3-large (its 0.025
   edge is one query on n=40: treat as parity, not victory). The 0006
   reopen-trigger "a benchmark showing a local model within tolerance
   on the gold set" is UNAMBIGUOUSLY met — by the smallest (274 MB),
   fastest-reindexing strong candidate, which also closes the privacy
   asymmetry outright. `bge-m3` and `embeddinggemma` also clear the
   incumbent.
2. **The incumbent ranks mid-table** (0.825) — nothing is broken, but
   staying on it is no longer defensible on quality grounds.
3. **Small-context models are disqualified by the long-input leg:**
   `mxbai-embed-large` (353 fails) and `nomic-v2-moe` (383) can't hold
   this corpus under `truncate:false` — the MoE model re-confirms the
   fleet's measured CPU-MoE caveat. The qwen3 family (32k ctx, 0
   fails) underperforms far smaller models here and 8b's 28-minute
   reindex buys nothing.
4. **Hybrid R@1 < semantic R@1 for every strong model** (e.g. nomic
   0.750 vs 0.950): RRF's keyword channel dilutes an excellent
   semantic top-1 on paraphrase queries, though hybrid keeps R@10 at
   1.000. Worth a follow-up look at RRF weighting someday; not part of
   the provider decision.
5. **Cloud-compat matrix corrections** (live errors, not docs):
   Mistral (`extra_forbidden`) and Voyage ("not supported") both
   REJECT the `dimensions` param the openai adapter always sends — the
   generic path does NOT work for them today (the fleet's
   strict-upstream lesson, verbatim: build bodies by adding only
   supplied fields). Cohere trial keys cap at 100 calls/min and 429'd
   the backfill. All three rows updated below.

**Caveats:** n=40, single-target gold, queries authored by one person
against sampled memories — differences under ~0.05 are one query and
must not be over-read. The relative tiers (nomic/3-large/gemini at
top; incumbent mid; small-context models out) are robust.

**NAS latency leg (RUN 2026-08-29, same day):** `nomic-embed-text`
pulled on the NAS Ollama and timed through the real adapter with real
corpus content:

| Path | NAS (CPU) | Incumbent (OpenAI) |
|---|---|---|
| Query embed, warm | **396 ms** mean / 428 ms p95 | ~213 ms |
| Query embed, cold (model unloaded) | 2.2 s | — |
| Batch of 32 memories | ~40 s | — |
| Full 868-row reindex (extrapolated) | **~19-25 min** | 25 s |

The NAS Ollama already runs the fleet-recommended env
(`OLLAMA_KEEP_ALIVE=24h`, `MAX_LOADED_MODELS=3`, `NUM_PARALLEL=1`), so
steady state is the warm path — the cold 2.2 s applies only after a
container restart or model eviction. **Verdict: livable.** Every
semantic search pays ~+180 ms over the incumbent (sub-second
end-to-end); the reindex cost is rare, background, and degrades to
FTS5-only rather than downtime; ongoing per-save embedding is well
under a second. The quality gate and the latency gate are both
cleared — the switch (stack env `OC_EMBEDDING_PROVIDER=ollama` +
`OLLAMA_HOST=http://host.docker.internal:11434` +
`OC_EMBEDDING_MODEL=nomic-embed-text`, then
`oc maintenance run-once embedding_backfill`) awaits the operator's
go. ADR 0005 makes it safe by construction.

## Recurring cadence — the quarterly embedding-provider sweep

**Operator-directed (2026-08-29): evaluating new Ollama models for the
embedding provider is a standing quarterly practice, not a one-off.**
It runs with the quarterly items in the phase-end audit (the AGENTS.md
project checklist carries the line) and absorbs the previously separate
Ollama Cloud re-check so there is one clock, not two.

The sweep, in order — each step is a diff against a recorded baseline,
never a re-derivation:

1. **Ollama library**: fetch <https://ollama.com/search?c=embedding>
   and diff against the baseline below. A new family or a new
   variant/size of a shortlisted family is a candidate.
2. **Ollama Cloud**: the V3_PLAN re-check (baseline 2026-08-28: 19
   hosted models, zero with `embedding` capability). The moment it
   lists one, it becomes an immediately usable provider — with the same
   benchmark gate and the same privacy posture as OpenAI.
3. **Anthropic**: baseline 2026-08-29 — no first-party embeddings API
   exists ("Anthropic does not offer its own embedding model"; it
   recommends Voyage AI, already in the cloud matrix below). One doc
   check per quarter in case that changes.
4. **Atlas Cloud** (fleet subscription, `atlascloud-mcp`): baseline
   2026-08-29 — the full Text catalog is 65 models, all
   chat/completion LLMs (plus OCR), **zero embedding models**. Checked
   because the operator raised it; kept on this clock because adoption
   would be near-free if that changes: OC's OpenAI adapter already
   honors `OPENAI_BASE_URL`, so an OpenAI-compatible `/v1/embeddings`
   endpoint there would be a config-only switch — inheriting, as
   always, the benchmark gate and the cloud privacy posture. One
   `atlas_list_models(query="embedding")` call per quarter.
5. **Candidates found**: pull locally, run the gold-set benchmark
   (until that benchmark exists, record the candidate here with a date
   and hold — a model nobody measured is not a switch argument), and
   update this document's baseline either way.
6. **Reopen the provider decision** only on this review's named
   triggers or a benchmark result within tolerance of the incumbent.

**Ollama library baseline (2026-08-29), 12 families:**
`qwen3-embedding` (0.6b/4b/8b) · `embeddinggemma` (300m) ·
`nomic-embed-text` · `nomic-embed-text-v2-moe` · `mxbai-embed-large`
(335m) · `bge-m3` (567m) · `bge-large` (335m) · `all-minilm`
(22m/33m) · `snowflake-arctic-embed` (5 sizes) ·
`snowflake-arctic-embed2` (568m) · `paraphrase-multilingual` (278m) ·
`granite-embedding` (30m/278m).

**Local test pool (pulled and live-verified 2026-08-29, measured
native dims):** `qwen3-embedding:0.6b` (1024d) · `qwen3-embedding:4b`
(2560d) · `qwen3-embedding:8b` (4096d — accuracy ceiling; note the
query-time search embedding also pays its latency, not just backfill)
· `embeddinggemma` (768d) · `nomic-embed-text` (768d, the adapter
default/baseline) · `mxbai-embed-large` (1024d) · `bge-m3` (1024d) ·
`snowflake-arctic-embed2` (1024d) · `nomic-embed-text-v2-moe` (768d —
carries the fleet's measured CPU-MoE-underdelivery caveat and must
prove itself). Excluded as superseded or too weak: `all-minilm`,
`bge-large`, `snowflake-arctic-embed` v1, `paraphrase-multilingual`,
`granite-embedding`.

The sweep's cost when nothing changed is minutes; its value is that a
strong new local model — the kind that flips this review's
recommendation — is noticed within a quarter instead of by accident.
