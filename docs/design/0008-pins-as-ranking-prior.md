# ADR 0008 — Pins as a Ranking Prior

**Status:** PROPOSED (rev 3 — rev 1 failed adversarial review, rev 2's
mechanism survived it with amendments; see Review history) ·
**Date:** 2026-08-29 · **Supersedes:** the pin-float mechanism in BOTH
its implementations (the hybrid/semantic float in `EmbeddingService`
and the keyword-mode float in `search_memory.execute`) · **Direction
ratified** by the operator 2026-08-29 (V3_PLAN active queue item 1;
OC memory `141393b7`).

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
deployments). Any redesign must cover both.

### Explicitly out of scope: the hybrid-R@1 deficit

The 0006 benchmark also showed hybrid R@1 (0.750) trailing
semantic-only R@1 (0.950). Review proved this **structurally
unfixable inside RRF**: the paraphrase failure case is a target at
semantic #1 absent from the keyword list, and a competitor at
semantic #2 + keyword #1 wins whenever `W_KEYWORD > ~0.016` — far
below any useful weight, while going under collapses hybrid into
semantic-only. RRF's rank compression discards semantic confidence by
construction. Fixing it means score-aware fusion — a different,
larger design recorded as a candidate future ADR. This ADR changes
pin policy only.

## Decision (proposed)

### 1. The prior lives in the RANK domain: a bounded, clamped lift

Rev 1's multiplicative score boost is dead (no gate in semantic mode;
all-pin pages on RRF's compressed scores at its own grid values).
Instead, wherever a pinned row appears in a channel's ranked
candidate list, its rank improves by a bounded number of positions
before fusion/cut:

```text
effective_lift            = min(PIN_RANK_LIFT, effective_top_k)      # per request
effective_rank(m, ch)     = max(1, rank(m, ch) − effective_lift)     # if m.pinned
                            rank(m, ch)                              # otherwise
```

- **Clamped, never asserted.** The lift's reach is capped per request
  by the request's own `effective_top_k` — a small `top_k` shrinks
  the lift instead of tripping an assertion (rev 2's
  `PIN_RANK_LIFT < K_WINDOW/2` assert was over a caller-controlled
  quantity and its own sweep grid violated it at default `top_k`;
  a caller-triggerable 500 is not an invariant).
- **Deterministic total order.** The clamp *guarantees* effective-
  rank collisions (every lifted pin collides with the row holding its
  target rank; multiple pins can pile on the `max(1, ·)` floor).
  Ordering is therefore defined as the tuple
  **(effective rank, original rank, memory id)** — ascending, total,
  stable across requests. Consequences of this tie-break, stated
  plainly: a lifted pin *ties* do not let it pass the row already AT
  its target rank (original rank breaks the tie in that row's favor)
  — the lift lets a pin pass the rows *between*, which is the
  intended semantics ("gains up to `effective_lift` positions") and
  makes `offset` pagination well-defined.
- **The gate, stated honestly.** A pin benefits only where it appears
  in a channel's candidate list. For the keyword channel that is a
  real relevance gate (FTS5 match required). For the semantic channel
  every embedded row has *some* cosine, so the gate there is depth,
  not absence: a near-noise pin sits at a deep rank and a bounded
  lift cannot surface it through a populated page — but on a sparse
  result set (fewer genuine matches than `top_k`) low-similarity rows
  including pins can fill the bottom of the page, exactly as they can
  today with `include_pinned=True`. The mechanism adds no new
  exposure; it does not claim an absolute gate (rev 2 overclaimed).
- **Score domains untouched.** RRF fuses lifted ranks with the
  unchanged formula and `K = 60`; `rrf_score` keeps its documented
  ~2/61 ceiling; `semantic_similarity` stays raw. In semantic mode
  the result order may therefore disagree with the
  `semantic_similarity` fields the caller sees — the row's `pinned`
  flag is the explanation, and the docs updated by this ADR say so
  (rev 2 dispositioned this only for `rrf_score`).
- **One mechanism for every mode.** Ranks exist in the keyword list,
  the semantic ranking, the keyword-only path, and the degraded
  fallback — the SAME clamped lift and the SAME tie-break apply in
  all of them. Keyword-only/degraded deployments keep pin
  preference, relevance-gated instead of float-shaped.

### 2. The candidate window extends by the lift's reach (no quota)

Rev 2 proposed an additive "pinned quota at true full-ranking rank."
Review killed it from two directions: the keyword channel cannot
produce a pin's true full-ranking rank without an unbounded per-query
sort (a pinned-only predicate yields rank-*within-pins*, a different
number), and any quota row deeper than `window + lift` is dead weight
that RRF's monotonicity can never surface. The mechanically
equivalent cheap design replaces it:

```text
channel fetch = top (2 × effective_top_k + effective_lift)   # was 2 × effective_top_k
```

Every pin the lift could possibly surface is inside the widened
fetch by construction; every rank the lift operates on is an honest
rank from the fetch itself; no new port surface exists
(`search_pinned` dies with nothing replacing it — the ordinary
ranked query with `include_pinned=True` is the one primitive).
Pins deeper than the widened window remain unreachable — that is the
aging argument working: relevance ordering, not arrival order or cap
luck, decides which pins compete.

### 3. Tuning against the upgraded harness

- **Fixture upgrades first:** pinned-target flags stored per gold
  query; pinned-target queries expanded to ≥20; a ~10-query
  broad-query fixture for the pin-crowding probe with numeric gates
  (mean pins-in-top-10 ≤ 5, max ≤ 8).
- **Harness upgrades first:** embed once per store, re-score all
  sweep cells against the same vectors; `PIN_RANK_LIFT` injected via
  the `EmbeddingService` constructor (production wiring passes the
  named module default — the constant is deliberately code-only, no
  env var / `core.json` key: retuning is a code change by design,
  per the no-over-engineering rule); the harness's `pinned_limit=0`
  special case is deleted.
- **Sweep:** `PIN_RANK_LIFT ∈ {0, 2, 4, 8}` (all cells valid under
  the clamp at the benchmark's `top_k=10`; rev 2's `10` cell
  violated its own bound at default `top_k`). `LIFT = 0` (lift off;
  float still removed) is an admissible outcome and the test plan
  survives it. The quota dimension is gone with the quota.
- **Held-out validation is a regression veto, not a confirmation
  bar:** queries split ~60/40 tune/validate; the winning cell is
  REJECTED if its validated delta is negative; at the fixture's size
  (~8 validation pinned queries, R@1 granularity 0.125) a
  confirmation requirement would be noise-decided, so none is
  imposed — deltas under one query's granularity are reported as
  noise either way.

### 4. Surface contract

- `include_pinned` keeps its exact meaning in every mode (`False`
  hides pins entirely) — visibility policy, orthogonal to ranking.
- `channel` keeps reporting the producing ranked channel; the
  `"pinned"` value stops occurring in ALL modes (the
  documented-behavior change that drives versioning).
- `pinned_limit` becomes inert on every wire surface (MCP tool, REST
  query param, CLI flag): accepted, marked deprecated (FastAPI
  `deprecated=True` so the OpenAPI spec says so per STABILITY step 2;
  its `ge/le` range validation is dropped along with the meaning it
  validated), removed **no earlier than v5.0.0**.
- Internal signatures (`EmbeddingService.search_*`,
  `search_memory.execute`) drop `pinned_limit` outright; internal
  callers (CLI plumbing, `scripts/benchmark_embeddings.py`) are
  updated in the same change — they are not under STABILITY.
- `MemoryStorePort.search_pinned` loses ALL callers (both float
  sites die) and is removed (port + store + tests). Nothing replaces
  it.
- **Documentation inventory** (checklist for the implementation
  stage, since the schema snapshot does not catch docstring drift):
  `mcp_server_spec.md` (channel enum, float paragraphs),
  `docs/cli/commands.md` (relevance/channel column text),
  `scored_memory.py` docstring (documents the `pinned` channel
  value), `interfaces/serializers.py` relevance commentary, the
  MCP/REST/CLI docstrings and flag help, `memory_store_port.py`
  float commentary and `DEFAULT_PINNED_LIMIT`, and the
  `sqlite_store.py` include/exclude tristate comments. Grep `pinned`
  across `docs/` and docstrings is the exit check.

### 5. Versioning — OPEN QUESTION for the operator

Request/response *schemas* are unchanged; documented *behavior*
changes (pins stop leading; a documented `channel` enum value ceases
to occur; a documented parameter goes inert). Under STABILITY.md's
"changing the meaning of an existing field" this is **MAJOR →
recommend v4.0.0**. On the deprecation window, stated honestly this
time: STABILITY's window text attaches to MAJOR changes wholesale and
says "keep the old shape working." This ADR keeps the old *syntax*
working (the accepted-inert parameter, through v4.x) but the old
*behavior* (pins leading the page) ends at v4.0.0 with no parallel
surface — **a deliberate deviation from the policy's letter**,
justified by proportionality: a parallel `/api/v2` deployment to
preserve a float for an audience of zero external users is ceremony
without a beneficiary. The operator accepting §5 accepts that
deviation explicitly. The alternative — calling this MINOR — remains
rejected: quiet reinterpretation is how stability promises rot.

## Consequences

- **The lift adds no all-pin failure mode** — bounded per pin, tied
  conservatively, capped by the request's own size. Stated precisely
  (rev 2 overclaimed "can never return an all-pin page"): a page can
  still be pin-heavy when the *unlifted* ranking honestly is — 149
  pins genuinely outranking everything is relevance deciding, and no
  ranking policy should hide it. What can no longer happen is
  policy *manufacturing* that page, which is the defect this ADR
  kills.
- A relevant pin passes up to `effective_lift` near-equal unpinned
  competitors in every mode, at any pin population; rows it merely
  ties (the row at its target rank) keep their place.
- Degraded and keyword-only deployments keep pin preference via the
  same mechanism.
- One ranking-policy mechanism total (down from two float
  implementations + one exclusion-set protocol); the benchmark
  measures production behavior with no special configuration.
- Costs accepted: `PIN_RANK_LIFT` is a global, code-only constant
  (retuning is a release); result order is no longer derivable from
  the raw per-channel signals alone (the lift intervenes; the
  `pinned` flag explains it, and semantic mode's order may visibly
  disagree with its `semantic_similarity` fields — documented).

## Test plan

- **Bounded-lift + tie-break properties** (deterministic, injected
  constants; equality-of-score assertions stay banned): a pin gains
  at most `effective_lift` positions per channel; a pin lifted onto
  an occupied rank sorts AFTER the original-rank holder; pile-ups at
  the rank-1 floor order by original rank then id.
- **Clamp:** `top_k=1` and `top_k=2` requests succeed with the lift
  clamped, never erroring.
- **Keyword-gate:** a pin with no FTS5 match never surfaces in
  keyword mode / the keyword channel.
- **Semantic exposure parity:** on a sparse result set, a
  low-similarity pin appears no earlier than it would today with
  `include_pinned=True` and no float (the mechanism adds no new
  exposure).
- **Mode parity:** keyword mode and degraded-hybrid apply the same
  lift and tie-break as the fused path.
- **Window extension:** a pin at unlifted rank `2×top_k + lift` (the
  last fetched row) can surface; one rank deeper cannot.
- **`include_pinned=False`** hides pins in all three modes.
- **Pagination:** two consecutive `offset` pages neither duplicate
  nor drop rows (now satisfiable — the total order is defined).
- **Inert-param compat:** `pinned_limit` accepted on MCP/REST/CLI and
  ignored; OpenAPI marks it deprecated.
- Tuning gates live in the harness: unpinned non-regression,
  pinned-target improvement, crowding gate, held-out regression veto.
- Schema snapshot + the §4 documentation checklist land with the
  surface change.

## Rollout

1. Operator decision on this rev (mechanism reviewed twice; the
   rev-2→3 amendments follow the critics' own prescriptions).
2. Harness + fixture upgrades (§3) — landable independently.
3. Implement lift + window extension with `PIN_RANK_LIFT=0`
   injected. **At LIFT=0 the window extension adds zero rows and no
   rank moves — the ranked stream is identical to today's
   `pinned_limit=0` behavior by construction** (a real equivalence
   this time: rev 2's version was falsified by its own always-on
   quota). The float removal itself is the deliberate, versioned
   behavior change at defaults — enumerated in the CHANGELOG.
4. Tuning run per §3; land the winning constant; record the cell
   here.
5. Version bump per the operator's §5 answer; ships with the next
   tag; no reindex (ranking-only).

## Review history

- **Rev 1 (2026-08-29): FAILED adversarial review** (three critics —
  ranking-math, API-contract, implementation). Sustained: the
  multiplicative score boost had no gate in semantic mode and
  permitted all-pin pages on RRF's compressed scores at its own grid
  values; the keyword-mode float in `search_memory.execute` was
  unaccounted for; weighted RRF was mathematically incapable of
  fixing the hybrid-R@1 deficit it cited (`W_KEYWORD` threshold
  ≈ 0.016); the candidate window recreated the pin lottery; the
  "byte-equivalent" rollout claim was unfalsifiable; the tuning plan
  overfit n=40 with no held-out set; degraded mode silently lost its
  float; §5 misdescribed its own deprecation mechanics.
- **Rev 2 (2026-08-29): mechanism SURVIVED re-review; amendments
  required** (same three critics, rev-1 findings verdicted
  individually — all resolved or partially resolved). Sustained
  against rev 2 and fixed in rev 3: the pinned quota was
  unimplementable as specified (keyword-channel "true rank" needs an
  unbounded per-query sort; a pinned-only predicate yields
  rank-within-pins; deep quota rows were dead weight) → replaced by
  the lift-reach window extension both critics prescribed; the
  LIFT=0 equivalence claim was falsified by the always-on quota →
  now a construction-level identity; the `K_WINDOW/2` assert was
  over a caller-controlled quantity and the sweep's own LIFT=10 cell
  violated it → per-request clamp, grid rebased to {0,2,4,8}; lifted
  ranks collided with no tie-break, leaving ordering and pagination
  undefined → total order (effective rank, original rank, id); "can
  never return an all-pin page" and the "real gate" were overclaims →
  restated precisely (no *added* failure mode; keyword gate absolute,
  semantic gate is depth); §5 misattributed a schema-break carve-out
  to STABILITY → the deviation is now owned explicitly; held-out
  gate at ~8 validation queries was noise-decided → regression veto;
  plus doc-inventory additions (scored_memory, cli docs,
  serializers, OpenAPI `deprecated=True`), "no earlier than v5.0.0"
  removal date, and the code-only-constant decision made explicit.
