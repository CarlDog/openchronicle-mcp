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
| Dual/fallback providers | Rejected — a second active provider is a second vector space and a second failure surface; the FTS5 fallback already covers outages. The identity machinery would keep it *correct*, but nothing needs it |

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
4. Bookkeeping: the quarterly Ollama Cloud re-check continues; the
   fleet NAS rules' MoE caveat does not apply to the small dense
   embedding models in play here.
