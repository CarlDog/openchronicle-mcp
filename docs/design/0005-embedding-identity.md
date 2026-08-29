# ADR 0005 — Composite Embedding Identity

**Status:** ACCEPTED (revision 2) — operator-ratified 2026-08-29;
**Phases B and C implemented the same day** (assessment revs 134-135,
768 → 786 tests). Phase D remains · **Date:** 2026-08-29

**Sources:** [0002 Finding 3](0002-openclaw-memory-review.md) (proposed
hardening), [0003 Finding 1](0003-ollama-repository-review.md) (promoted
this to an ADR), 0004's independent corroboration.

> **This is the second revision.** Revision 1 was put through a
> three-critic adversarial review (over-engineering · correctness ·
> source-consistency) before any decision, and did not survive it: two
> would-be production incidents (a SQL `= NULL` predicate that would
> have blanked semantic search on the default deployment, and a
> content-hash definition that livelocked backfill under any client-side
> input transform), an unimplementable migration rule, a grace state
> that collided with the plan's own Phase C, and a stability-bound
> health field whose meaning changed undispositioned. Where revision 1's
> choice was attacked and *survives*, there is an explicit *considered
> and kept* note; where it fell, the change is stated with the failure
> it removes. Revision 1's largest structural fix: **the forced reindex
> moved into Phase B**, which deletes the `legacy` grace state, the
> third health bucket, and the mid-plan mixed-space window in one move.

## 1. Problem

A stored vector's freshness is judged by ONE fact: its `model` string
equals `port.model_name()`. That single label under-determines the
vector space:

1. **Same label, different space.** Two providers can share a model
   label; an Ollama tag can be re-pulled with different weights; a
   provider-side `dimensions` request changes the space without
   changing the name. Same-dimension drift silently corrupts cosine
   ranking; different-dimension drift crashes the matmul and degrades
   to FTS5.
2. **Same label, different input policy.** Ollama's default
   `truncate=true` embeds only a long memory's prefix; the policy used
   is recorded nowhere, so flipping it (0003 Phase C) would leave old
   prefix-vectors indistinguishable from full-content vectors.
3. **Same row, different content — the residual race.** Rev 122 closed
   the acute case (content update deletes the vector before
   re-embedding). What remains: `memory_update` runs on FastAPI's
   threadpool and the provider call sits *outside* the store lock, so
   two updates to one memory can finish embedding out of order and the
   older content's vector publishes last, silently. (Verified
   mechanically reachable in the adversarial review — not
   hypothetical.)

None of these is a live incident on the NAS (OpenAI,
`text-embedding-3-small`, 1536 dims, no request-side options). The
timing argument, stated honestly this time: **only the `provider`
backfill is cheaper today than later** (every existing row is
attributable to the one provider ever deployed — via the reindex, see
§3). The content-hash reindex costs the same whenever it happens;
what shipping now buys is that Phase C's contract changes land on top
of a freshness boundary instead of creating unmarked mixed spaces.

## 2. Decision (proposed)

### Phase B scope — two fields, both consumed on day one

| Field | Type | Content |
|---|---|---|
| `provider` | TEXT NOT NULL | `openai` / `ollama` / `stub` — the adapter kind that produced the vector |
| `content_hash` | TEXT NOT NULL | **SHA-256 of the stored memory content the vector represents** |

Together with the existing `model` and `dimensions` (already recorded
as measured fact), the Phase B space identity is
`(provider, model, dimensions)` — all NOT NULL, so the eligibility
predicate is plain equality with no NULL semantics to trip over.

**Deferred to Phase C** (*considered and moved* — revision 1 shipped
them in B): `model_revision` (nullable provider digest) and
`settings_fingerprint`. On the current deployment the fingerprint
would hash a constant empty option set and the revision would be NULL
on every row — two dead columns until Phase C introduces the first
setting that varies. `ALTER TABLE ADD COLUMN` costs the same then.
Lifecycle notes for the future maintainer, so the fields aren't
mysteries when they do land: `model_revision` uses `IS`/`COALESCE`
matching, **never `=`** (SQL `= NULL` matches nothing — revision 1's
worst defect: the full-identity filter would have blanked semantic
search on the default NULL-revision deployment the day it shipped),
and is droppable if no revision-bearing provider ever deploys;
`settings_fingerprint` is computed by **one shared core helper** over a
typed options dict (canonical JSON: sorted keys, JSON booleans,
explicit nulls, SHA-256) — *never* per-adapter, which three
implementations would drift; a format change stales every vector and
forces a full reindex, which is accepted and must be said in its
migration note.

### Content identity — hash the stored content, not the provider input

`content_hash` is the SHA-256 of the **memory's stored content**.
Revision 1 hashed "the exact string handed to the provider," which
livelocks the moment any client-side transform exists (truncation,
normalization, future chunking): the stored hash never equals
hash-of-current-content, so backfill re-embeds forever while CAS
refuses every save. Under revision 2, any input transform is part of
the *space* identity (`settings_fingerprint`, Phase C) — and until
that field exists, **client-side input transforms are forbidden**; the
string embedded must be the stored content, byte for byte.

### Service rules

- **Freshness:** a row is current iff `(provider, model, dimensions)`
  equals the active port's AND `content_hash` equals the hash of the
  memory's current content. `count_stale_embeddings` and the backfill
  candidate filter move to this predicate.
- **Search eligibility:** `list_embeddings` filters on the space
  identity. A mismatched row is invisible to ranking — equivalent to
  missing, never mixed in. (Content-mismatched rows remain *space*-
  eligible for ranking until backfill replaces them: a slightly-old
  vector in the right space is useful; a wrong-space vector is
  poison.)
- **Conditional publication (CAS):** `save_embedding` takes the
  `content_hash` the caller embedded and persists only if the memory's
  current content still hashes to it — implemented as one
  read-compare-upsert **inside the store lock**, which the adversarial
  review verified makes it atomic against every other store call. A
  losing writer's vector is dropped with a log line; the row stays a
  backfill candidate. **The deleted-memory case is specified** (it was
  not, in revision 1): a memory deleted between embed and save is
  refuse-and-drop-with-log, *not* an error — it must not surface as a
  provider "save" failure in health. Rev 122's delete-before-re-embed
  stays: it is what produces an honest MISSING on a *failed* re-embed,
  which CAS alone does not.
- **Health:** `embedding_status` splits `stale` into **disjoint**
  buckets — `space_mismatch` first; `content_mismatch` counted only
  among space-matching rows — so `stale = space_mismatch +
  content_mismatch` with no double-counting (revision 1's sum counted
  a both-ways-stale row twice). **Stability disposition for `stale`**,
  which revision 1 omitted and STABILITY.md binds: the new predicate
  is a strictly more truthful refinement of an under-counting one
  (model-string-only), shipped as a bug-fix/MINOR with this ADR as
  the record; because the reindex ships in the same release (§3), the
  visible value returns to ~0 within minutes of deploy rather than
  jumping durably. The configured/effective/stored-dimensions status
  0003's Phase B promised is **assigned to Phase C** (it is the
  dimensions-request work's truth surface), recorded here so it can't
  drop silently again.

## 3. Migration + reindex — one release, no grace state

*Considered and replaced* — revision 1 split migration (B) from
reindex (D) and bridged them with a `legacy` eligible-but-stale
sentinel. That state was a guess dressed as a rule ("same-space in
practice"), required a carve-out in every read path, and — fatally —
its grace window overlapped Phase C's fingerprint flip, recreating the
mixed-space ranking this ADR exists to prevent. At 862 rows the full
reindex is minutes of batched OpenAI calls; Phase D's bounded
`embed_batch` is an *optimization* of reindexing, not a prerequisite
for it.

1. `002_embedding_identity.sql` — plain SQL only (the migrator
   executes script files; it has no Python hook and no config access,
   so revision 1's "backfill provider if only one was ever configured"
   was unimplementable — and had no data source anyway):
   `ADD COLUMN provider TEXT NOT NULL DEFAULT ''`,
   `ADD COLUMN content_hash TEXT NOT NULL DEFAULT ''`. The `''`
   sentinel rows are **stale and search-ineligible** — never guessed
   at. (SQLite has no `ADD COLUMN IF NOT EXISTS`; the migrator's
   version gate plus its savepoint-per-migration rollback is what
   makes a partial failure re-runnable, and the migration note must
   say the idempotency lives there, not in the SQL.)
2. The same release's deploy runbook runs the forced reindex
   immediately (`oc memory embed force=true` or
   `oc maintenance run-once embedding_backfill` after the flag): every
   row regenerates through the normal save path, acquiring real
   `provider` + `content_hash`. During those minutes hybrid search
   serves FTS5-only — the documented degradation mode, bounded and
   observable (`missing`/`stale` in health count down to ~0).
3. No third freshness state exists at any point: rows are current,
   stale-and-ineligible, or absent.

## 4. Non-goals (from the source reviews, kept explicit)

- No Ollama-only special case — the model applies identically to all
  providers.
- No source/chunker/tokenizer identity fields (OpenClaw's extras) —
  they return only if file chunking ever does.
- No shadow-index publication, no cache layers, no per-write embedding
  state in save/update responses (0002's separate API question; the
  2026-08-29 mnemosyne incident was investigated and was *not* its
  consumer).
- No change to the retrieval unit or silent chunking.

## 5. Test plan (binding on the implementation batch)

Phase B:

- Space mismatch: same model label, different `provider` → stale and
  search-ineligible.
- Content mismatch: hash differs from current content → stale,
  backfill candidate, still space-eligible for ranking until replaced.
- CAS: writer A embeds v1, writer B updates to v2 and publishes; A's
  late save is refused and logged, B's vector survives.
- CAS deleted-row: memory deleted between embed and save → dropped
  with log, no `IntegrityError`, no provider-failure count.
- Health buckets are disjoint: a row failing both counts once, in
  `space_mismatch`.
- Migration: sentinel rows are stale + ineligible; a forced reindex in
  a test store retires every sentinel; semantic search over sentinel
  rows returns [] while FTS5 still serves them.

Phase C additions (recorded now so they aren't reinvented):
`model_revision` matching via `IS` with a NULL-revision-provider test
pinning that the default deployment stays searchable; fingerprint
canonicalization golden tests against the shared helper; the
configured/effective/stored dimensions status.

## 6. Sequencing after acceptance

1. **Phase B (this ADR):** migration + predicate + CAS + disjoint
   health buckets + forced reindex, one release.
2. **Phase C (0003):** Ollama adapter contract (request `dimensions`,
   explicit `truncate=false`, response validation, structured errors,
   capability probe) + `model_revision` and `settings_fingerprint`
   columns + dimensions-truth status.
3. **Phase D (0003):** bounded `embed_batch` with per-item fallback —
   an optimization for future reindexes and bulk imports, no longer a
   correctness dependency.
