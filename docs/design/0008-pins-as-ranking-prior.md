# ADR 0008 — Pins as a Ranking Prior

**Status:** PROPOSED (rev 1, unreviewed) · **Date:** 2026-08-29 ·
**Supersedes:** the pin-float mechanism (rev 123's floated-pins-lead-
the-stream shape and `search_pinned`'s float role) · **Direction
ratified** by the operator 2026-08-29 (V3_PLAN active queue item 1;
OC memory `141393b7`); this ADR is the design that ratification asked
for.

## Problem

Two defects, one fusion layer, both found by the gold-set benchmark
(design 0006) on the live corpus:

1. **The pin-float can consume the entire response.**
   `DEFAULT_PINNED_LIMIT` (10) equals the default `top_k` (10), and
   floated pins lead the single `top_k`-bounded stream — so on a
   149-pin corpus, any broad query keyword-matching ≥10 pins returns
   ONLY pins. Twelve different embedding models scored byte-identically
   in the benchmark because every top-10 was the same pin set. A
   smaller cap was rejected: pins only accumulate, so any fixed cap
   decays into an FTS5-rank lottery among pins — keyword-gated,
   never aging, blind to the semantic channel.
2. **Unweighted RRF dilutes an excellent semantic top-1.** Hybrid
   R@1 trailed semantic-only R@1 for every strong model
   (`nomic-embed-text`: 0.750 hybrid vs 0.950 semantic) while hybrid
   kept R@10 at 1.000 — the keyword channel's vote drags a confident
   semantic #1 down without adding recall at the top.

Both are properties of how ranked lists are combined, so they are one
ADR: pinned-ness becomes a *prior* inside the fusion instead of a
bypass around it, and the fusion gains per-channel weights.

## Decision (proposed)

### 1. Retire the float; boost pins multiplicatively inside ranking

The float block in `search_hybrid`/`search_semantic` (the
`search_pinned` call, the `channel="pinned"` prepend, the exclusion
set) is removed. Pins enter the ranked channels like every other row
(they already can — `include_pinned=True` reaches them in both
channels since 2026-08-23). After fusion, each result's score is
multiplied by a pin boost when its item is pinned:

```text
final_score(m) = fused_score(m) × (PIN_BOOST if m.pinned else 1.0)
```

**Multiplicative, not additive, is load-bearing:** a pin that matches
nothing scores zero and stays invisible — relevance always gates,
which is the entire point. An additive bonus would resurrect the
float's failure mode (irrelevant pins surfacing on policy alone).

Applied per mode:

- `search_hybrid`: on the RRF fused score, before the top-k cut.
- `search_semantic`: on cosine similarity, before the top-k cut
  (scores may exceed 1.0 — they order results, they are not
  probabilities; the response's per-channel signals stay raw).
- Keyword-only / degraded paths: **no boost.** The FTS5 store path
  returns rank order without comparable scores; nudging ranks by
  position is a different (worse) mechanism. Degraded mode is
  degraded — documented, not compensated.

### 2. Weighted RRF

```text
fused_score(m) = W_SEMANTIC / (K + rank_sem(m)) + W_KEYWORD / (K + rank_kw(m))
```

with `K = 60` unchanged. Starting hypothesis from the benchmark:
`W_SEMANTIC > W_KEYWORD` (e.g. 1.0 / 0.5). The keyword channel's
value is recall insurance (exact identifiers, rare tokens) — it
should break ties and rescue misses, not outvote a confident
semantic ranking.

### 3. Both constants are tuned, not guessed

The gold-set benchmark is the instrument. The tuning run sweeps
`PIN_BOOST ∈ {1.0, 1.1, 1.25, 1.5, 2.0}` ×
`(W_SEMANTIC, W_KEYWORD) ∈ {(1,1), (1,0.5), (1,0.25)}` and reports,
per cell:

- hybrid R@1 / MRR on the 30 unpinned-target queries
  (**non-regression gate**: must not drop vs today's `(1,1)` +
  no-boost baseline);
- hybrid R@1 / MRR on the 10 pinned-target queries (the improvement
  this ADR exists to buy);
- a **pin-crowding probe**: for a set of broad queries, the count of
  pins in the top-10 (today: can be 10/10; the boost must not
  recreate that).

`PIN_BOOST = 1.0` disabling the mechanism entirely is a valid tuning
outcome; the constants land in code as named module constants with
the winning cell recorded here.

### 4. Surface contract

- `include_pinned` keeps its exact meaning (`False` hides pins from
  results entirely) — it is visibility policy, orthogonal to ranking.
- `channel` keeps reporting the producing ranked channel; the
  `"pinned"` value simply stops occurring (the field's type and
  meaning are unchanged; consumers were already required to tolerate
  its other values).
- `pinned_limit` becomes a **no-op**: accepted, documented as
  deprecated, removed at the next MAJOR. It has no coherent meaning
  without a float.
- `MemoryStorePort.search_pinned` loses its only production caller.
  Per the dead-code rule it is REMOVED (port + store + tests) rather
  than kept "just in case" — `search_memory` with
  `include_pinned=True` already reaches pins.
- Response objects gain nothing; `rrf_score` now carries the
  weighted+boosted value (same field, same "fused relevance score"
  meaning, different formula — formula was never part of the
  contract).

### 5. Versioning (OPEN QUESTION for the operator)

By `docs/api/STABILITY.md`'s letter, `pinned_limit` changing from
"cap on floated pins" to no-op is *changing the meaning of an
existing field* → MAJOR. Three honest options:

- **(a) v4.0.0, deprecation window waived** (recommended): zero
  external users exist; the parallel-`/api/v2` machinery would be
  ceremony. The MAJOR number honestly signals "response composition
  changed"; CHANGELOG carries the migration note (one parameter went
  inert).
- (b) v4.0.0 with the full documented window — maximal fidelity to
  STABILITY.md, real ongoing cost (two shapes in one image) for an
  audience of zero.
- (c) Call it MINOR ("behavioral tuning") — rejected here: it
  contradicts the policy this repo deliberately adopted, and quiet
  reinterpretations are how stability promises rot.

## Consequences

- Pin visibility becomes proportional to relevance everywhere; a
  broad query can never return an all-pin page again, and a pinned
  standing rule surfaces for exactly the queries it's relevant to —
  at any pin population (the aging argument that killed the cap).
- Semantic-channel quality (now excellent: 0.95 R@1 on the incumbent
  local model) is no longer capped by an unweighted keyword vote.
- One fewer port method, one fewer policy layer, one fewer response
  channel value; the benchmark harness measures production behavior
  with NO special configuration (today it must disable the float to
  measure ranking at all — the two harness incidents that found
  these defects).
- Risk: a single global `PIN_BOOST` may fit this corpus and not a
  future one. Accepted: the constant is one line, the benchmark is
  rerunnable, and per-corpus tunables are premature machinery today.

## Test plan (beyond the tuning run)

- Zero-relevance pin never surfaces (multiplicative gate).
- Deterministic construct: pinned row outranks an identically-scored
  unpinned row; unpinned rows keep relative order (boost is
  monotonic within each class).
- `include_pinned=False` hides pins in every mode (existing tests
  keep passing).
- `pinned_limit` accepted and inert (compat test until MAJOR
  removal).
- Weighted-RRF unit test with hand-computed fused scores.
- Schema snapshot + `mcp_server_spec.md` + STABILITY-relevant docs
  updated together.

## Rollout

1. ADR review (adversarial pass, per house practice) → ACCEPTED rev.
2. Implement behind the current default constants
   (`PIN_BOOST = 1.0`, `W = (1,1)`) — pure refactor first, benchmark
   confirms byte-equivalent-except-float ranking.
3. Tuning run; land the winning constants + record them here.
4. Version bump per the operator's answer to §5; deploy rides the
   next tag; no reindex needed (ranking-only — vectors untouched).
