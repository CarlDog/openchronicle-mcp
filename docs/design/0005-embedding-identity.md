# ADR 0005 — Composite Embedding Identity

**Status:** PROPOSED — awaiting operator acceptance; no implementation
authorized · **Date:** 2026-08-29

**Sources:** [0002 Finding 3](0002-openclaw-memory-review.md) (proposed
hardening), [0003 Finding 1](0003-ollama-repository-review.md) (promoted
this to an ADR), 0004's independent corroboration. Ratifying this ADR
unblocks 0003 **Phase C** (the Ollama adapter contract: send
`dimensions`, explicit `truncate`, response validation, structured
errors) and **Phase D** (bounded `embed_batch` reindex), which were
deliberately sequenced behind it so a dimension or input-policy change
cannot mix vector spaces mid-fix.

## 1. Problem

A stored vector's freshness is judged by ONE fact: its `model` string
equals `port.model_name()`. That single label under-determines the
vector space in three verified ways:

1. **Same label, different space.** Two providers can share a model
   label; an Ollama tag can be re-pulled with different weights; a
   provider-side `dimensions` request (or Matryoshka truncation) changes
   the space without changing the name. Same-dimension drift silently
   corrupts cosine ranking; different-dimension drift crashes the
   matmul and degrades to FTS5.
2. **Same label, different input policy.** Ollama's default
   `truncate=true` embeds only a long memory's prefix. The policy used
   is recorded nowhere, so flipping it (0003 Phase C wants
   `truncate=false`) leaves old prefix-vectors indistinguishable from
   full-content vectors.
3. **Same row, different content — the residual race.** Rev 122 closed
   the acute case (a content update now deletes the vector before
   re-embedding, so a failed re-embed leaves MISSING, never stale). What
   remains is the concurrent-update race 0003 named: two updates to one
   memory can finish embedding out of order, and the older content's
   vector publishes last. Nothing binds a vector to the content revision
   it embeds, so the loser wins silently.

None of these is a live incident on the NAS (OpenAI,
`text-embedding-3-small`, fixed 1536 dims, no request-side options).
That is exactly why the boundary should be built *now*: the migration is
cheap while one provider/one policy is true, and 0003 Phase C makes it
false.

## 2. Decision (proposed)

Two identities, judged together at every read and write of
`memory_embeddings`:

**Embedding-space identity** — "which space is this vector in":

| Field | Type | Content |
|---|---|---|
| `provider` | TEXT NOT NULL | `openai` / `ollama` / `stub` — the adapter kind |
| `model` | TEXT NOT NULL | the configured/resolved model label (existing column) |
| `model_revision` | TEXT NULL | provider revision when one exists (Ollama manifest digest); NULL for providers without one — NULL matches NULL |
| `dimensions` | INTEGER NOT NULL | actual stored vector length (existing column, already recorded as fact) |
| `settings_fingerprint` | TEXT NOT NULL | canonical hash of every embedding-affecting setting: requested dimensions, truncation policy, and any future typed option. Computed by the adapter from a sorted key=value serialization; `""`-equivalent inputs hash identically to their absence |

**Content identity** — "which content does this vector embed":

| Field | Type | Content |
|---|---|---|
| `content_hash` | TEXT NOT NULL | SHA-256 of the exact content string handed to the provider |

The service-level rules:

- **Freshness**: a stored row is *current* iff its full space identity
  equals the active port's AND `content_hash` equals the hash of the
  memory's current content. `count_stale_embeddings` and the backfill
  candidate filter both move to this predicate.
- **Search eligibility**: `list_embeddings` filters on the full space
  identity, not `model` alone. A mismatched row is invisible to
  ranking (equivalent to missing), never mixed in.
- **Conditional publication (closes the race)**: `save_embedding`
  becomes compare-and-swap — the caller passes the `content_hash` it
  embedded, and the store persists only if the memory's current content
  still hashes to it. A losing writer's vector is dropped with a log
  line, and the row stays a backfill candidate. This subsumes rev 122's
  delete-before-re-embed, which stays as belt-and-braces.
- **Health**: `embedding_status` reports the active space identity and
  splits today's `stale` into `space_mismatch` and `content_mismatch`
  counts (additive fields; `stale` remains as their sum).

## 3. Migration

One new migration (`002_embedding_identity.sql`) adds the columns.
Existing rows cannot be trusted to any identity they don't carry, and
the ratified rule is *never guess*:

- Backfill `provider` from the active provider **only if** exactly one
  provider has ever been configured on this deployment (true for the
  NAS); otherwise leave rows ineligible.
- `settings_fingerprint` and `content_hash` are **not** reconstructable
  — set them to a sentinel (`legacy`) that the freshness predicate
  treats as stale. The scheduled backfill then regenerates every row
  through the normal path (0003 Phase D's bounded `embed_batch` exists
  to make exactly this reindex cheap: ~860 rows ≈ a few bounded
  batches).
- Search treats `legacy` rows as *eligible* until their replacement
  lands (grace behavior: same-space in practice on the NAS, and the
  alternative is a semantic-search blackout for the whole reindex
  window). This grace is a one-release concession, removed when the
  reindex completes; `health` reports the remaining `legacy` count so
  completion is observable.

## 4. Non-goals (from the source reviews, kept explicit)

- No Ollama-only special case — the model applies identically to all
  providers (`model_revision` is simply NULL where no digest exists).
- No source/chunker/tokenizer identity fields (OpenClaw's extras) —
  OpenChronicle embeds whole curated rows; those fields come back only
  if file chunking ever does.
- No shadow-index publication, no cache layers, no per-write embedding
  state in save/update responses (0002 called this a separate API
  question).
- No change to the retrieval unit or silent chunking (0003's
  hidden-content-transformation non-fit).

## 5. Test plan (from 0003, binding on the implementation batch)

- Same provider/model with changed `model_revision` → stale.
- Same model+revision with changed dimensions or fingerprint → stale.
- A failed content regeneration leaves the row visible to backfill
  (already pinned by rev 122's tests; extended to the hash predicate).
- The slow-older-update race: writer A embeds content v1, writer B
  embeds v2 and publishes; A's late save is refused by compare-and-swap.
- Migration determinism: legacy rows are eligible-but-stale, counted in
  health, and fully replaced by one forced backfill in a test store.

## 6. Sequencing after acceptance

1. **Phase B (this ADR's implementation):** migration + store predicate
   - CAS publication + health fields. One commit, full reindex NOT yet
   forced.
2. **Phase C (0003):** Ollama adapter contract — request `dimensions`,
   explicit `truncate=false`, response validation, structured errors,
   cached capability probe. The fingerprint gives these changes a place
   to land without mixing spaces.
3. **Phase D (0003):** bounded `embed_batch` backfill with per-item
   fallback, then the one forced reindex that retires `legacy`.
