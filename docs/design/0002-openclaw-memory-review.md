# OpenClaw Memory Design Review — Applicable Lessons for OpenChronicle

**Status:** Research complete; verified defects recorded as unscheduled
tech debt; no implementation batch approved or shipped

**Assessment date:** 2026-08-27

**OpenClaw snapshot:** [`openclaw/openclaw` commit
`894f254`](https://github.com/openclaw/openclaw/commit/894f25427e28732f029dc33f4e5ed913f8db9cca)

**OpenChronicle snapshot:** `main` at
`68a4eebd947963d4aa87ae1470bd0ff4d06e0774`, package
`3.0.0rc8`

## Executive conclusion

OpenClaw contains several strong memory-engineering patterns, but its
memory subsystem is part of a complete assistant runtime rather than a
standalone memory service. The comparison supports OpenChronicle's
existing boundary: keep OpenChronicle a focused memory data plane and
leave sessions, prompt construction, model execution, scheduling, and
agent orchestration to clients.

The findings divide into six dispositions:

| Disposition | Candidate | Reason |
|---|---|---|
| Verified defect | Filter project/tag eligibility before semantic top-N and tag eligibility before the FTS limit; invalidate stale embeddings after content updates; make response budgets truthful | Current code can omit eligible results, rank stale content, or violate the documented bound |
| Demonstrated consumer gap | Filtered chronological listing | A Mnemosyne workflow currently requires a compact full-project scan plus individual reads |
| Proposed hardening | Composite embedding identity | Strong upstream pattern and plausible mismatch, but no OpenChronicle production incident |
| Pilot or benchmark | Read-only stale/duplicate audit and MMR diversity reranking | Corpus drift exists, but automatic consolidation and reranking are not yet justified |
| Conditional | Import lineage, structured trust/provenance, supersession, whole-search deadlines, and shadow-index publication | Each requires a specific future ingestion, lifecycle, latency, or materialized-index need |
| Do not adopt | Dreaming in core, active-recall agents, transcripts, standing intents, Markdown canonical storage, filesystem watchers, Gateway/runtime breadth, and global temporal decay | These violate the v3 memory-only boundary or solve problems OpenChronicle does not have |

This document records evidence and recommended sequencing. The verified
defects and demonstrated consumer gap are linked into
[`V3_PLAN.md`](../V3_PLAN.md) as unscheduled tech debt. Every other
candidate requires an explicit accepted status in V3_PLAN or a later
implementation ADR/design; this review cannot approve itself.

## Scope and method

The review covered:

- OpenClaw's current memory documentation, implementation, schemas,
  tests, and issue history at the pinned commit.
- OpenChronicle's current schema, ports, search implementation, MCP,
  REST, and CLI contracts, cross-checked against the
  [MCP specification](../integrations/mcp_server_spec.md) and
  [stability policy](../api/STABILITY.md).
- Current OpenChronicle usage, including a concrete Mnemosyne recency
  query and a spot check against the live memory corpus.
- Architectural fit against OpenChronicle's explicit v3 scope in
  [the v3 plan](../V3_PLAN.md) and
  [architecture document](../architecture/ARCHITECTURE.md).

At the assessment date, the pinned OpenClaw `main` snapshot was ahead
of its [latest published release](https://github.com/openclaw/openclaw/releases/latest).
It is therefore design evidence, not proof that every behavior is in a
stable release. The review did not run comparative load benchmarks and
made no code changes.

OpenClaw is [MIT licensed](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/LICENSE),
so legal reuse is permissive. Architectural reuse is a different
question: the locally sparse-checked memory-related subtree at the
pinned snapshot contained roughly 49,000 production lines and 58,000
test lines, several times larger than OpenChronicle's entire source
tree. Direct transplantation would be disproportionate.

## System-boundary comparison

OpenClaw is a TypeScript assistant Gateway. Memory is a plugin
capability that participates in sessions, prompt construction, cron,
model calls, compaction, and runtime lifecycle. Its broad data path is:

~~~text
Markdown and session sources
  -> safe scan, hashing, chunking, and provenance
  -> derived SQLite FTS and vector index
  -> hybrid merge
  -> decay, importance, project affinity, and MMR
  -> visibility filtering and runtime prompt injection
~~~

OpenChronicle is a Python memory service:

~~~text
Explicit typed memory rows
  -> canonical SQLite storage and one embedding per memory
  -> FTS5 and semantic retrieval fused with RRF
  -> MCP, REST, and CLI clients
~~~

| Dimension | OpenClaw | OpenChronicle | Transfer implication |
|---|---|---|---|
| Product boundary | Full single-operator assistant runtime | Cross-client memory data plane | Runtime features do not belong in OpenChronicle |
| Canonical content | Markdown and eligible session sources | SQLite memory rows | Watchers and rebuild machinery solve an OpenClaw-specific problem |
| Retrieval unit | Overlapping chunks from files and transcripts | One curated memory row | OpenClaw's diversity problem may be weaker in OpenChronicle |
| Mutation model | Agent flushes and scheduled model-assisted consolidation | Explicit CRUD and caller-side synthesis | Borrow review safety, not model execution |
| Trust model | Runtime-classified owner, agent, untrusted, and system origins | Transport-oriented `source` field | Structured trust requires a real authenticated ingestion boundary |
| Index lifecycle | Derived index with rebuild and publication races | Canonical row plus per-row embedding | Shadow publication only fits a future materialized vector index |

OpenClaw's high-level design is documented in its
[memory architecture](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/memory-architecture.md).
Its memory plugin composition is visible in
[`extensions/memory-core/index.ts`](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/index.ts)
and
[`manager.ts`](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/manager.ts).

## Transfer gate

An OpenClaw feature should enter OpenChronicle only when both answers
below are yes:

1. Does it improve memory ingestion, storage, retrieval, portability,
   safety, or operation rather than agent orchestration?
2. Is there an observed defect, demonstrated consumer pain, or credible
   near-term use case?

Features passing both gates should then prefer:

- reuse of the existing SQLite, port, and maintenance boundaries;
- deterministic behavior before model-assisted behavior;
- preview and explicit confirmation before destructive mutation;
- measurable exit criteria;
- small, reversible changes;
- no new core dependency without a demonstrated scale or capability
  threshold.

## Finding 1: retrieval correctness precedes new ranking features

Several OpenChronicle behaviors can currently omit valid results or
rank against stale data. These should be corrected before adding
temporal weighting, importance, MMR, or other ranking policy.

### Semantic eligibility is applied after global candidate selection

[`EmbeddingService._semantic_search`](../../src/openchronicle/core/application/services/embedding_service.py)
loads and ranks the global embedding set, retains a bounded top-N, and
then filters selected memories by project and tags. Unrelated vectors
can consume the candidate window, causing false negatives within the
requested scope. This does not leak other projects, but it can
underfill or miss the best eligible results.

**Recommendation:** establish the eligible memory IDs before vector
top-N selection. At the current corpus size, filter the in-memory
matrix by eligible IDs before the NumPy operation. A future vector
index should apply the equivalent predicates within or immediately
before candidate selection.

### Keyword tag filtering uses a lossy over-fetch heuristic

[`SqliteStore.search_memory`](../../src/openchronicle/core/infrastructure/persistence/sqlite_store.py)
retrieves at most `limit * 4` FTS matches and then applies tag
filtering in Python. Valid tagged results beyond that window are never
considered.

**Recommendation:** push exact tag predicates into SQL before
`LIMIT` and `OFFSET`. SQLite JSON1's `json_each` is sufficient if
it is guaranteed or feature-detected. A normalized tag table becomes
worth considering only if query complexity or scale outgrows JSON1.

### A failed content re-embedding can leave a permanently stale vector

[`UpdateMemory.execute`](../../src/openchronicle/core/application/use_cases/update_memory.py)
commits the new content before attempting a forced re-embedding. If the
provider fails, the old embedding remains. The scheduled backfill sees
an existing row for the current model and skips it, so semantic search
can continue ranking the old content indefinitely.

**Recommendation:** either delete/invalidate the vector whenever
content changes or persist a content hash/version with every embedding
and treat mismatches as missing. Whether save/update responses should
also expose per-write embedding state is a separate API-design
question, not required to repair the correctness defect.

### Documented limits are not final response limits

Search returns up to `top_k` ranked memories plus a separate matching
pin budget. The MCP contract currently calls `top_k` the maximum
number of results, so the documented bound and actual response can
disagree. `context_recent.memory_limit` has the same semantic issue
when `query` is supplied and it delegates to search.
In addition,
[`include_pinned`](../../src/openchronicle/interfaces/cli/commands/memory.py)
is available to the CLI/use case but absent from MCP and REST even
though the MCP documentation tells callers to use it.

**Recommendation:** choose and document one contract:

- make `top_k` a total response budget that includes floated pins; or
- name it explicitly as a ranked-result budget and expose the separate
  pin budget and visibility control consistently on every surface.

Query-aware pinning itself is valuable. The defect is ambiguity about
the final response size and controls.

## Finding 2: add true filtered-recency enumeration

This is the clearest new capability with a demonstrated consumer.

A Mnemosyne continuation workflow needs the newest memories tagged
`scene` in one project while excluding `validation:errors`.
Currently:

- `memory_search(tags=...)` filters but relevance-ranks;
- `memory_list(project_id=...)` is chronological but cannot filter
  tags;
- pinned rows float ahead of pure chronology;
- obtaining full content requires a compact full-project scan followed
  by individual `memory_get` calls.

The existing MCP listing contract is in
[`interfaces/mcp/tools/memory.py`](../../src/openchronicle/interfaces/mcp/tools/memory.py).

A possible additive shape is:

~~~python
memory_list(
    project_id=project_id,
    tags=["scene"],                    # require all
    exclude_tags=["validation:errors"],  # exclude any
    order_by="created_at",             # pure chronology
    include_pinned=False,              # optional visibility control
    limit=20,
    compact=True,
)
~~~

This is an illustrative contract, not an approved API. The important
semantics are:

- keep enumeration distinct from relevance search;
- apply tag, exclusion, project, and pin predicates before pagination;
- provide an order that does not implicitly float pins;
- retain the current list behavior as the default if an additive change
  is preferred;
- test that eligible rows beyond an early ineligible window still
  appear.

## Finding 3: composite embedding identity is proposed hardening

This is OpenClaw's strongest directly transferable engineering pattern.

OpenClaw persists an index identity that covers provider, model,
provider-specific embedding settings, vector dimensions, enabled
sources, chunk parameters, tokenizer, and classifier versions. Search
rejects an absent or incompatible identity rather than mixing vector
spaces. See
[`manager-reindex-state.ts`](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/manager-reindex-state.ts)
and
[`memory-search-tool-query.ts`](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory-search-tool-query.ts).

OpenChronicle currently scopes persisted vectors primarily by model.
Two providers or endpoints can share a model label while producing
different dimensions or incompatible vector spaces.

The proportional OpenChronicle design has two layers:

- an embedding-space identity containing provider, model, actual
  dimensions, and a canonical fingerprint of embedding-affecting
  settings;
- a per-row memory-content hash or version that proves which content
  produced the stored vector.

Health and maintenance status should report:

- the active identity;
- mismatched and stale row counts;
- whether a rebuild is required.

The existing force-backfill path can remain the migration mechanism.
OpenClaw's source, chunker, and tokenizer identity fields should not be
copied unless OpenChronicle later adds file chunking.

## Finding 4: pilot memory hygiene, not Dreaming

The current corpus has visible drift. The review found two stale pinned
records, `daa33596-c357-4a08-83c5-93f600f54012` and
`5a0208d7-40cd-43df-9212-3dd16e97bfcb`, describing rc3 as the current
state while the project is at rc8. Several overlapping milestone and
deployment summaries also exist.

That evidence supports a read-only audit, not automatic consolidation.
An initial CLI or offline report could identify:

- old pins tagged `handoff`, `current-state`, or `snapshot`;
- highly similar pairs using existing embeddings;
- multiple memories purporting to be the active current state.

Existing `memory_update`, `memory_pin`, and confirmed deletion can
perform reviewed cleanup. The audit should not mutate data.
Content-identity checks and import-batch analysis become possible only
after the proposed embedding-identity or lineage fields exist.

OpenClaw's
[User Model](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/user-model.md)
and
[Dreaming design](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/dreaming.md)
offer useful mutation-safety ideas if recurring manual pain eventually
justifies more:

- preview structured operations rather than accepting replacement prose;
- rehydrate and fingerprint live sources before applying;
- preserve preimages and lineage;
- validate the proposed result;
- abort when concurrent changes invalidate the proposal;
- fall back to append-only behavior when a safe rewrite is impossible.

The model-driven scheduler and consolidation agent do not belong in
OpenChronicle. If the audit proves insufficient, the next proportional
step would be a caller-driven `memory_merge` or
`memory_supersede` operation with preview, explicit confirmation,
and lineage.

## Finding 5: benchmark MMR before adopting it

OpenClaw applies Maximal Marginal Relevance after initial retrieval to
prevent near-duplicate chunks from monopolizing the top results. Its
implementation operates on a bounded candidate pool with local token
similarity:

- [memory-search design](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/memory-search.md)
- [MMR implementation](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/mmr.ts)

OpenClaw has a concrete issue report with useful counts. In
[issue #19760](https://github.com/openclaw/openclaw/issues/19760), one
large transcript produced 125 overlapping chunks and occupied a
disproportionate share of top-three results.

OpenChronicle stores one curated memory and one embedding per row. A
spot check against current story memory did not show the same result
collapse, so OpenClaw's severity cannot be assumed.

Before exposing MMR or changing defaults:

1. Build an offline query set around known overlapping deployment,
   milestone, decision, and story memories.
2. Compare current RRF with MMR over a bounded 3-4x candidate pool.
3. Measure duplicate rate and human-judged relevance in the top-N.
4. Test text/Jaccard and embedding-cosine inter-result similarity.
5. Keep floated pins and exact phrase matches outside reranking first.
6. Preserve the original RRF and channel scores; MMR changes ordering,
   not confidence.

Do not copy OpenClaw's lambda, candidate multiplier, or tokenization
policy without corpus-specific evidence.

## Finding 6: separate lineage from trust provenance

OpenChronicle's `source` currently describes the interface that
created a memory, such as `mcp` or `api`, rather than the origin or
authority of the claim. The MCP save path hardcodes that transport
source in
[`interfaces/mcp/tools/memory.py`](../../src/openchronicle/interfaces/mcp/tools/memory.py).
At the dated 2026-08-27 global snapshot, 786 of 816 memories reported
`source=mcp`, demonstrating that the field has little semantic value
for lineage.

Two concerns should remain separate.

### Import lineage

If Git onboarding and curated external imports need targeted rollback,
a minimal lineage seam could contain:

- `created_via`;
- `source_ref` or external identifier;
- `import_batch_id`;
- `observed_at`.

That would allow previewing and deleting a bad attributable batch
without depending on ad hoc tags.

### Trust classification

OpenClaw records owner, agent, untrusted, and system origins, session
kind, observation time, and supersession metadata in its
[provenance schema](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/packages/memory-host-sdk/src/host/memory-schema-provenance.ts).
This protects automatic ingestion and runtime injection paths.

OpenChronicle's explicit-save model currently avoids most of that
hazard. An unauthenticated caller also cannot create trustworthy
provenance merely by labeling its own write `owner`. A real trust
boundary requires authenticated client identity or server-side
classification.

Therefore:

- consider batch lineage only when import rollback becomes recurring
  pain;
- require structured provenance before adding automatic transcript,
  crawler, or tool-output ingestion;
- treat caller-provided origin as an assertion, not verified trust;
- do not add a security-flavored enum that the server cannot enforce.

OpenClaw's issue history shows the underlying risk is real in automatic
ingestion systems: persistent prompt injection
([#12524](https://github.com/openclaw/openclaw/issues/12524)), replayed
historical commands
([#68751](https://github.com/openclaw/openclaw/issues/68751)), and
transport metadata promoted into durable memory
([#67442](https://github.com/openclaw/openclaw/issues/67442)).

## Finding 7: retain two lifecycle patterns for future use

### Whole-search deadline

OpenClaw wraps synchronization, query embedding, and retrieval in one
deadline with cancellation propagation:
[`search-deadline.ts`](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/search-deadline.ts).

OpenChronicle has provider timeouts, but a deadline around the complete
operation could bound database, vector calculation, fallback, and
serialization work. This is hardening, not a current demonstrated
incident. Add it only when corpus growth, overloaded SQLite, or client
cancellation produces observable hangs.

Do not move index maintenance into the request path. OpenClaw
[issue #112196](https://github.com/openclaw/openclaw/issues/112196)
shows search-time synchronization consuming the deadline and obscuring
provider health. OpenChronicle's background backfill is the better
default.

### Shadow-index publication

OpenClaw builds full indexes in a shadow SQLite database and publishes
them only after an optimistic revision check. Failed or stale builders
cannot overwrite the live index:

- [shadow publication](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/manager-db.ts)
- [rebuild recovery](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/manager-sync-ops.ts)

OpenChronicle's current per-memory vectors do not justify this
machinery. Revisit it only if `sqlite-vec`, bulk dimension
migrations, or offline full-index construction introduces a
materialized index with long rebuilds.

## Existing OpenChronicle choices that the comparison validates

### Keep SQLite canonical

OpenClaw's mutable Markdown plus derived-index design has been
associated with historical issue reports covering missing index
identity, request-path rebuilds, and empty results despite apparently
populated FTS/vector tables:

- [#106239](https://github.com/openclaw/openclaw/issues/106239)
- [#112196](https://github.com/openclaw/openclaw/issues/112196)
- [#46671](https://github.com/openclaw/openclaw/issues/46671)

OpenChronicle's transactional SQLite store is an advantage. It should
not adopt Markdown as canonical storage or add filesystem watchers.

### Keep RRF as the fusion primitive

OpenClaw's weighted score merge is reasonable inside its policy stack,
but OpenChronicle's RRF avoids treating BM25 and cosine as calibrated on
the same numeric scale. MMR, if justified, should rerank a candidate
pool without replacing RRF or relabeling rank-fusion scores as
confidence.

### Keep explicit capture and caller-side synthesis

OpenChronicle intentionally removed sessions, conversation storage, and
the embedded LLM. Explicit capture substantially reduces the automatic
ingestion and replay hazards that forced OpenClaw to build provenance
tainting, session tombstones, flush gates, and consolidation controls.

### Keep degradation and health signals

OpenChronicle already degrades hybrid retrieval to FTS5 on provider
failure and reports embedding coverage, a model-mismatch stale-vector
count, FTS5 activity, package/schema versions, and maintenance
degradation. The current stale count does not detect a vector generated
from older content under the same model. These signals still cover much
of the operator-facing value in OpenClaw's diagnostics without its
index-manager complexity.

## Explicit non-fits

The following capabilities should remain outside OpenChronicle unless
the product boundary changes:

| OpenClaw capability | Why it does not fit |
|---|---|
| Gateway, channels, devices, model router, and session runtime | Recreates the v2 orchestrator that v3 deliberately removed |
| Automatic session/transcript ingestion | Reintroduces conversation storage, privacy scope, replay, and poisoning risks |
| Pre-compaction memory flush | Only the client/runtime can observe context-window pressure |
| Active-recall subagents | Model orchestration rather than storage or retrieval |
| Standing intents, cron triggers, cooldowns, and fire budgets | Prospective action execution belongs in a client or automation runtime |
| Dreaming or LLM consolidation in core | Violates the no-LLM boundary; language judgment belongs to callers |
| `MEMORY.md` and `USER.md` as canonical stores | Replaces typed transactional state with mutable files and a derived index |
| Filesystem watching and search-time reindexing | Solves OpenClaw's file-backed architecture and adds race/failure paths |
| Global temporal decay or TTL | Old decisions and conventions can remain authoritative indefinitely |
| OpenClaw's importance and ranking constants | Corpus-specific policy without an OpenChronicle consumer |
| Multimodal indexing, local GGUF, or broad provider parity | No demonstrated need and significant dependency/operations cost |
| Plugin or interchangeable memory-backend architecture | OpenChronicle already has ports and intentionally removed its plugin system |

## Confidence register

| Conclusion | Confidence | Basis and limit |
|---|---|---|
| Semantic and FTS filter-after-limit behavior can omit eligible results | High | Verified directly in current OpenChronicle code; adversarial regression tests are still needed |
| Content updates can leave stale embeddings after provider failure | High | Verified directly across update and backfill paths |
| Filtered chronological listing is a real consumer need | High | Observed in a Mnemosyne workflow, with a multi-call/full-scan fallback |
| Composite embedding identity is worthwhile hardening | Medium-high | Strong OpenClaw implementation precedent and a plausible OpenChronicle mismatch; no known production incident yet |
| Read-only hygiene reporting would find useful work | Medium-high | Stale current-state pins and overlapping milestones were observed; the value of a permanent tool is unmeasured |
| MMR would improve OpenChronicle retrieval | Medium-low | Strong OpenClaw evidence for transcript chunks, but only limited OpenChronicle duplication evidence |
| Import lineage or supersession is needed now | Low | Useful future capability, but existing explicit updates and tags may remain sufficient |
| OpenClaw issue reports describe current upstream defects | Not asserted | Issues are historical failure-mode evidence only; the pinned code may already contain fixes |

## Recommended sequence

This sequence is a recommendation, not a commitment.

### Candidate batch A: retrieval correctness

**✅ SHIPPED IN FULL 2026-08-28** (assessment revs 120-124, one commit
per finding, after a validation pass re-confirmed every claim at HEAD):

- ~~filter project/tag eligibility before semantic top-N~~ — rev 121,
  via a new `eligible_memory_ids` store primitive sharing the ranked
  search's clause builders;
- ~~filter tags in SQL before FTS pagination~~ — rev 120, JSON1
  `json_each` predicate on both branches (and the fallback's 200-row
  window, the same defect shape this review had not separately named);
- ~~invalidate or version embeddings after content changes~~ — rev 122,
  the invalidate option: `delete_embedding` on every content change
  before re-embedding (the hash/version option folded into the
  embedding-identity ADR, which also owns the concurrent-update race);
- ~~reconcile total-result and pin budgets~~ — rev 123, the operator
  chose the total-budget contract: one combined stream bounded by
  `top_k`, paginated by `offset`;
- ~~expose pin visibility controls consistently~~ — rev 124,
  `include_pinned` on MCP + REST by operator decision (additive/MINOR;
  schema snapshot regenerated);
- ~~add adversarial tests where valid matches sit beyond the former
  global or 4x candidate window~~ — landed with each item.

### Candidate batch B: read-surface completion

- add tag and exclude-tag filtering to `memory_list`;
- add pure chronological ordering with no implicit pin float;
- keep enumeration and relevance search semantically distinct;
- verify all predicates are applied before pagination;
- pin the Mnemosyne newest-scenes use case in tests.

### Proposed hardening C: embedding identity

- persist provider, model, dimensions, settings fingerprint, and
  content hash;
- reject or degrade safely on identity mismatch;
- expose mismatch counts and rebuild need in health;
- route recovery through the existing backfill mechanism.

### Experiment D: corpus hygiene and diversity

- ship a read-only stale-pin/duplicate report first;
- create an offline retrieval evaluation set;
- benchmark MMR without changing defaults;
- consider supersession or caller-driven merge only if reviewed cleanup
  remains recurring work.

### Conditional architecture work

- import lineage before batch rollback becomes necessary;
- trust provenance before any automatic ingestion;
- whole-search deadlines after a measurable latency/cancellation need;
- shadow publication with a future materialized vector index.

## Decision triggers

| Candidate | Trigger to promote | Evidence required |
|---|---|---|
| MMR | Duplicate memories repeatedly crowd out distinct relevant results | Offline query suite shows better top-N relevance/diversity without harming exact or pinned hits |
| Supersession | Reviewed cleanup repeatedly finds conflicting active memories that in-place update cannot represent safely | Concrete corpus examples and desired default visibility semantics |
| Import lineage | A bad import or Git-onboard batch needs targeted rollback | At least one real batch-cleanup incident or recurring manual tag recovery path |
| Structured trust | Automatic web, transcript, crawler, or tool-output ingestion is proposed | Authenticated or server-classified origin design precedes ingestion |
| Whole-search deadline | Search latency or cancellation exceeds client bounds outside provider calls | Timings identify the non-provider stages and a safe timeout policy |
| Shadow index | A materialized vector index requires long or failure-prone rebuilds | Rebuild concurrency and availability requirements are documented |
| Vector extension | NumPy full-table scanning crosses an observed latency or memory ceiling | Corpus-size benchmark, not an assumed scale problem |

## Source index

### OpenClaw primary sources

- [Repository](https://github.com/openclaw/openclaw)
- [Pinned review commit](https://github.com/openclaw/openclaw/commit/894f25427e28732f029dc33f4e5ed913f8db9cca)
- [README and product boundary](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/README.md)
- [Memory architecture](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/memory-architecture.md)
- [Memory search](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/memory-search.md)
- [Dreaming](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/dreaming.md)
- [User model](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/docs/concepts/user-model.md)
- [Provenance schema](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/packages/memory-host-sdk/src/host/memory-schema-provenance.ts)
- [Hybrid retrieval](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/hybrid.ts)
- [MMR](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/mmr.ts)
- [Index identity](https://github.com/openclaw/openclaw/blob/894f25427e28732f029dc33f4e5ed913f8db9cca/extensions/memory-core/src/memory/manager-reindex-state.ts)

### OpenChronicle sources

- [Current-state assessment](../CODEBASE_ASSESSMENT.md)
- [v3 plan and live backlog](../V3_PLAN.md)
- [Architecture](../architecture/ARCHITECTURE.md)
- [Memory model](../../src/openchronicle/core/domain/models/memory_item.py)
- [Embedding service](../../src/openchronicle/core/application/services/embedding_service.py)
- [SQLite store](../../src/openchronicle/core/infrastructure/persistence/sqlite_store.py)
- [MCP memory tools](../../src/openchronicle/interfaces/mcp/tools/memory.py)
