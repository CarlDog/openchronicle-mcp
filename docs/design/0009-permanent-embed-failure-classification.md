# ADR 0009 — Permanent Embed-Failure Classification

**Status:** ACCEPTED (rev 3, operator, 2026-08-29) — after a
two-critic adversarial review of rev 1 (2 BLOCKING, 8 MAJOR-tier, 5
MINOR — all dispositioned in rev 2) and a verification round on rev 2
by the same critics (all findings confirmed resolved against code;
residuals amended in rev 3). Implementation proceeds on `main` (v3.x
additive line). · **Date:** 2026-08-29 ·
**Queue:** V3_PLAN active queue item 4 · **Ships:** v3.x from `main`
(additive) — independent of the v4 line.

## Problem

Under ADR 0005's `truncate:false` contract, a memory whose content
exceeds the embedding model's context fails **visibly** — correct and
deliberate. But nothing knows the failure is *permanent*. Observed
live after the v3.2.0 cutover: 9 corpus rows exceed
`nomic-embed-text`'s context; every backfill retries and fails all 9,
and once they are the only candidates there are no successes to reset
the consecutive-failure counter — `embedding_status.status` reads
**`degraded` forever on a healthy system** (`failure_count` 36 = 9
rows × 4 runs, all via the per-item handler). Failure-shaped health
on designed behavior — the mirror of the rev-126 defect. Sub-defects:
wasted retries; counter poisoning; and (rev-1 review) the same
poisoning on the *save/update* path, plus a first-backfill-after-fix
that would trip the maintenance job's all-failed guard.

## Key insight: permanence is SPACE- and CONTENT-scoped, never absolute

"Unembeddable" is only true relative to (provider, model, revision,
settings) × (this exact content). A larger-context model or a
shortened memory embeds fine. The marker must expire on either change
— and ADR 0005's identity matching already expresses exactly that.

## Decision (proposed)

### 1. Classification: a structured `CONTENT_TOO_LONG` error code

New canonical code `CONTENT_TOO_LONG` (added to `error_codes.py` and
its `__all__`; the canonical-codes test updates with it). Raised by
the adapters in place of `PROVIDER_ERROR` when the upstream rejection
is the over-length one:

- **Ollama:** in the existing `httpx.HTTPStatusError` handler — which
  still holds the structured status and body (`_upstream_error`) — a
  400 whose error message contains the substring `context length`,
  case-insensitively. Ground truth for the predicate is the repo's
  own captured rejection, `"input exceeds maximum context length"`
  (pinned in `tests/test_embedding_adapters.py` and quoted in the
  adapter) — NOT rev 1's unverified paraphrase. The predicate is one
  module-level function with its own unit tests.
- **OpenAI:** requires an adapter change rev 1 glossed: today the
  adapter stringifies bare `Exception` and preserves no SDK
  structure. It will inspect the SDK error's structured attributes
  and classify when `code == "context_length_exceeded"`, with a
  conservative message-substring fallback (`context length`) —
  **gated, like the Ollama predicate, to 400-family SDK errors
  only** (rev-2 review: an ungated fallback would classify any error
  whose stringification happens to contain the substring). **Caveat, accepted and documented:** on
  generic OpenAI-compatible hosts (`OPENAI_BASE_URL` — Voyage,
  Gemini, Mistral) neither may match; the conservative bias means
  those deployments keep today's retry-forever behavior rather than
  risk a false-permanent. No verified capture of the OpenAI
  embeddings over-length body exists in the repo; the implementation
  takes one (live or from SDK docs) before pinning the fixture.
- **Mechanism for per-item-only classification (rev-1 gap):** the
  ADAPTER classifies whenever the upstream rejection matches — batch
  or single call; the SERVICE ignores the code at the batch level
  (falls to the existing per-item isolation retry) and acts on it
  ONLY in per-item handlers. A batch-level `CONTENT_TOO_LONG` is
  never treated as attributing every item.

Misclassification bias is asymmetric by design: a false negative
preserves today's behavior; a false positive parks a row until its
next content edit or space change. The predicate stays conservative.

### 2. Persistence: a tombstone row inside the ADR 0005 identity

Migration `004_embedding_status.sql`:

```sql
ALTER TABLE memory_embeddings ADD COLUMN status TEXT NOT NULL DEFAULT 'ok';
-- 'ok'               — a real vector
-- 'content_too_long' — a tombstone: no usable vector; this content,
--                      in this space, is known unembeddable
```

On a per-item `CONTENT_TOO_LONG` outcome, a **tombstone** is written:
the full ADR 0005 identity (provider, model, `model_revision`,
`settings_fingerprint`), the `content_hash` OF THE CONTENT THAT
FAILED, `status='content_too_long'`, an empty vector payload, and
`dimensions = 0` as the honest fact of the stored payload.

**`save_embedding` grows a `status` parameter (default `'ok'`), and —
the rev-1 BLOCKING fix — the upsert's update set includes
`status = excluded.status`**, so a later *successful* save onto a
tombstoned row resurrects it to `'ok'` in the same statement. Without
that clause, the ADR's own headline recovery (switch to a
larger-context model → re-embed succeeds) would leave a valid vector
permanently marked unembeddable. A dedicated resurrection test
asserts the round-trip: tombstone → successful save → row is `'ok'`,
searchable, counted embedded.

CAS semantics are unchanged and sufficient (verified in review): the
tombstone write compares the failed content's hash against the
memory's current content and is refused if the content moved mid-run
— the row simply remains a candidate.

**Overwrite trade-off, dispositioned (rev-1 MAJOR; same-space branch
added per rev-2 review):** the table is one row per memory, so a
tombstone REPLACES whatever row sat there — two branches:

- *Old-space vector* (e.g. the 9 rows' intact OpenAI vectors, which
  today would make a provider rollback instantly free): accepted —
  the rollback cost is 9 re-embeds (~cents, ~seconds) and a brief
  FTS5-only window, while preserving dead vectors as rollback
  insurance would require abandoning one-row-per-memory.
- *Same-space serving vector*: a `force=true` re-embed against a
  provider whose limits drifted (same model label, revision NULL)
  can replace a valid, currently-serving vector with a tombstone —
  pre-ADR, a failed force wrote nothing and the vector kept serving.
  Accepted: `force` is an explicit operator override, the trigger is
  provider-side drift on unchanged content (exotic), the INFO line
  names the remedy, and recovery is one successful re-embed. Both
  branches recorded so neither surprises a future operator.

**Expiry (mechanism named, per review):** candidacy exclusion is
EMERGENT — a current-identity, current-hash tombstone already reads
as current to `_is_current`, which consults no status; **zero new
candidacy code exists, and none may be added** (an explicit
"tombstone → not current" branch would reintroduce the infinite
retry). Content edits in practice re-candidate via the existing
row-deletion on update (rev 122); the hash-mismatch path is the
backstop for any future write path that skips deletion. Space
changes re-candidate via identity mismatch. This adds a fourth row
state to ADR 0005 §3's "no third freshness state" model —
**ADR 0005 is amended by this ADR**: rows are current-usable,
stale-and-ineligible, absent, or current-unembeddable; the
tombstone is current (not re-generated) yet never eligible for
similarity.

### 3. Consumers — every branching surface enumerated

- **Candidacy:** emergent, above. `force=true` retries tombstones
  (verified: force bypasses `_is_current` entirely; no
  special-casing).
- **All THREE `_record_failure` sites** (rev-1 MAJOR — rev 1 covered
  one): a `CONTENT_TOO_LONG` outcome records neither failure nor
  success at the backfill per-item handler, the save/update path,
  and the search-query path (an over-length *query* is caller
  content, not provider health). The save/update path ALSO writes
  the tombstone, so an edit that stays over-length re-parks
  immediately instead of poisoning health until the next 6-hourly
  backfill.
- **Save-path contract, decided (rev-2 review's one MAJOR):**
  `generate_for_memory` treats a classified `CONTENT_TOO_LONG` as a
  HANDLED outcome — it writes the tombstone, logs the one INFO line,
  and **returns normally; it does not raise**. Transient failures
  keep the existing raise-on-failure contract unchanged, so the
  callers' warning blocks (`add_memory`/`update_memory`) still fire
  for genuine failures and never emit a traceback for a parked,
  designed outcome (the rev-144 log-noise class). **Caller-visible
  semantics, decided: silent by design at the response level.** The
  save itself SUCCEEDED — the memory is stored and FTS5-searchable —
  and embedding outcomes have never been part of the save response;
  health (`unembeddable`) and the INFO line are the surfaces. If
  operator experience later wants the remedy at save time, an
  additive response hint is a one-line follow-up, not smuggled in
  here.
- **`BackfillResult` grows a third count (rev-1 BLOCKING #2):**
  `BackfillResult(generated, failed, tombstoned, elapsed_ms)`.
  Tombstone writes count in `tombstoned` ONLY. Consumers updated in
  the same change: the maintenance job's all-failed guard
  (`failed and not generated`) keeps its expression — a
  9-tombstone/0-failed run no longer matches it; `embed_memory`'s
  ok/partial/failed mapping treats a tombstoned-only run as `ok` and
  carries the additive `tombstoned` field; the CLI summary prints it
  and exits 0. The deploy note then holds on every surface.
- **Search:** `list_embeddings` returns only `status='ok'` rows.
  (Belt-and-braces: `dimensions=0` already fails the dimension
  filter; the status predicate is the stated guard.)
- **Dimension truth:** `stored_embedding_dimensions()` gains the
  `status='ok'` predicate — a tombstone's factual `0` must not
  surface as `stored_dimensions: [0, 768]` on the 0003-F2 drift
  surface (rev-1 MAJOR).
- **Health — the partition, stated precisely (rev-1 MAJOR):** rows
  partition as: `status='ok'` rows → `embedded` (current ones
  usable, non-current ones ALSO in a stale bucket, exactly as
  today); **current** tombstones (identity+hash match) →
  `unembeddable`, a new additive field; **non-current** tombstones →
  the existing `space_mismatch`/`content_mismatch` stale buckets
  (they are genuine backfill candidates and the buckets' documented
  sum-equals-backfill-work invariant must keep holding). `embedded`
  becomes `count(status='ok')`: for every pre-ADR database this is
  byte-identical to today's all-rows count (tombstones don't exist
  yet), so the meaning is refined for a new row type, not changed
  for an existing one — dispositioned as additive. `missing` stays
  `total − all rows` (a tombstone is known, not missing). Expected
  live reading post-deploy: `embedded: 863, missing: 0, stale: 0,
  unembeddable: 9, status: active`. The health test asserts the
  PARTITION **over row classes** — every `memory_embeddings` row is
  exactly one of {`status='ok'`, current tombstone, non-current
  tombstone} and the class counts sum to the row count — NOT over
  the health FIELDS, which legitimately overlay (an ok-but-stale row
  is in `embedded` AND a stale bucket, exactly as today; the rev-2
  review caught a field-level partition test as self-contradictory;
  rev 1's disjointness test was trivially satisfiable by a row in
  zero buckets). **Cross-field relationships, stated so nobody
  re-derives them wrong (rev-2 review):** `stale ⊆ embedded` no
  longer holds — a non-current tombstone is in a stale bucket but
  not in `embedded` (after a future provider switch the live corpus
  would read `embedded: 863, stale: 872`); the invariants that DO
  hold are `embedded + tombstones = total rows` and
  `missing = total memories − total rows`, and `stale` counts
  regeneration work regardless of row status. `MAINTENANCE.md`'s
  health notes carry these relationships (docs checklist).
- **Logging:** tombstone write = one INFO line with the memory id and
  the remedy (shorten the content, or use a larger-context model).
- **Docs + rendering checklist:** `env_vars.md`/`MAINTENANCE.md`/
  `mcp_client_setup.md` wherever `embedding_status` fields are
  enumerated (MAINTENANCE.md also gains the cross-field
  relationships above); **`mcp_server_spec.md`** (the `memory_embed`
  row's progress-via-health text gains `unembeddable`/`tombstoned`,
  and the error-semantics prose that names `PROVIDER_ERROR` as the
  adapters' code learns of `CONTENT_TOO_LONG`) — rev-2 review caught
  its omission; the `memory_embed` tool description (`force` retries
  tombstones; `tombstoned` in the response); the CLI `oc memory
  embed` run-summary line AND the `--status` human rendering, which
  prints Total/Embedded/Missing/Stale and would otherwise leave the
  9 parked rows visible in NO printed field — it gains an
  `Unembeddable` line; the maintenance guard's message names all
  three counts (its "all N failed" wording goes stale in mixed
  runs); `error_codes.py` `__all__` + canonical test.

### 4. Out of scope

- Content chunking / summarize-then-embed.
- A second `status` value. Provider-level permanent-looking failures
  (bad model, auth) are not per-content facts; they stay in the
  counters.
- REST/MCP status-mapping for `CONTENT_TOO_LONG` on the semantic-
  query path: today an over-length *query* surfaces as the generic
  502 provider mapping — a caller-content condition presented as a
  gateway error. Real, pre-existing, and NOT worsened here (rev 1
  claimed the code "reaches REST envelopes" as if that dispositioned
  the MCP gap; in every flow this ADR touches the code is consumed
  internally and reaches no envelope). The 502-vs-4xx question is
  parked with the standing `error_code` V3_PLAN item.

## Versioning

Additive throughout: a new error code, a defaulted column (migration
004, idempotent), a new health field, a new additive
`BackfillResult`/`memory_embed` response field, and a documented
`force` refinement. **MINOR**, ships from `main` in the next v3.x
tag. Deploy note: the first backfill after deploy writes 9
tombstones, reports `ok` with `tombstoned: 9`, the maintenance job
run succeeds, and health goes `active` with `unembeddable: 9`.

## Test plan

- Adapter classification: the captured ollama rejection →
  `CONTENT_TOO_LONG`; near-miss bodies (timeout, other 400s) →
  `PROVIDER_ERROR`; openai SDK error with
  `code=context_length_exceeded` and with message-only fallback; a
  compat-host unclassifiable error stays `PROVIDER_ERROR`.
- Batch mechanism: a batch containing one over-length row falls to
  isolation; only that row tombstones; the batch-level code is never
  trusted for attribution.
- Tombstone write: identity + failed-content hash + `status` +
  `dimensions=0`; CAS refusal when content moved mid-run.
- **Resurrection (the rev-1 blocker's regression test):** tombstone →
  successful save → `status='ok'`, in `list_embeddings`, counted
  `embedded`, absent from `unembeddable`.
- Candidacy: current tombstones excluded from `generate_missing`;
  `force=true` retries; a space change re-candidates; a content
  update (deletion path) re-candidates.
- Save path: over-length save/update parks immediately (tombstone
  written), records no failure; a transient save failure still
  records one. Search path: over-length query records no failure.
- `BackfillResult`: tombstoned-only run → maintenance job success,
  `embed_memory` status `ok` with `tombstoned` count, CLI exit 0;
  mixed runs report all three counts.
- Search: tombstones never in `list_embeddings`;
  `stored_embedding_dimensions` never contains 0 from a tombstone.
- Save-path contract: an over-length save/update RETURNS normally
  (no raise), callers emit no traceback, the response is unchanged;
  a transient save failure still raises and still warns.
- Health: the row-class PARTITION asserted (every row exactly one class;
  invariant sum); `unembeddable` counts only current tombstones;
  non-current tombstones appear in the stale buckets; counters
  unchanged by classified outcomes; transient failures still count.
- Migration 004: applies to a populated DB (`status='ok'` on
  existing rows), re-run no-op.

## Review history

- **Rev 1 (2026-08-29): two-critic adversarial review** (identity/
  data-model lens; adapter/surfaces lens). Sustained and fixed in
  rev 2 — BLOCKING: the upsert's enumerated update set would never
  reset `status`, so the headline recovery (bigger model) left
  resurrected vectors permanently unembeddable (→ `status =
  excluded.status` + resurrection test); `BackfillResult` accounting
  was unspecified and every implicit answer broke a consumer — the
  first post-deploy backfill would have tripped the maintenance
  all-failed guard "provider down?" on designed behavior (→
  `tombstoned` count + consumer-by-consumer spec). MAJOR: tombstone
  overwrite destroys the rollback-enabling old-space vectors (→
  dispositioned as an accepted trade); bucket exclusion contradicted
  expiry — the literal reading left stale tombstones in NO bucket
  and "disjointness" tests pass trivially (→ precise partition;
  partition-not-disjointness test); the save/update/search
  `_record_failure` sites were uncovered — a single save of an
  over-length memory still flipped health to degraded, and edits
  destroyed tombstones without re-parking (→ all three sites
  specified; save path parks); `dimensions=0` leaked into the
  `stored_dimensions` truth surface (→ status predicate); `embedded`
  /`missing` semantics drifted undispositioned (→ refined-for-new-
  row-type argument stated); the openai adapter "already parses
  bodies" premise was false and its predicate had no fallback (→
  adapter change acknowledged; fallback + compat-host caveat).
  MINOR: rev 1's quoted ollama rejection matched no captured string
  (→ fixture-grounded); per-item-only classification was
  unimplementable at the adapter alone (→ adapter classifies,
  service attributes); "reaches REST envelopes" overstated (→
  corrected; 502-mapping parked); content-edit expiry credited the
  wrong mechanism (→ deletion path named, hash path as backstop);
  candidacy exclusion's zero-code emergence and the ADR 0005
  state-model amendment made explicit. Verified clean in the same
  review: emergent candidacy, CAS sufficiency, force semantics,
  migration feasibility, single-source health assembly, and the
  batch-level counter (the observed 36 was purely per-item — the
  fix does stop the climb once the save path is covered).
- **Rev 2 (2026-08-29): re-verified by both original critics.** All
  rev-1 findings confirmed RESOLVED against code (the resurrection
  clause closes every write path including delete-then-INSERT under
  CAS; the stated partition matches the real bucket SQL with no
  status predicate needed; the maintenance guard, `embed_memory`
  mapping, and CLI exit all hold with zero expression changes;
  `dimensions=0` creates no third mismatch class — the bucket SQL
  never consults dimensions). Residuals fixed in rev 3 — the shared
  MAJOR: the save-path park's exception contract and caller-visible
  semantics were implementer-inventable (→ decided: handled outcome,
  returns normally, no traceback, response silent by design with
  health as the surface). MINORs: field-level partition test was
  self-contradictory (→ row-class partition + cross-field
  relationships stated, `stale ⊆ embedded` breakage named); OpenAI
  fallback lacked the 400 gate (→ gated); `mcp_server_spec.md` and
  the CLI `--status` human rendering were missing from the checklist
  (→ added, `Unembeddable` line specified); the same-space
  force-overwrite branch was undispositioned (→ accepted, recorded);
  the maintenance guard's "all N failed" message wording (→ names
  all three counts).
