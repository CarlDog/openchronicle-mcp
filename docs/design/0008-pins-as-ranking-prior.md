# ADR 0008 — Pins as a Ranking Prior

**Status:** PROPOSED (rev 2 — rev 1 failed adversarial review, see
Review history) · **Date:** 2026-08-29 · **Supersedes:** the pin-float
mechanism in BOTH its implementations (the hybrid/semantic float in
`EmbeddingService` and the keyword-mode float in
`search_memory.execute`) · **Direction ratified** by the operator
2026-08-29 (V3_PLAN active queue item 1; OC memory `141393b7`).

## Problem

The pin-float can consume the entire search response.
`DEFAULT_PINNED_LIMIT` (10) equals the default `top_k` (10) and
floated pins lead the single `top_k`-bounded stream — on the live
149-pin corpus, a broad query keyword-matching ≥10 pins returns ONLY
pins (twelve embedding models scored byte-identically in the 0006
benchmark because every top-10 was the same pin set). A smaller cap
was rejected by the operator: pins only accumulate, so any fixed cap
decays into a keyword-rank lottery among pins that never ages and
never consults the semantic channel.

The float exists **twice**: in `search_hybrid`/`search_semantic`
(`EmbeddingService`) and, independently, in the keyword-mode branch of
`use_cases/search_memory.py` (which also serves keyword-only
deployments). Rev 1 missed the second site; any redesign must cover
both or it is not a redesign.

### Explicitly out of scope: the hybrid-R@1 deficit

The 0006 benchmark also showed hybrid R@1 (0.750) trailing
semantic-only R@1 (0.950). Rev 1 proposed channel weights; review
showed that is **structurally unfixable inside RRF**: the paraphrase
failure case is a target at semantic #1 absent from the keyword list,
and a competitor at semantic #2 + keyword #1 wins whenever
`W_KEYWORD > ~0.016` — far below any useful weight, while going under
that threshold collapses hybrid into semantic-only. RRF's rank
compression discards semantic confidence by construction (a
0.95-vs-0.60 cosine gap becomes 1/61 vs 1/62). Fixing it means
score-aware fusion — a different, larger design with its own
normalization pitfalls. It is scoped OUT of this ADR and recorded as
a candidate future design; this ADR changes pin policy only.

## Decision (proposed)

### 1. The prior lives in the RANK domain, not the score domain

Rev 1's multiplicative score boost is dead — review proved it has no
gate in semantic mode (background cosine sits ~0.2-0.5, never zero,
so a 0.35-similarity pin × 2.0 beats a 0.65 relevant row) and
misbehaves catastrophically on RRF's rank-compressed scores (all
fused scores live in [2/(60+2k), 2/61]; at rev 1's own grid values a
pin ranked 16th in both channels outscored a double-#1, refilling the
all-pin page).

Instead: **a bounded rank lift.** Wherever a pinned row appears in a
channel's ranked candidate list, its rank is improved by a fixed
number of positions before fusion/cut:

```text
effective_rank(m, channel) = max(1, rank(m, channel) − PIN_RANK_LIFT)   if m.pinned
                             rank(m, channel)                            otherwise
```

Properties the review demanded and this form delivers:

- **A real gate.** A pin absent from a channel's candidate list gets
  nothing from that channel — presence in a ranked list is the
  relevance evidence. No background-similarity floor to exploit.
- **Bounded influence by construction.** A pin can pass at most
  `PIN_RANK_LIFT` competitors per channel — it can never leapfrog the
  whole page, so the all-pin failure mode is structurally excluded
  for any lift value materially smaller than `top_k`'s window
  (enforced: `PIN_RANK_LIFT < K_WINDOW / 2`, asserted in code).
- **Score domains untouched.** RRF fuses lifted ranks with the
  unchanged formula and `K = 60`; `rrf_score` keeps its documented
  ~2/61 ceiling, `semantic_similarity` stays raw. No response-field
  semantics change.
- **One mechanism for every mode.** Ranks exist in the keyword list,
  the semantic ranking, the keyword-only path, and the degraded
  fallback — the SAME lift applies in all of them. This resolves rev
  1's mode inconsistency (boost in two modes, nothing in the others)
  and the unnamed degraded-mode regression (degraded mode keeps pin
  preference, now relevance-gated instead of floated).

### 2. Pinned candidate quota at the window stage

Fusion only sees each channel's over-fetched candidate window
(~2×top_k, selected today without regard to pins). Review showed that
without a window story, 149 pins compete with everything else for
~20 slots and the lottery relocates rather than dies. Therefore: each
channel's candidate set becomes

```text
candidates(channel) = top_W unpinned-or-pinned as ranked   (the window, unchanged)
                    ∪ top_Q pinned rows of that channel    (the quota, additive)
```

with each quota row carrying its TRUE rank from the full channel
ranking (so the lift operates on honest ranks). The quota is additive
— it never displaces unpinned candidates — and small (`PIN_QUOTA`,
default 10). A pin outside both the window and the quota is genuinely
not relevant enough to surface; that is the aging argument working,
not failing: relevance ordering, not arrival order or cap luck,
decides which pins compete.

### 3. Both constants tuned against an upgraded harness — honestly

Review sustained that the rev 1 tuning plan was unexecutable
(per-cell full re-embeds, no pinned-target marker in the fixture, no
broad-query set, no threshold) and statistically dishonest (argmax on
the same 40 queries, granularity 0.10 on the pinned subset). Rev 2
schedules the instrument work FIRST:

- **Fixture upgrades:** pinned-target flags stored per gold query;
  the pinned-target query set expanded to ≥20; a new ~10-query
  broad-query fixture for the pin-crowding probe with a numeric gate
  (mean pins-in-top-10 ≤ 5, max ≤ 8 across the set).
- **Harness upgrades:** embed once per store, re-score all sweep
  cells against the same vectors (constants injected via
  `EmbeddingService` constructor parameters, landing as named module
  defaults); the `pinned_limit=0` measurement special-case is deleted
  (post-refactor the production config IS the measurable config —
  the property rev 1 claimed and didn't have).
- **Held-out validation:** queries split ~60/40 tune/validate; the
  winning cell must hold direction on the validation split, and
  deltas under one query's granularity are reported as noise, not
  wins (0006's own caveat, now binding on this tuning).
- **Sweep:** `PIN_RANK_LIFT ∈ {0, 2, 5, 10}` × `PIN_QUOTA ∈ {5, 10}`.
  `LIFT = 0` (mechanism off, float still removed) is an admissible
  outcome; the test plan below is written to survive it.

### 4. Surface contract

- `include_pinned` keeps its exact meaning in every mode (`False`
  hides pins from results entirely) — visibility policy, orthogonal
  to ranking.
- `channel` keeps reporting the producing ranked channel. The
  `"pinned"` value stops occurring in ALL modes — including keyword
  mode, whose float is replaced by the same rank lift (this is the
  documented-behavior change that drives versioning, below).
- `pinned_limit` becomes inert on every wire surface (MCP tool, REST
  query param, CLI flag): accepted, documented as deprecated, removed
  at the MAJOR after next. **The accepted-inert parameter IS the
  deprecation window** — rev 1's "waive the window" framing was
  wrong; no parallel surface is needed because no request/response
  schema changes.
- Internal signatures (`EmbeddingService.search_*`,
  `search_memory.execute`) drop `pinned_limit` outright — internal
  callers (CLI plumbing, `scripts/benchmark_embeddings.py`) are
  updated in the same change; they are not under STABILITY.
- `MemoryStorePort.search_pinned` now genuinely loses ALL callers
  (both float sites die) and is removed (port + store + tests). The
  quota fetch reuses `search_memory`'s ranked query with a
  pinned-only predicate — one ranking primitive, not two.
- Documentation inventory (review finding): the float is described in
  `mcp_server_spec.md` (channel enum, float paragraphs, `rrf_score`
  ceiling note stays valid), the MCP/REST/CLI docstrings,
  `memory_store_port.py` commentary, and the sqlite tristate
  comments. The implementation stage carries an explicit
  grep-`pinned`-docs checklist; "documented as deprecated" is a
  listed edit set, not an intention.

### 5. Versioning — OPEN QUESTION for the operator

The honest classification: request/response *schemas* are unchanged;
what changes is documented *behavior* (pins stop leading; a
documented `channel` enum value ceases to occur; a documented
parameter goes inert). By STABILITY.md that is still
"changing the meaning of an existing field" → **recommend v4.0.0**,
with the deprecation mechanics satisfied by the accepted-inert
parameter (§4) rather than a parallel `/api/v2` surface (which the
policy reserves for schema breaks). The alternative — calling it
MINOR as "behavioral tuning" — remains rejected: quiet
reinterpretation is how stability promises rot.

## Consequences

- A broad query can never return an all-pin page: the lift is bounded
  below the window size by construction, not by tuning luck.
- A relevant pin reliably outranks near-equal unpinned rows in every
  mode, at any pin population; an irrelevant pin (absent from the
  ranked channels) surfaces nowhere.
- Degraded and keyword-only deployments keep pin preference —
  relevance-gated, no longer float-shaped.
- One ranking-policy mechanism total (down from two float
  implementations + one exclusion-set protocol); the benchmark
  measures production behavior with no special configuration.
- Costs accepted: `PIN_RANK_LIFT`/`PIN_QUOTA` are global constants (a
  future corpus may want different values — rerun the tuning);
  `rrf_score` ordering is no longer derivable from raw channel ranks
  alone (the lift intervenes; the per-channel raw signals remain in
  the response).

## Test plan

- **Bounded-lift property:** a pinned row gains at most
  `PIN_RANK_LIFT` positions per channel (deterministic constructs
  with fixed injected constants — no identical-score assertions; the
  review showed RRF tie order is hash-iteration-dependent, so
  equality-based tests are banned here).
- **Gate:** a pin absent from both channels' candidates+quota never
  surfaces, in hybrid, semantic, and keyword modes.
- **Mode parity:** keyword mode and degraded-hybrid apply the same
  lift (regression guard on the rev-1 blind spot).
- **Quota:** a pin at true rank outside the window but inside the
  quota enters fusion with its true rank; unpinned candidates are
  never displaced by the quota.
- **`include_pinned=False`** hides pins in all three modes
  (semantic-mode guard explicitly retained when float tests die).
- **Pagination:** `offset` walks the lifted ordering consistently
  (a lift must not duplicate/skip rows across page boundaries).
- **Inert-param compat:** `pinned_limit` accepted on MCP/REST/CLI and
  ignored (until the scheduled MAJOR-after-next removal).
- Tuning-gate tests live in the harness, not pytest: non-regression
  on unpinned targets, pinned-target improvement, crowding gate,
  held-out confirmation.
- Schema snapshot + spec/docstring edits land in the same commit as
  the surface change (the snapshot does NOT catch docstring drift —
  review finding — hence the explicit checklist in §4).

## Rollout

1. Rev 2 adversarial re-review → ACCEPTED rev.
2. Harness + fixture upgrades (§3) — landable independently, useful
   regardless of tuning outcome.
3. Implement lift+quota with `PIN_RANK_LIFT=0` injected: at that
   setting the ranked stream is verifiably identical to today's
   `pinned_limit=0` behavior (the harness config that already exists
   proves it), while the float removal itself is the deliberate,
   versioned behavior change at defaults — enumerated in the
   CHANGELOG, never called "byte-equivalent" (rev 1's false claim).
4. Tuning run per §3; land winning constants; record the cell here.
5. Version bump per the operator's §5 answer; ships with the next
   tag; no reindex (ranking-only).

## Review history

- **Rev 1 (2026-08-29): FAILED adversarial review** (three critics —
  ranking-math, API-contract, implementation). Sustained: the
  multiplicative score boost had no gate in semantic mode and
  permitted all-pin pages on RRF's compressed scores at the proposed
  grid values; the keyword-mode float in `search_memory.execute` was
  entirely unaccounted for (falsifying the "only caller" /
  "no-op" / "stops occurring" claims); weighted RRF was
  mathematically incapable of fixing the hybrid-R@1 deficit it cited
  (`W_KEYWORD` threshold ≈ 0.016); the candidate window recreated the
  pin lottery; the "pure refactor / benchmark confirms
  byte-equivalence" rollout claim was unfalsifiable at the
  benchmark's `pinned_limit=0` config; the tuning plan overfit n=40
  with no held-out set and an unexecutable harness; degraded mode
  silently lost its float; §5 misdescribed its own deprecation
  mechanics. Rev 2 replaces the mechanism (rank-domain lift + quota),
  covers both float sites and all modes, scopes the fusion-quality
  question out, and schedules the instrument work before tuning.
