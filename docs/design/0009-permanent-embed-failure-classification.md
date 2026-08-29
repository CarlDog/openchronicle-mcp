# ADR 0009 — Permanent Embed-Failure Classification

**Status:** PROPOSED (rev 1, unreviewed) · **Date:** 2026-08-29 ·
**Queue:** V3_PLAN active queue item 4 · **Ships:** v3.x from `main`
(additive/MINOR) — independent of the v4 line.

## Problem

Under ADR 0005's `truncate:false` contract, a memory whose content
exceeds the embedding model's context fails **visibly** — correct and
deliberate (a silent prefix embedding must never masquerade as the
full content). But the backfill has no concept of a *permanent*
failure. Observed live finishing the v3.2.0 cutover: 9 corpus rows
exceed `nomic-embed-text`'s context; every backfill run — manual or
the 6-hourly maintenance job — retries all 9 and fails all 9, and
once they are the only stale candidates there are no successes to
reset the consecutive-failure counter, so
`embedding_status.status` reads **`degraded` forever on a healthy
system** (`failure_count` 36 and climbing when caught). This is
failure-shaped health on designed behavior — the mirror image of the
success-shaped-health defect fixed in rev 126.

Two sub-defects, one cause:

1. **Wasted, misleading retries** of failures that cannot succeed.
2. **Counter poisoning**: known-permanent failures feed the
   consecutive-failure counter that exists to detect provider
   outages.

## Key insight: permanence is SPACE- and CONTENT-scoped, never absolute

"Unembeddable" is only true relative to (provider, model, revision,
settings) × (this exact content). Switch to a 32k-context model and
the 9 rows embed fine; edit the memory shorter and it embeds fine.
Any persisted marker must therefore expire on either change — and
ADR 0005's identity machinery already expresses exactly that.

## Decision (proposed)

### 1. Classification at the adapter boundary, as a structured code

The adapters already parse upstream error bodies. A new error code
**`CONTENT_TOO_LONG`** (SCREAMING_SNAKE_CASE per convention) is
raised instead of generic `PROVIDER_ERROR` when the upstream
rejection is the over-length one:

- `ollama_adapter`: HTTP 400 whose structured error message matches
  the documented over-length rejection (`"input length exceeds the
  maximum context length"` family — matched case-insensitively on
  the stable substring `context length`; the match lives in ONE
  module-level predicate with its own unit tests, not inline).
- `openai_adapter`: the 400 `context_length_exceeded`-family error
  (OpenAI sends a machine-readable `code` — prefer it over message
  text where present).
- Classification is per-item only: a failed batch still falls to the
  existing per-item retry, and only the per-item `CONTENT_TOO_LONG`
  outcome is classified. A batch-level failure is never classified
  permanent (one over-length item poisons a batch; the isolation
  retry attributes it).

Misclassification risk is asymmetric by design: a false NEGATIVE
(unrecognized over-length message) merely preserves today's behavior
(retry forever); a false POSITIVE (transient error misread as
permanent) parks a row until its next content edit or space change.
The predicate is therefore conservative — it must match the
documented rejection shapes only, and anything else stays
`PROVIDER_ERROR`.

### 2. Persistence: a tombstone row inside the ADR 0005 identity

Migration `004_embedding_status.sql` adds to `memory_embeddings`:

```sql
ALTER TABLE memory_embeddings ADD COLUMN status TEXT NOT NULL DEFAULT 'ok';
-- 'ok'               — a real vector
-- 'content_too_long' — a tombstone: no usable vector; this content,
--                      in this space, is known unembeddable
```

On a per-item `CONTENT_TOO_LONG` failure, the backfill writes a
**tombstone**: the full ADR 0005 identity (provider, model,
`model_revision`, `settings_fingerprint`, and the `content_hash` OF
THE CONTENT THAT FAILED), `status='content_too_long'`, and an empty
vector payload. The write goes through the existing CAS publication
(refused if the content changed mid-run — then the row is simply
still a backfill candidate, which is correct). One row per memory as
today; a tombstone REPLACES whatever old-space row sat there (that
row was already search-invisible by space mismatch).

**Expiry is free, by construction:**

- Content edited → `content_hash` mismatch → the tombstone is stale
  by the existing rules → the row is a backfill candidate again.
- Provider/model/revision/settings change → space mismatch → same.
- No new expiry logic exists anywhere; the ADR 0005 matching that
  already governs vector currency governs tombstone currency.

### 3. Consumers

- **Backfill candidacy:** rows whose CURRENT-space, current-content
  match is a tombstone are excluded from `generate_missing`'s
  candidates. `memory_embed force=true` (and only force) retries
  tombstoned rows — the explicit operator override, documented in
  the tool description.
- **Search:** `list_embeddings` returns only `status='ok'` rows
  (a tombstone is not a vector; it must never enter similarity).
- **Health:** `embedding_status` gains an additive **`unembeddable`**
  count (current-space, current-content tombstones). Tombstoned rows
  are excluded from `stale`/`missing`/`space_mismatch`/
  `content_mismatch` — the disjoint-buckets rule extends by one
  bucket. The live deployment's reading becomes
  `stale: 0, unembeddable: 9, status: active`.
- **Failure counters:** a classified `CONTENT_TOO_LONG` outcome
  records NEITHER a provider failure NOR a success — it is a
  classified result, not evidence about provider health. Transient
  failures keep counting exactly as today. (Recording it as success
  would mask a genuinely degraded provider behind a stream of
  tombstone writes; recording nothing is the honest middle.)
- **Logging:** the tombstone write logs one INFO line naming the
  memory id and the actionable remedy (shorten the content, or
  switch to a larger-context model); rev-144's one-line-WARNING rule
  already covers the failure itself.

### 4. Out of scope

- Content chunking / summarize-then-embed (a feature, not a
  classification).
- Any second `status` value beyond `content_too_long`. Other
  permanent-looking failures (invalid model, auth) are provider-level
  conditions, not per-content facts, and stay in the counters where
  they belong.
- The MCP `error_code` transport gap (V3_PLAN item): `CONTENT_TOO_LONG`
  reaches REST envelopes today; MCP clients still see prose, per that
  standing item.

## Versioning

Additive throughout: a new error code, a new defaulted column
(migration 004, idempotent re-run no-op per the migrator's
savepoint/version rules), a new health field, and a documented
`force=true` behavior refinement. **MINOR**, ships from `main` in the
next v3.x tag. Deploy note: on the live NAS, the first backfill after
deploy writes 9 tombstones and health goes `active`.

## Test plan

- Adapter classification: over-length bodies → `CONTENT_TOO_LONG`
  (ollama + openai fixtures); near-miss bodies (timeouts, other
  400s) → `PROVIDER_ERROR` (the conservative-predicate guard).
- Tombstone write: identity columns + `content_hash` of the failed
  content; CAS refusal when content moved mid-run.
- Expiry by construction: content edit → row is a candidate again;
  provider/model/fingerprint/revision change → candidate again.
- Candidacy: tombstoned rows excluded from `generate_missing`;
  `force=true` retries them.
- Search: tombstones never appear in `list_embeddings` output.
- Health: `unembeddable` counted; disjointness across all five
  buckets asserted; counters unchanged by classified outcomes;
  a transient failure still increments.
- Migration 004: applies, re-runs as a no-op, `status='ok'` on all
  existing rows.
- Backfill loop: a batch containing one over-length row tombstones
  only that row and embeds the rest.

## Review history

- Rev 1: unreviewed (single-round adversarial pass planned per the
  0008 practice, sized to this ADR's smaller surface).
