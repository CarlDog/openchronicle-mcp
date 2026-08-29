# Embedding Provider Review

**Status:** Review complete — recommendation recorded, no switch made;
the benchmark is the named gate for any change · **Date:** 2026-08-29

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
| Voyage AI | `OPENAI_BASE_URL=https://api.voyageai.com/v1` | Anthropic's recommended vendor; wire format verified OpenAI-shaped. Caveat: Voyage's `input_type` query/document prompts aren't expressible on the compat path — full quality needs a dedicated adapter (trigger-gated on actually choosing Voyage) |
| Google Gemini | `.../v1beta/openai` compat endpoint | `gemini-embedding-001` family |
| Mistral | `https://api.mistral.ai/v1` | `mistral-embed` |
| Cohere | `https://api.cohere.ai/compatibility/v1` | `embed-v4` family |
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

1. **Stay on `text-embedding-3-small` today.** Nothing is broken, the
   cost is noise, and quality is proven-in-use.
2. **The one funded next step, if any: build the 0003 gold-set
   benchmark** (an offline script + fixture, not a service feature).
   It is the decision instrument for every future provider question —
   local models, 3-large, a future Ollama Cloud — and without it every
   switch argument is vibes.
3. **The trigger that reopens this review:** the operator deciding the
   privacy asymmetry now outweighs proven quality (a posture change,
   like the auth decision would be), OR a benchmark showing a local
   model within tolerance on the gold set, OR OpenAI API terms/pricing
   moving materially.
4. Bookkeeping: the quarterly Ollama Cloud re-check continues — as one
   leg of the recurring sweep below; the fleet NAS rules' MoE caveat
   does not apply to the small dense embedding models in play here.

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
