# ADR 0008 — Pins as a Ranking Prior

**Status:** ACCEPTED (rev 4, operator, 2026-08-29 — including §5:
**v4.0.0**, with the deprecation-window deviation explicitly
accepted). Implementation proceeds on the **`v4/develop` branch**
(operator-directed): `main` stays the v3.x production line so fixes
ship to prod untangled from v4 work; `main` merges into `v4/develop`
regularly; CI runs test+quality on `v4/develop` but publishes images
only from `main`/tags. Exception: the §3 harness + fixture upgrades
are v3-compatible additive work and land on `main`. · **Date:**
2026-08-29 · **Supersedes:** the pin-float mechanism in BOTH its
implementations (the hybrid/semantic float in `EmbeddingService` and
the keyword-mode float in `search_memory.execute`) · **Direction
ratified** by the operator 2026-08-29 (V3_PLAN active queue item 1;
OC memory `141393b7`).

## Problem

The pin-float can consume the entire search response.
`DEFAULT_PINNED_LIMIT` (10) **exceeds** the default `top_k` (8 at
every production surface — service, use case, MCP, REST, CLI; rev 3's
"equals 10" was wrong, and the true relation is strictly worse), and
floated pins lead the single `top_k`-bounded stream — on the live
149-pin corpus, a broad query keyword-matching enough pins returns
ONLY pins (twelve embedding models scored byte-identically in the
0006 benchmark because every top-10 was the same pin set). A smaller
cap was rejected by the operator: pins only accumulate, so any fixed
cap decays into a keyword-rank lottery among pins that never ages and
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
semantic-only. Fixing it means score-aware fusion — recorded as a
candidate future ADR. This ADR changes pin ranking policy (and, as an
honestly-dispositioned side effect, candidate fetch depth — see §2).

## Definitions

- `top_k` — the caller's requested page size (default 8).
- `effective_top_k = top_k + offset` — the depth a paged request must
  rank to. Used ONLY for fetch depth, never for the lift.
- `effective_lift = min(PIN_RANK_LIFT, top_k)` — the per-request lift
  strength. **Clamped on `top_k`, not `effective_top_k`**: rev 3
  clamped on the offset-inclusive value, which made the lift grow
  with page depth — the same logical query ranked differently on
  page 1 and page 3, breaking pagination (rev-3 review finding 1,
  BLOCKING). A small `top_k` shrinks the lift; nothing errors.

## Decision (proposed)

### 1. The prior lives in the RANK domain: a bounded, clamped lift

Rev 1's multiplicative score boost is dead (no gate in semantic mode;
all-pin pages on RRF's compressed scores at its own grid values).
Instead, wherever a pinned row appears in a channel's ranked
candidate list, its rank improves by `effective_lift` positions
before fusion/cut:

```text
effective_rank(m, ch) = max(1, rank(m, ch) − effective_lift)   # if m.pinned
                        rank(m, ch)                             # otherwise
```

**Ordering, fully specified** (rev 3 defined a per-channel tuple and
left the fused stream — the default mode — undefined; its ties fall
to set-iteration order today, which is hash-nondeterministic across
restarts):

- **Within a single-channel list** (keyword mode, semantic mode,
  degraded fallback): total order is the tuple
  **(effective rank, original rank, memory id)**, ascending. A lifted
  pin ties — and therefore sorts AFTER — the row already holding its
  target rank (original rank breaks the tie); it passes only the rows
  *between*. Pile-ups at the rank-1 floor order by original rank.
- **In the fused (hybrid) stream:** RRF consumes the collided
  effective ranks as-is (`1/(K + effective_rank)` per channel,
  `K = 60` unchanged — NOT re-linearized tuple positions), and the
  fused stream's total order is
  **(fused score descending, memory id ascending)**. Fused-score
  ties are structural (a keyword-only row and a semantic-only row at
  the same effective rank score identically), so the id leg is
  load-bearing, deterministic, and stable across requests — which
  today's set-iteration tie order is not. Adopting it is itself a
  (desirable) tie-ordering change from current behavior, carved out
  of the Rollout equivalence claim below.

**The gate, stated honestly per channel:**

- Keyword channel under FTS5: a real relevance gate — no match, no
  candidacy. Under the **non-FTS5 fallback scorer**
  (`_fallback_search_memory`, which ranks zero-match rows by
  recency), the gate is depth, not absence — the same qualification
  as the semantic channel, applying only to deployments with FTS5
  absent/disabled (rev-3 review finding 12).
- Semantic channel: every embedded row has *some* cosine, so the gate
  is depth. On a sparse result set (fewer genuine matches than
  `top_k`), low-similarity rows including pins can fill the bottom of
  the page — exactly as they can today with `include_pinned=True`.
  The mechanism adds no new *membership* exposure.

**Score domains untouched.** `rrf_score` keeps its documented ~2/61
ceiling; `semantic_similarity` stays raw. In semantic mode the result
order may therefore disagree with the `semantic_similarity` fields
the caller sees; each result row carries the item's `pinned` flag,
which explains a *pin-caused* reorder, and the docs updated by this
ADR say so. (It does not explain fetch-depth effects — see §2, which
dispositions those separately; rev 3 overclaimed here.)

**One mechanism for every mode.** Ranks exist in the keyword list,
the semantic ranking, the keyword-only path, and the degraded
fallback — the SAME clamped lift and the SAME ordering rules apply in
all of them, and in the fused stream via the effective ranks it
consumes. Keyword-only/degraded deployments keep pin preference,
relevance-gated instead of float-shaped.

### 2. The candidate fetch extends by the lift's reach (no quota)

Rev 2's "pinned quota at true full-ranking rank" was killed by review
(unbounded keyword sort; rank-within-pins ≠ full-channel rank; deep
rows dead weight). The replacement, with **per-mode baselines stated**
(rev 3's single "was 2×" annotation was false for keyword-only mode —
rev-3 review finding 5):

```text
hybrid, per channel:   top (2 × effective_top_k + effective_lift)   # today: 2 × effective_top_k
semantic mode:         top (2 × effective_top_k + effective_lift)   # today: 2 × effective_top_k
keyword-only mode:     top (effective_top_k + effective_lift)       # today: effective_top_k (no window)
```

Every rank the lift operates on is an honest rank from the fetch
itself; no new port surface exists (`search_pinned` dies with nothing
replacing it — the ordinary ranked query with `include_pinned=True`
is the one primitive). Pins deeper than the widened fetch remain
unreachable — relevance ordering, not arrival order or cap luck,
decides which pins compete.

**Honestly-dispositioned side effect (rev-3 review finding 6):** in
hybrid mode the widened fetch changes *fusion membership* for
unpinned rows too — a row just past today's window gains a channel
term it lacked, so at `LIFT > 0` two rows with no pin involvement can
change relative order as a function of the pin constant. This is a
fetch-depth effect, not a pin effect, and "changes pin policy only"
(rev 3) was therefore false. It is accepted: deeper fetch is strictly
*more* evidence in the fusion, the effect exists today whenever
`top_k` changes, and the sweep's ablation cell (§3) measures the two
effects separately so the tuning gates attribute what they see.

**Reach, stated per mode** (agreed ground from the review's split
finding 4): the deepest unlifted rank a pin can surface *from* is
bounded by `top_k + effective_lift − 1` in the single-channel modes
(the page is `top_k` deep and the lift is bounded); in hybrid a
deeper pin can still surface via two-channel fusion. The fetch
formulas above cover the full reach in every mode; in single-channel
modes the fetch beyond `effective_top_k + effective_lift` does not
exist (see the keyword-only baseline), so nothing is fetched that
cannot matter.

**Pagination honesty (rev-3 review findings 1 and 3):** with the
clamp offset-invariant (§ Definitions), the single-channel modes are
offset-stable: two consecutive pages neither duplicate nor drop rows.
The fused mode is NOT offset-stable — and was not before this ADR:
fetch depth grows with `offset`, so a deep page can add a channel
term to a row and move it across a page boundary. That instability is
inherited, unchanged by this design, and now documented instead of
claimed-solved (rev 3 claimed the tie-break made the pagination test
"satisfiable" everywhere; it is satisfiable in the single-channel
modes and documented-unstable in hybrid).

### 3. Tuning against the upgraded harness

- **Fixture upgrades first:** pinned-target status **derived at load
  time** from the corpus fixture's per-memory `pinned` field (not
  stored per query — a stored copy silently drifts when the corpus is
  re-snapshotted; rev-3 review finding 15); pinned-target queries
  expanded to ≥20; a ~10-query broad-query fixture for the
  pin-crowding probe.
- **Harness upgrades first:** embed once per store, re-score all
  sweep cells against the same vectors; `PIN_RANK_LIFT` injected via
  the `EmbeddingService` constructor for the sweep (production wiring
  passes the named module default; the keyword-only path — which
  runs precisely when no `EmbeddingService` exists — reads the same
  module constant directly). The constant is deliberately code-only:
  no env var, no `core.json` key; retuning is a code change by
  design. The harness's `pinned_limit=0` special case is deleted.
- **Sweep:** `PIN_RANK_LIFT ∈ {0, 2, 4, 8}`, all cells valid under
  the clamp at the benchmark's `top_k=10`. Each `LIFT > 0` cell is
  paired with a **window-only ablation** (fetch extended by the same
  `effective_lift`, lift itself disabled) so the fetch-depth side
  effect (§2) and the lift's own effect are separately attributable.
  `LIFT = 0` (lift off; float still removed) is an admissible
  outcome and the test plan survives it.
- **Crowding gate is a DELTA over the LIFT=0 cell** (rev-3 review
  finding 8 — an absolute gate measures the corpus, not the lift:
  live-verified, a broad query honestly returns 10/10 pins at zero
  lift on the 149-pin corpus, which no ranking policy should hide).
  Measured on hybrid mode at the benchmark's `top_k=10` over the
  broad-query fixture: **mean pins-in-top-10 minus the LIFT=0 cell's
  mean ≤ 1.0, and max per-query increase ≤ 2**. The LIFT=0 cell
  passes by construction; an all-cells-fail outcome is impossible.
- **Held-out validation is a regression veto:** queries split ~60/40
  tune/validate; the metric is hybrid R@1 over the validation
  pinned-target queries at the cell's constants, baselined against
  the LIFT=0 cell; **any negative validated delta rejects the cell**.
  The veto is deliberately asymmetric — no positive confirmation is
  required (at ~8 validation queries, granularity 0.125, a
  confirmation bar would be noise-decided), but a regression of even
  one query is disqualifying because `LIFT = 0` is always available.

### 4. Surface contract

- `include_pinned` keeps its exact meaning in every mode (`False`
  hides pins entirely) — visibility policy, orthogonal to ranking.
- `channel` keeps reporting the producing ranked channel; the
  `"pinned"` value stops occurring in ALL modes (the
  documented-behavior change that drives versioning).
- `pinned_limit` becomes inert on every wire surface (MCP tool, REST
  query param, CLI flag): accepted, marked deprecated (FastAPI
  `deprecated=True` so the OpenAPI spec says so per STABILITY step
  2), **its existing `ge/le` range validation KEPT** (rev 3 proposed
  dropping it, which is wire-observable validation loosening on a
  bound surface — an unclassified change bought nothing; rev-3
  review finding 10), removed **no earlier than v5.0.0**.
- Internal signatures (`EmbeddingService.search_*`,
  `search_memory.execute`) drop `pinned_limit` outright; internal
  callers (CLI plumbing, `scripts/benchmark_embeddings.py`) are
  updated in the same change — they are not under STABILITY.
- `MemoryStorePort.search_pinned` loses ALL callers (both float
  sites die) and is removed (port + store + tests). Nothing replaces
  it.
- **Documentation inventory** (checklist for the implementation
  stage; the schema snapshot does not catch docstring drift):
  `mcp_server_spec.md` (channel enum, float paragraphs — and the
  `context_recent` tool's shared relevance-block description, which
  routes through `search_memory.execute` and changes with it),
  `docs/cli/commands.md` (relevance/channel column text),
  `scored_memory.py` docstring (documents the `pinned` channel
  value), `interfaces/serializers.py` relevance commentary, the
  MCP/REST/CLI docstrings and flag help, `memory_store_port.py`
  float commentary and `DEFAULT_PINNED_LIMIT`, and the
  `sqlite_store.py` include/exclude tristate comments. Grep `pinned`
  across `docs/` and docstrings is the exit check.

### 5. Versioning — OPEN QUESTION for the operator

Response *shapes* are unchanged; the request schema changes only by
marking one parameter deprecated (its type, default, and validation
are untouched — rev 3's "schemas are unchanged" premise was
imprecise; rev-3 review finding 10). Documented *behavior* changes
(pins stop leading; a documented `channel` enum value ceases to
occur; a documented parameter goes inert). Under STABILITY.md's
"changing the meaning of an existing field" this is **MAJOR →
recommend v4.0.0**. On the deprecation window, stated honestly:
STABILITY's window text attaches to MAJOR changes wholesale and says
"keep the old shape working." This ADR keeps the old *syntax* working
(the accepted-inert parameter, through v4.x) but the old *behavior*
(pins leading the page) ends at v4.0.0 with no parallel surface —
**a deliberate deviation from the policy's letter**, justified by
proportionality: a parallel `/api/v2` deployment to preserve a float
for an audience of zero external users is ceremony without a
beneficiary. The operator accepting §5 accepts that deviation
explicitly. Calling this MINOR remains rejected: quiet
reinterpretation is how stability promises rot.

## Consequences

- **The lift cannot manufacture an all-pin page from thin air, but it
  CAN complete one.** Stated with the arithmetic on the table (rev
  3's "adds no all-pin failure mode" was falsified at sanctioned
  parameters; rev-3 review finding 13): the lift displaces up to
  ~`effective_lift` trailing unpinned rows, so a page that honestly
  ranks ≥ `top_k − effective_lift` pins near the top can finish
  all-pin. What can no longer happen is a cap-shaped policy filling a
  page with pins the ranking did not place near the top — the float's
  defect. A page that is pin-heavy because 149 pins genuinely outrank
  everything is relevance deciding, and no ranking policy should hide
  it.
- **Per-channel bound, honestly scoped** (rev-3 review finding 16): a
  pin passes at most `effective_lift` competitors *per channel*. In
  the fused stream, a rank improvement in both channels can move a
  pin past MORE than `effective_lift` unpinned rows when the score
  band is dense — the per-channel bound does not linearly bound fused
  positions gained. The qualitative safety property (bounded,
  relevance-gated influence) holds; the quantitative sentence applies
  to the single-channel modes.
- Degraded and keyword-only deployments keep pin preference via the
  same mechanism.
- One ranking-policy mechanism total (down from two float
  implementations + one exclusion-set protocol); the benchmark
  measures production behavior with no special configuration.
- Costs accepted: `PIN_RANK_LIFT` is a global, code-only constant
  (retuning is a release); hybrid fetch depth co-varies with the pin
  constant (the §2 side effect, measured by the ablation cells);
  result order is no longer derivable from the raw per-channel
  signals alone; hybrid pagination remains offset-unstable as it is
  today (documented, §2).

## Test plan

- **Bounded-lift + ordering properties** (deterministic, injected
  constants; equality-of-score assertions stay banned): a pin gains
  at most `effective_lift` positions per channel; a pin lifted onto
  an occupied rank sorts AFTER the original-rank holder; floor
  pile-ups order by original rank then id; a fused-score tie orders
  by memory id (constructible: a keyword-only row and a semantic-only
  row at the same effective rank).
- **Clamp:** `top_k=1` and `top_k=2` requests succeed with the lift
  clamped; two pages of one query (`offset=0`, `offset=top_k`) use
  the SAME `effective_lift` (the rev-3 defect's regression test).
- **Keyword gate:** under FTS5, a pin with no match never surfaces in
  the keyword channel (scoped to FTS5 — the fallback scorer is
  depth-gated and exempt).
- **Mode parity:** keyword mode and degraded-hybrid apply the same
  lift and ordering as the fused path's channels (degraded-hybrid is
  constructible via the existing provider-failure test pattern).
- **Fetch reach, per mode:** single-channel — a pin at unlifted rank
  `top_k + effective_lift − 1` can surface and one deeper cannot;
  hybrid — a pin at the widened fetch boundary of one channel enters
  fusion (membership, not position, is the assertion; rev 3's
  uniform boundary test was impossible in three of four modes).
- **`include_pinned=False`** hides pins in all three modes.
- **Pagination:** in keyword and semantic modes, two consecutive
  `offset` pages neither duplicate nor drop rows. (Hybrid is
  documented-unstable and gets no false test.)
- **Inert-param compat:** `pinned_limit` accepted on MCP/REST/CLI,
  ignored, `ge/le` still enforced, OpenAPI marks it deprecated.
- Tuning gates live in the harness: unpinned non-regression,
  pinned-target improvement, the delta crowding gate, the held-out
  regression veto, and the window-only ablation cells.
- Schema snapshot + the §4 documentation checklist land with the
  surface change.

## Winning cell (step 4 adjudicated 2026-08-29): PIN_RANK_LIFT = 0

The tuning sweep ran on `v4/develop` (driver commit `0f9cf940`; seven
cells — LIFT 0/2/4/8 + window-only ablations; one embedded store,
cached query vectors, exact integer hit counts; results + gate policy
in `data/embedding_benchmark/sweep_results.json`, verifier findings
alongside). **The held-out regression veto rejected every nonzero
lift**: validate∩pinned-target hybrid R@1 fell 0.875 → 0.5 (lifts
2/4) and → 0.375 (lift 8), tune-side pinned deltas were negative at
every lift (the lift harmed the subset it exists to help), unpinned
R@1 dropped 2-5 queries, and lift 4 also failed the crowding gate
(max per-query increase +3). The ablation cells held the veto metric
exactly flat, attributing the damage to the lift itself, not the
fetch depth. Mechanism, consistent with §1's own ordering rules: on
a 149-pin corpus a competitor pin at ranks (2,2) floors to (1,1) and
exactly TIES a true (1,1) target's fused score, turning the fused id
tie-break into an id lottery that displaces true targets — the
single-channel tuple order protects the incumbent; RRF's bare-number
rank consumption cannot.

**So the mechanism ships DISABLED — and the sweep's larger finding is
that the float removal alone was the fix**: with the float gone,
broad-query crowding fell from the float-era mean 10.0 pins-in-top-10
to 5.0 at LIFT=0 — half the all-pin page was float-manufactured, the
remaining pin presence is relevance-earned. Both outcomes are ones
this ADR explicitly admitted in advance (§3: "`LIFT = 0` … is an
admissible outcome"; Consequences: honest pin-density is relevance
deciding). The lift machinery stays in the code, tested (including
the mutation-verified fusion tests) and injectable, should a future
corpus or a fused-tie-break redesign change the evidence. Harness
hardening minors from the sweep's verification (channel-integrity
assertion, run-identity metadata, `--out` default collision, noise
labels not consulted by ablation verdicts) are recorded in
`data/embedding_benchmark/sweep_verifier_findings.txt` and on the
V3_PLAN punch list.

## Rollout

1. ✅ Operator decision on this rev (mechanism reviewed three times; the
   rev-3→4 amendments follow the ultracode review's prescriptions
   verbatim). ACCEPTED 2026-08-29 with §5 = v4.0.0.
2. ✅ Harness + fixture upgrades (§3) — landed on `main` (rev 157).
3. ✅ Implement lift + fetch extension with `PIN_RANK_LIFT=0` injected
   — DONE on `v4/develop` (`de7e5c6d` + fix pass `8072cf4a`; 817 tests).
   At LIFT=0 the fetch extension adds zero rows and no rank moves —
   the ranked stream is identical to today's `pinned_limit=0`
   behavior **up to fused-tie ordering**, which this ADR makes
   deterministic (today it is hash-iteration-dependent; the carve-out
   is the improvement, not a regression). The float removal itself is
   the deliberate, versioned behavior change at defaults — enumerated
   in the CHANGELOG.
4. ✅ Tuning run per §3 (cells + ablations) — DONE (`0f9cf940`); the
   winning constant is the shipped default (see Winning cell above);
   record the cell here.
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
  required.** Sustained and fixed in rev 3: the pinned quota was
  unimplementable (keyword true-rank needs an unbounded sort;
  pinned-only predicate yields rank-within-pins; deep rows dead
  weight) → lift-reach window extension; LIFT=0 equivalence falsified
  by the always-on quota → construction-level identity; caller-
  triggerable `K_WINDOW/2` assert self-contradicted by the sweep →
  clamp; undefined tie-break → total order; all-pin and gate
  overclaims → restated; STABILITY misquote → owned deviation;
  noise-decided held-out gate → regression veto.
- **Rev 3 (2026-08-29): ultracode review (6 finder lenses, per-
  finding dual adversarial verification; 46 agents) — mechanism
  survived, amendments REQUIRED; all applied in rev 4.** Gating,
  fixed: the clamp was offset-dependent, breaking pagination within
  one paged query (→ clamp on `top_k`); the fused stream had no
  defined total order (ties fall to hash-iteration order today) (→
  fused order = score desc, id asc; RRF consumes collided effective
  ranks); the pagination "now satisfiable" claim was false for
  hybrid, whose fetch depth grows with offset (→ documented as
  inherited instability; test scoped to single-channel modes); the
  "was 2×" fetch baseline was false for keyword-only mode (→
  per-mode baselines + keyword window specified); "changes pin
  policy only" was false — the widened fetch reorders unpinned rows
  (→ dispositioned; ablation cells attribute effects); the absolute
  crowding gate could veto every cell including LIFT=0 —
  live-verified 10/10 pins on an honest broad query (→ delta gate
  over the LIFT=0 cell). Minors, fixed: default `top_k` is 8 not 10
  (the relation worsens, a fortiori); §5's "schemas unchanged" was
  imprecise and the `ge/le` drop was unclassified loosening (→
  validation kept); keyword gate qualified for the non-FTS5 fallback
  scorer; "cannot manufacture an all-pin page" restated as
  completion-not-manufacture with the displacement arithmetic;
  semantic-exposure-parity test replaced by a membership assertion;
  pinned-target flags derived at load, not stored; the per-channel
  bound rescoped (fused positions gained can exceed it). Split
  (non-gating) findings addressed by one-line clarifications:
  `context_recent` named in the doc inventory; keyword-path constant
  source stated; validated-delta metric and the veto's deliberate
  asymmetry specified.
