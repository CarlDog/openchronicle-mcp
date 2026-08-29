# Ollama Repository Review — Applicable Lessons for OpenChronicle

**Status:** Research complete; verified optional-adapter defects and
proposed hardening recorded; no implementation batch approved or shipped

**Assessment date:** 2026-08-27

**Ollama snapshot:** [`ollama/ollama` commit
`f96e7aa`](https://github.com/ollama/ollama/commit/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a)

**OpenChronicle snapshot:** `main` at
`68a4eebd947963d4aa87ae1470bd0ff4d06e0774`, package
`3.0.0rc8`

## Executive conclusion

Ollama is a model runtime, while OpenChronicle is a memory data plane.
The review found no reason to restore the model execution, orchestration,
agent, or media scope removed in OpenChronicle v3. The two systems are
complementary: Ollama can supply local inference and OpenChronicle can
provide persistent cross-session memory through MCP.

The useful lessons are concentrated at the embedding-provider boundary
and in two provider-independent reliability patterns:

| Disposition | Candidate | Reason |
|---|---|---|
| Verified optional-adapter defects | Make Ollama dimensions, truncation, response validation, and structured errors truthful | OpenChronicle accepts and reports dimensions it never sends, inherits silent truncation, and trusts an unchecked response |
| Proposed correctness hardening | Identify embeddings by content revision and embedding-space fingerprint, including an Ollama manifest digest when available | A mutable model tag and a content update can both leave an old vector looking current |
| Proportionate improvement | Use bounded batch backfill with partial-failure recovery | The port and providers already support batches, but backfill performs one HTTP request per memory |
| Verified operational defect | Track provider health across search, save, and backfill; do not record a totally failed backfill as successful | Current health observes search failures only, while adapter construction performs no provider I/O |
| Separate reliability improvement | Validate a staged SQLite backup before atomic publication | Ollama verifies staged artifacts before rename; OpenChronicle currently publishes an unvalidated staged database |
| Benchmark or defer | Model changes, persistent clients, provider admission, query singleflight, `keep_alive`, and output-dimension reduction | Each is plausible, but none has evidence strong enough to justify standalone scope |
| Do not adopt | Model management, runner/GPU scheduling, chat, tools, vision, cloud routing, inference logging, and cache hierarchies | These solve model-runtime problems or create privacy and scope regressions |

This document records evidence and sequencing. It does not add any item
to the live backlog by itself. The existing
[OpenClaw memory review](0002-openclaw-memory-review.md) already records
verified retrieval defects that should precede new ranking or provider
features. In particular, Ollama strengthens that review's composite
embedding-identity proposal; it does not independently approve it.

## Scope and method

The review covered the pinned Ollama source and tests for:

- the native embedding API and official client;
- model manifests, list/show metadata, capabilities, and cache identity;
- model loading, queueing, cancellation, and lifecycle controls;
- transfer staging, integrity verification, and credential boundaries;
- operational status, logging, and concurrency patterns; and
- official embedding documentation and the current recommended models.

Those mechanisms were compared with OpenChronicle's:

- `EmbeddingPort`, OpenAI adapter, and Ollama adapter;
- embedding generation, backfill, hybrid search, and degradation paths;
- `memory_embeddings` schema and SQLite persistence behavior;
- maintenance loop, health payload, backup publication, and tests; and
- explicit v3 product boundary in
  [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) and
  [V3_PLAN.md](../V3_PLAN.md).

The local Ollama checkout was clean on `main` at the pinned commit. The
review was source-level: it did not run an Ollama model, compare retrieval
quality between models, or load-test either repository. Current production
context matters to the disposition: the NAS deployment uses OpenAI
embeddings, not Ollama. Ollama-only defects are therefore real defects in
an optional adapter, not known incidents on the live provider.

Ollama is
[MIT licensed](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/LICENSE).
Its patterns can be adapted permissively; any substantial copied portion
would still carry the required copyright and license notice. The findings
below need little or no direct code copying.

## System-boundary comparison

~~~text
Ollama
  model manifests and blobs
    -> runner selection and model loading
    -> generation or embedding inference
    -> lifecycle, queue, GPU, and transfer management
    -> native and compatibility APIs

OpenChronicle
  explicit typed memory rows
    -> canonical SQLite storage and one embedding per memory
    -> FTS5 and semantic retrieval fused with RRF
    -> MCP, REST, and CLI clients
~~~

| Dimension | Ollama | OpenChronicle | Transfer implication |
|---|---|---|---|
| Product boundary | Local/cloud model runtime and agent launcher | Persistent memory database | Borrow provider contracts, not runtime scope |
| Canonical identity | Content-addressed manifests and blobs | Memory UUID plus mutable content | Digest-based freshness is relevant to embeddings |
| Expensive resource | Loaded model and GPU/CPU runner | Provider calls and SQLite work | Only a small admission boundary may transfer |
| Retrieval role | Produces embeddings; does not own memory retrieval | Owns storage, FTS5, vector ranking, and result contracts | Ollama supplies vectors, not a search subsystem |
| Failure fallback | Request errors, queue saturation, model reload | Hybrid search degrades to FTS5 | Missing or unhealthy Ollama should remain fail-soft |
| Lifecycle owner | Pulls, loads, unloads, copies, and deletes models | Configures one embedding provider | Model lifecycle stays operator-owned |

The transfer gate is the same one used by the OpenClaw review:

1. Does the mechanism improve memory ingestion, storage, retrieval,
   portability, safety, or operation rather than agent orchestration?
2. Is there an observed defect, demonstrated consumer pain, or credible
   near-term use case?

Only mechanisms passing both questions should enter an implementation
design.

## Finding 1: embedding identity is too weak

### Ollama treats a model name as a pointer, not an identity

Ollama's list response separates the friendly model name from its
manifest digest and exposes capabilities, context length, and native
embedding length in the same descriptor:

- [`api/types.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/api/types.go#L831-L852)
- [`server/model_list_cache.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/model_list_cache.go#L322-L360)

Its inference cache includes behavior-affecting options and manifest
digest in cache freshness, coalesces concurrent cold misses, and returns a
clone so callers cannot mutate the cached object:

- [`server/model_inference_cache.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/model_inference_cache.go#L45-L113)
- [`server/model_inference_cache_test.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/model_inference_cache_test.go#L14-L120)

The important transferable principle is not the cache. It is the
freshness boundary: a mutable label is insufficient when the content or
behavior behind the label can change.

### OpenChronicle keys freshness by model string only

[`EmbeddingService.generate_for_memory`](../../src/openchronicle/core/application/services/embedding_service.py)
skips generation when the stored model string equals
`port.model_name()`. The store's stale count and semantic read path use
the same comparison:

- [`sqlite_store.py`](../../src/openchronicle/core/infrastructure/persistence/sqlite_store.py)
- [`001_initial.sql`](../../src/openchronicle/core/infrastructure/persistence/migrations/001_initial.sql)

The schema records `memory_id`, vector bytes, model, actual dimensions,
and generation time. It does not record:

- the provider;
- an Ollama manifest digest or other provider revision;
- an embedding-affecting settings fingerprint;
- the long-input policy used to prepare the text; or
- the memory content revision or hash represented by the vector.

Two distinct stale-vector cases follow.

#### Same Ollama tag, different weights

An operator can pull changed weights under the same mutable tag. New
query vectors then come from a different embedding space while existing
memory vectors still pass OpenChronicle's model-string filter. A
dimension change is likely to fail the matrix operation and trigger the
FTS5 fallback. A same-dimension change is worse: it can silently produce
meaningless semantic ranking.

This review found a deterministic trigger and a usable revision signal,
not evidence that the NAS has experienced this incident.

#### Same memory ID, different content

The existing OpenClaw review verified that a memory content update is
committed before forced re-embedding. If the provider call fails, the old
vector remains. Because its model string still matches, later backfill
can skip it indefinitely. Two concurrent updates can also finish
embedding out of order and allow the older content's vector to publish
last.

Model digest and content revision solve different problems. A complete
freshness boundary needs both.

### Proposed design boundary

An implementation ADR should define two identities:

1. **Embedding-space identity** — provider, resolved model, optional
   provider revision/digest, effective dimensions, and a canonical hash
   of every setting or input policy that changes vector semantics.
2. **Content identity** — the memory revision or a canonical hash of the
   content embedded.

A possible schema direction, not a decision, is:

| Field | Purpose |
|---|---|
| `provider` | Prevent same-named models from different providers sharing a space |
| `model` | Preserve the configured or resolved model label |
| `model_revision` | Ollama manifest digest when available; nullable for providers without one |
| `dimensions` | Continue recording the actual vector length |
| `settings_fingerprint` | Canonical identity of dimension and input-affecting policy |
| `content_hash` or `content_revision` | Bind the vector to the memory state embedded |

Vector publication should be conditional: save only if the memory still
has the content identity embedded. Search should exclude identity
mismatches, and maintenance should count them as stale and regenerate
them.

**Disposition:** promote the existing composite-identity proposal for an
ADR. Do not implement a digest-only Ollama special case; the migration
should establish one provider-independent freshness model.

## Finding 2: the Ollama request contract is not truthful

Ollama's current native request accepts `model`, scalar-or-array `input`,
`keep_alive`, `truncate`, `dimensions`, and runner options. The response
contains the resolved model, vectors, total duration, load duration, and
prompt token count:

- [official `/api/embed` reference](https://docs.ollama.com/api/embed)
- [`EmbedRequest` and `EmbedResponse`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/api/types.go#L598-L628)
- [`EmbedHandler`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/routes.go#L795-L1023)

OpenChronicle's
[`OllamaEmbeddingAdapter`](../../src/openchronicle/core/infrastructure/embedding/ollama_adapter.py)
accepts `dimensions` but sends only `model` and `input`. It then trusts
`data["embeddings"]` and normalizes each returned list.

### Dimensions are accepted and reported but never requested

The adapter defaults to 768 dimensions and returns that claim through
`dimensions()`. Health publishes it as the active dimension. The SQLite
store correctly records the actual vector length, so persistence is not
corrupted by the claim, but the operator-facing status can still be
wrong. A configured 384-dimensional model can therefore produce stored
384-dimensional vectors while health says 768.

Current adapter tests unintentionally preserve the mismatch: a test
constructs a 768-dimensional adapter, returns a three-element vector,
and accepts it as valid.

Ollama reduces a vector when a smaller `dimensions` value is requested
and renormalizes the result. A value larger than the native dimension is
effectively ignored. The client must therefore both send the requested
value and validate the actual result.

### Truncation defaults to silent prefix indexing

Ollama documents `truncate=true` as the default. When the input exceeds
the model context, the server truncates it before inference; with
`truncate=false`, it returns an error instead.

OpenChronicle omits the field, so its effective policy is silent
truncation. That conflicts with the project's established rule that a
compact or partial representation must not masquerade as full content.
It can cause semantic search to represent only a memory's prefix while
FTS5 continues to index the entire row.

A live corpus spot check on the assessment date found 817 memories, 105
longer than 4,000 characters, 11 longer than 8,000, and a maximum of
30,523 characters. Characters are not tokens and context sizes vary, so
this is evidence of exposure, not proof that an Ollama request has
truncated.

The proportionate default is `truncate=false`: fail visibly, preserve
the memory and FTS5 search path, and queue the vector for later repair.
Automatic chunking and pooling should remain a separate retrieval-design
question. A curated memory row is the current retrieval unit; silently
changing that unit is not an adapter fix.

### Responses and errors need boundary validation

The adapter does not currently validate:

- one vector per input;
- non-empty vectors;
- finite numeric values;
- consistent dimensions across a batch; or
- agreement with an explicitly requested dimension.

It also reduces every HTTP failure to `HTTP <status>`, although Ollama
returns a structured `{"error": "..."}` body. Ollama's official client
preserves the status and provider message:

- [`api/client.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/api/client.go#L36-L62)
- [official error documentation](https://docs.ollama.com/api/errors)

OpenChronicle should surface a bounded and sanitized upstream message.
That is especially important when `truncate=false`: "input exceeds
maximum context length" is actionable, while "HTTP 400" is not.

### Recommended adapter contract

- Send `dimensions` when explicitly configured.
- Send an explicit `truncate` policy, defaulting to fail-visible.
- Keep arbitrary runner `options` private until a concrete supported
  option is needed; do not expose an unchecked map.
- Validate cardinality, finiteness, consistency, and actual dimensions.
- Short-circuit `embed_batch([])` without loading the model.
- Preserve a bounded structured Ollama error and an operator hint.
- Keep OpenChronicle's provider-independent unit normalization. Ollama
  already returns L2-normalized vectors, but the redundant normalization
  is cheap and protects the dot-product-as-cosine invariant across
  providers. See the
  [official embedding guide](https://docs.ollama.com/capabilities/embeddings).

**Disposition:** verified optional-adapter defects. Correct them together
with the embedding-identity design so a dimension or input-policy change
cannot mix vector spaces.

## Finding 3: backfill bypasses the existing batch capability

[`EmbeddingPort`](../../src/openchronicle/core/domain/ports/embedding_port.py)
already defines `embed_batch`, and both OpenAI and Ollama adapters
implement it. `EmbeddingService.generate_missing` nevertheless calls
`embed()` once per candidate.

Ollama accepts an array of inputs, executes the batch, and preserves
input order by writing each result to its original index. The official
guide recommends array input for batch generation:

- [batch embedding documentation](https://docs.ollama.com/capabilities/embeddings#generate-a-batch-of-embeddings)
- [`EmbedHandler`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/routes.go#L974-L1023)

The reliable benefit is fewer OpenChronicle-to-provider HTTP round
trips. Ollama runs embedding-model inference with restricted runner
parallelism, so the design should not promise linear compute speedup.

The current corpus would turn a forced rebuild into as many as 817
provider calls. Routine backfill had only two missing vectors at the
assessment date, so the day-to-day gain is small. The useful cases are:

- schema or embedding-identity migration;
- provider or model change;
- restore and bulk import;
- recovery after an extended provider outage; and
- explicit force-reindex operations.

One failed input causes Ollama's whole HTTP batch to fail. OpenChronicle's
current loop deliberately preserves partial success. A correct batch
implementation therefore needs bounded chunks plus recovery:

1. Select a bounded chunk; do not make the entire corpus one request.
2. Call `embed_batch` and validate one result per input.
3. Save successful vectors under the content/fingerprint publication
   rule from Finding 1.
4. If the batch fails, split it or retry items individually so one bad
   memory does not discard every good result.
5. Report generated and failed counts exactly as today.

The chunk size should be measured against both supported providers. It
should not be inferred from Ollama's internal `num_batch`, which controls
runner token processing rather than the number of OpenChronicle memories
per request.

**Disposition:** provider-independent improvement. It has strongest value
after the identity migration creates a real reindex event; it is not an
urgent optimization for two missing rows.

## Finding 4: provider and maintenance health can be success-shaped

The Ollama adapter constructor performs no network I/O. Nevertheless,
[`CoreContainer.embedding_status_dict`](../../src/openchronicle/core/infrastructure/wiring/container.py)
reports `active` whenever an embedding service exists and no search
failure has been recorded.

Only search operations update `_search_failure_count` and
`_last_failure_at`. Save and backfill failures do not affect provider
health. The maintenance `embedding_backfill` handler logs generated and
failed counts but returns normally even when every candidate fails; the
maintenance loop then sets `last_outcome="ok"` and advances
`last_success_at`.

A dead provider can therefore produce all three statements at once:

- embedding status is `active`;
- a backfill generated zero vectors; and
- the backfill job's last run was successful.

That is an observability defect independent of Ollama.

### Provider-boundary status

A small recorder at the provider/service boundary should cover every
operation, not just search:

- configured but never verified;
- last successful operation and time;
- last failed operation, time, error code, and bounded message;
- consecutive failure count;
- request latency; and
- for Ollama, optional load duration and prompt token count already
  returned by `/api/embed`.

The multi-field snapshot should be updated and read coherently. Search
runs in `asyncio.to_thread`; unsynchronized individual counters can
otherwise expose a mismatched state or let an older success clear a
newer failure.

An Ollama-specific, cached, non-fatal probe can enrich that state with:

- server version;
- whether the configured model is installed;
- manifest digest;
- embedding capability;
- native and effective dimensions; and
- context length.

`/api/tags` is the best primary descriptor at the pinned revision because
it carries digest and capability metadata together. Older servers may
omit newer fields, so the client should feature-detect and fall back to
an actual vector-length check. The probe must not run synchronously on
every health request or permanently remove the adapter after a transient
startup outage.

### Maintenance outcome

- Zero candidates remains a successful no-op.
- Partial success remains a completed but degraded result with exact
  generated/failed counts.
- A total provider failure should raise so the job records `failed` and
  does not advance `last_success_at`.

**Disposition:** verified operational defect. Design the recorder once
for OpenAI and Ollama rather than adding Ollama-only health fields.

## Finding 5: validate staged backups before publication

Ollama's transfer code downloads into a temporary artifact, verifies
resumed data, checks final size and digest, deletes invalid staging, and
only then renames it into place:

- [`x/transfer/download.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/x/transfer/download.go#L283-L337)
- [`x/transfer/transfer_test.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/x/transfer/transfer_test.go#L1709-L1911)

OpenChronicle's
[`backup.py`](../../src/openchronicle/core/infrastructure/persistence/backup.py)
already uses the correct shape: SQLite's online backup API writes a
temporary file and `os.replace` publishes it atomically. It does not,
however, validate the staged database before publication.

The transferable principle is "verify the artifact before the atomic
rename," not Ollama's SHA-256 implementation. A proportional SQLite
sequence is:

1. Create the staged database with the SQLite backup API.
2. Open the staged file independently, preferably read-only.
3. Run `PRAGMA quick_check` and require `ok`.
4. Optionally verify expected schema version and core table presence.
5. Publish with `os.replace` only after validation succeeds.
6. Run retention pruning only after the verified artifact is published.

`quick_check` is likely the right default at this deployment's size.
`integrity_check` is stronger but duplicates a more expensive scheduled
maintenance job. The failure path must preserve the previous destination
and surface the validation result.

Given the corrupt-database cutover history, this is a credible reliability
improvement, not generic defensive ceremony.

**Disposition:** ~~separate provider-independent hardening. It does not
depend on accepting any embedding work.~~ **✅ SHIPPED 2026-08-28**
(assessment rev 125): `PRAGMA quick_check` on a read-only open of the
staged file gates `os.replace`; a failing artifact is quarantined as
`<dest>.failed-quick-check` (forensic capture per the NemoClaw
review's caveat), the previous destination survives, and retention
pruning already ran only after successful publication. `quick_check`
over `integrity_check` exactly as proposed; the schema-version check
stayed optional and unadopted.

## Conditional mechanisms

### Persistent HTTP client

Ollama's official client owns and reuses an HTTP client. OpenChronicle's
Ollama adapter calls module-level `httpx.post`, forfeiting connection
pooling. A persistent `httpx.Client` is reasonable when the adapter is
otherwise revised, but it adds a close lifecycle to `CoreContainer` and
is not a standalone capability.

**Trigger:** measured connection setup cost or implementation of batch
and probe operations that make an owned client the simpler design.

### Bounded provider admission

Ollama's scheduler uses a bounded queue, rejects saturation explicitly,
and drops canceled requests before expensive model loading:

- [`server/sched.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/sched.go#L88-L104)
- [`server/routes.go`](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/routes.go#L3107-L3118)

OpenChronicle's request-rate limiter controls arrivals, not simultaneous
provider or `to_thread` work. A small shared semaphore or bounded
admission layer could prevent interactive search, manual reindex, and
maintenance from overwhelming one provider. It should return an explicit
busy outcome rather than silently building an unbounded executor queue.

Python cannot cancel work already running inside `to_thread`; admission
can only prevent a canceled waiter from starting. The full Ollama
scheduler, runner reference counts, VRAM eviction, and OOM reload state
machine do not transfer.

**Trigger:** observed overlap, queue growth, or provider saturation.

### Query-vector singleflight or cache

Every semantic search currently embeds its query anew. Ollama's internal
singleflight pattern shows how concurrent identical work can be
coalesced. A small cache could be safe if keyed by exact query plus the
embedding-space fingerprint, caches successful vectors only, and returns
immutable data or copies.

Arbitrary search text is an unbounded keyspace, and no current evidence
shows repeated concurrent identical queries. Caching full search results
or the embedding matrix would also require an explicit storage generation
to remain correct.

**Trigger:** instrumentation showing a material repeated-query rate and
provider latency.

### `keep_alive`, timeout splitting, and inference telemetry

Ollama exposes model keep-alive control and reports cold-load duration.
OpenChronicle's single 30-second timeout can theoretically expire during a
legal cold load. No observed latency incident justifies new configuration
today.

If cold starts become visible, prefer separate connect/read timeouts and
an on-demand diagnostic before exposing `keep_alive`. Preserve the
server's default unless an operator opts in; pinning a model indefinitely
would be unfriendly on a shared host.

### Embedding-model benchmark

Ollama's current documentation recommends `embeddinggemma`,
`qwen3-embedding`, and `all-minilm`. OpenChronicle's optional adapter
defaults to `nomic-embed-text`. An upstream recommendation is not enough
to change a retrieval default.

A useful benchmark would build a small gold query set from real memories
and compare:

- recall at k and rank of the known relevant memory;
- hybrid versus semantic-only behavior;
- long-input failures under the chosen policy;
- index and query latency, including cold load;
- actual dimensions and memory/storage cost; and
- full-reindex duration.

**Trigger:** a real plan to move the NAS from OpenAI to local Ollama, or
evidence that current retrieval quality is inadequate.

## Explicit non-fits and regressions to avoid

### Model runtime and agent breadth

Do not add:

- chat, generation, thinking, tool calling, vision, or web search;
- agent sessions, prompt construction, or an Ollama launch wrapper;
- model pull, create, copy, recommendation, or delete operations;
- GPU discovery, VRAM accounting, runner loading, eviction, or OOM
  recovery; or
- cloud model routing or multi-provider voting.

These are coherent Ollama responsibilities and explicit OpenChronicle
non-goals. A missing model should produce an actionable diagnostic and an
operator command, not make OpenChronicle a model manager.

### Cache hierarchy

Ollama's model list cache, inference cache, and stale-while-revalidate
show cache are carefully implemented because model metadata and loading
are expensive. OpenChronicle's memory and project reads are cheap local
SQLite operations. Adding stale copies would create invalidation and
sensitive-data-retention problems without a corresponding cost.

The transferable part is exact freshness identity, not the cache layers.

### Hidden content transformation

Do not replace Ollama's silent prefix truncation with silent chunking or
pooling. Chunking changes the retrieval unit, scoring interpretation, and
publication metadata. It needs a benchmark and a clear caller-visible
contract.

### Arbitrary provider options

Do not expose Ollama's free-form `options` map as a public OpenChronicle
configuration surface. Unknown options may be ignored by Ollama, and
several change inference behavior enough to require a new fingerprint.
Add one typed option only when a demonstrated use case needs it.

### Request-body debug logging and diagnostics exposure

Ollama can log complete inference request bodies and replayable curl
commands. Copying that behavior would duplicate private memory content on
disk. File mode `0600` limits readership but does not make the duplicate
safe or useful.

OpenChronicle should also retain its exact Host-header allowlist and
curated, masked configuration reporting. Ollama's more permissive local
host policy and broad environment logging are not improvements for this
deployment.

### SDK or compatibility-layer replacement

The existing direct adapter is small. Adding the Ollama Python SDK solely
to replace one HTTP call would add a dependency without removing the need
for OpenChronicle-specific validation, fingerprinting, status, or error
translation. Switching to the OpenAI-compatible endpoint would lose the
native truncation, model metadata, and metrics that make the boundary
truthful.

Stay on `/api/embed`.

## Recommended sequencing

The findings should not all become one batch. Their dependency order is:

### Phase A: preserve existing priorities

Finish or explicitly disposition the verified retrieval-integrity work in
[the OpenClaw review](0002-openclaw-memory-review.md): eligibility before
candidate limits, stale content vectors, truthful result budgets, and the
demonstrated filtered-recency need. Ollama does not replace those findings.

### Phase B: embedding correctness ADR

Define:

- embedding-space fingerprint fields and canonicalization;
- content identity and compare-and-swap publication;
- stale-row eligibility and backfill behavior;
- migration behavior for existing rows; and
- status representation for configured, effective, and stored dimensions.

This phase is a design decision because it changes persistence semantics
and requires a full reindex.

### Phase C: provider contract implementation

After Phase B is accepted:

- send and validate Ollama dimensions;
- make truncation explicit;
- preserve structured error details;
- validate all returned vectors;
- add cached, non-fatal capability discovery; and
- make provider status cover every operation.

The implementation should remain provider-independent above the adapter
boundary.

### Phase D: bounded reindex path

Use `embed_batch` in bounded chunks with split or individual fallback,
content-revision checks, and exact result accounting. This phase pays for
the forced reindex introduced by Phase B.

### Independent backup hardening

Add staged `PRAGMA quick_check` validation before backup publication. It
has no dependency on Phases B-D and can ship separately.

## Test plan for any accepted implementation

### Embedding identity and publication

- Same provider/model label with a changed Ollama digest is stale.
- Same model and digest with changed dimensions or input policy is stale.
- A failed content regeneration makes the old vector ineligible and
  visible to backfill.
- A slow older update finishing after a newer update cannot overwrite the
  newer vector.
- Existing rows migrate deterministically and are either usable by an
  explicit compatibility rule or queued for reindex, never guessed.

### Ollama adapter contract

- Request bodies include the selected `dimensions` and `truncate` values.
- Empty input does not call the provider.
- Response cardinality must equal input cardinality.
- Empty, non-finite, inconsistent, or wrong-dimension vectors fail with a
  provider error.
- A structured Ollama error is surfaced with bounded content and no
  credential-bearing URL.
- Older `/api/tags` responses missing optional metadata degrade cleanly.

### Backfill and provider state

- A successful batch saves every vector in input order.
- One bad item does not discard good items in the same initial chunk.
- A total provider failure marks the maintenance job failed and does not
  advance `last_success_at`.
- Partial failure reports exact counts and a degraded provider snapshot.
- Concurrent success and failure produce one coherent health snapshot.

### Backup publication

- A staged database that fails `quick_check` never replaces the previous
  destination.
- Validation failure prevents retention pruning.
- A valid staged database publishes atomically and remains readable from
  a new connection.

Use deterministic fakes, barriers, and events for concurrency tests.
Ollama's own queue integration test is skipped and several scheduler tests
are timing-sensitive; those files are useful design evidence, not a test
style OpenChronicle should copy.

## Decision ledger

| Candidate | Status after review | Evidence needed to change status |
|---|---|---|
| Explicit dimensions/truncation and response validation | Verified adapter defect | Implementation batch approval |
| Structured Ollama errors | Verified adapter defect | Implementation batch approval |
| Boundary-wide provider health and all-failed backfill outcome | Verified operational defect | Implementation batch approval |
| Composite embedding identity plus content revision | Proposed hardening; promote to ADR | ADR approval and migration/reindex plan |
| Bounded batch backfill | Proportionate improvement | Preferably lands with an identity-driven reindex |
| Staged backup validation | **✅ Shipped 2026-08-28** (rev 125) | Finding 5 records the closeout |
| Cached capability probe | Proposed component of provider-health work | Provider-health design approval |
| Persistent HTTP client | Conditional implementation detail | Adapter lifecycle work or measured connection cost |
| Provider admission | Conditional | Observed overlap, queueing, or saturation |
| Query-vector cache/singleflight | Benchmark only | Repeated-query and latency measurements |
| Change default Ollama embedding model | Benchmark only | Gold-set retrieval results |
| `keep_alive` and new timeouts | Conditional | Measured cold-load failures or latency |
| Full Ollama runtime/model lifecycle | Rejected | Would require an explicit reversal of the v3 product boundary |
| Request-body debug logging | Rejected | Privacy regression; no reasonable trigger identified |

## Source map

### Ollama

- [Repository at the reviewed commit](https://github.com/ollama/ollama/tree/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a)
- [Embedding request and response types](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/api/types.go#L598-L628)
- [Embedding handler](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/routes.go#L795-L1023)
- [Official embedding API](https://docs.ollama.com/api/embed)
- [Official embedding guide](https://docs.ollama.com/capabilities/embeddings)
- [Official client error handling](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/api/client.go#L36-L62)
- [Model list and digest metadata](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/api/types.go#L831-L852)
- [Digest-aware inference cache](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/model_inference_cache.go#L45-L113)
- [Verified staged download publication](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/x/transfer/download.go#L283-L337)
- [Scheduler admission](https://github.com/ollama/ollama/blob/f96e7aa0513b9973a0ccc71be414c2ecb9d65b1a/server/sched.go#L88-L104)

### OpenChronicle

- [Ollama embedding adapter](../../src/openchronicle/core/infrastructure/embedding/ollama_adapter.py)
- [OpenAI embedding adapter](../../src/openchronicle/core/infrastructure/embedding/openai_adapter.py)
- [Embedding port](../../src/openchronicle/core/domain/ports/embedding_port.py)
- [Embedding service](../../src/openchronicle/core/application/services/embedding_service.py)
- [SQLite embedding persistence](../../src/openchronicle/core/infrastructure/persistence/sqlite_store.py)
- [Initial schema](../../src/openchronicle/core/infrastructure/persistence/migrations/001_initial.sql)
- [Container health payload](../../src/openchronicle/core/infrastructure/wiring/container.py)
- [Maintenance jobs](../../src/openchronicle/core/infrastructure/maintenance/jobs.py)
- [Maintenance loop](../../src/openchronicle/core/application/services/maintenance_loop.py)
- [SQLite backup publication](../../src/openchronicle/core/infrastructure/persistence/backup.py)
- [Embedding adapter tests](../../tests/test_embedding_adapters.py)
- [OpenClaw memory review](0002-openclaw-memory-review.md)
