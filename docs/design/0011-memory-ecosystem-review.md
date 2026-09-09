# Memory Ecosystem Review — Applicable Lessons for OpenChronicle

**Status:** Research recorded; recommendations are unscheduled proposals,
not accepted designs or implemented features.

**Assessment date:** 2026-09-08 (America/Chicago)

**OpenChronicle baseline:** `main` at
`f1ed05b936123bed105c4ed9d0867ef085238637`, package `3.3.0`, including
inspection of the existing uncommitted observability work. That working
tree is not identical to the deployed release.

**Work-item key:** `CarlDog/openchronicle-mcp#research-0011-memory-ecosystem-review`

## Conclusion

There are suitable public repositories to learn from. Basic Memory,
Graphiti, and Hindsight are the strongest references for user experience,
changing knowledge, and retrieval respectively. Mem0, Cognee, and LangMem
offer narrower lessons in mutation history, ingestion, and client-side
memory management.

The proposed product direction is **trustworthy, self-hosted memory that
humans can inspect and agents can use efficiently**. OpenChronicle already
has useful foundations: explicit writes, hexagonal boundaries, hybrid
retrieval, portable data, and recovery mechanisms. The strongest proposed
differentiator is memory with evidence and a clear lifecycle: where a
statement came from, whether it still applies, what replaced it, and why
retrieval selected it.

This is an architectural and product judgment, not a demonstrated market
ranking. The operator requested research into potential improvements,
then authorized retaining the findings for later research and development.
Neither request schedules implementation or changes existing acceptance
gates. In particular, recording this review does not accept memory history,
automatic consolidation, a new database, or a broader agent runtime.

## Standing development priority: accuracy, then responsiveness

The operator clarified during documentation on 2026-09-08:

> Speed and responsiveness is absolutely paramount as we continue
> development, second only to accuracy.

This is an adopted development priority, distinct from the unscheduled
feature proposals in this review. Accuracy comes first; speed and
responsiveness are second only to accuracy. Feature breadth is subordinate
to those priorities. The canonical rule also lives in AGENTS.md and its
byte-identical CLAUDE.md mirror.

This review applies the priority to future evaluations as follows:

- Treat request latency and responsiveness, including tail latency under
  relevant concurrent load, as first-class acceptance evidence. Throughput
  and average latency alone cannot establish a responsive service.
- Compare against the existing pipeline under declared quality and latency
  budgets. Include relevant cold/warm behavior, provider failure and fallback
  behavior when those paths change; do not require an exhaustive new matrix
  for every small or documentation-only change.
- Make costs visible before adopting reranking, graph traversal, token
  counting, extraction, or extra synchronous writes. Keep optional expensive
  mechanisms independently evaluable; moving work to the background does
  not remove its resource or consistency costs.
- Preserve the existing performance/noise gates. This preference neither
  assigns new numerical thresholds nor authorizes another benchmark cycle,
  optimization batch, release, deployment, or metrics enablement.

## Scope, evidence, and limitations

The review inspected OpenChronicle's architecture, status and planning
documents, memory model, write/update paths, serializers, context retrieval,
embedding retrieval, benchmark harness, CI installation, and Docker build.
OpenChronicle MCP recall supplied prior decisions, which were cross-checked
against the current repository where relevant.

The bounded external comparison covered six repositories, the official MCP
memory reference server, and the LongMemEval benchmark repositories. Sources
were upstream repositories, selected implementation files, official
documentation, and release histories. Selection considered architectural
fit, inspectable implementations, documentation, and maintenance evidence;
popularity alone was not a quality criterion.

The upstream source links below generally point to moving `main` branches.
They are research pointers, not immutable source snapshots. Release versions
recorded below establish maintenance context; this review did not establish
that every inspected main-branch feature ships in those releases. Before
implementation or code reuse, select a commit, verify its relevant tests and
file-level licensing, and recheck the behavior being adapted.

No competing stack was installed or benchmarked. No end-to-end upstream
test suite, security audit, exhaustive repository audit, or legal reuse
assessment was performed. Published benchmark claims were not reproduced.
The documentation work made no runtime changes, ran no NAS load test, and
did not release, deploy, enable metrics, commit, or push anything.

## OpenChronicle baseline

### Strengths to preserve

- [Hexagonal architecture](../architecture/ARCHITECTURE.md) separates domain,
  application, persistence/provider adapters, and MCP/REST/CLI drivers.
- Explicit caller-authored memories keep synthesis and model execution
  outside the server. Git onboarding also leaves synthesis to the caller.
- FTS5 and embedding similarity are fused through RRF, with keyword-only,
  semantic-only, and hybrid modes. Hybrid retrieval has an embedding-failure
  fallback; semantic-only retrieval reports provider failure explicitly.
- [Embedding identity](0005-embedding-identity.md), content invalidation,
  and [permanent-failure classification](0009-permanent-embed-failure-classification.md)
  protect retrieval from stale vectors and repeated unembeddable inputs.
- Versioned export/import, atomic export publication, online backups,
  migrations, and regression tests provide a useful durability foundation.
- [The existing retrieval benchmark](../../scripts/benchmark_embeddings.py)
  exercises the actual search pipeline, includes FTS5 as a baseline, reports
  recall and MRR, and separates tuning from validation queries.

The [current assessment](../CODEBASE_ASSESSMENT.md) remains authoritative
for release and verification status. Its recorded test results are prior
evidence, not tests rerun during this research. Metrics integration remains
unreleased and subject to unresolved acceptance gates.

### Verified source observations and their implications

| Observation | Local evidence | Implication for future research |
|---|---|---|
| Memories contain an ID, content, tags, timestamps, pin state, project and source label; there are no first-class revision, provenance-reference, or supersession fields | [MemoryItem](../../src/openchronicle/core/domain/models/memory_item.py) | Source-linked history and changing facts would require a deliberate model and persistence design |
| MCP save creates a new MemoryItem per invocation and accepts no operation ID | [MCP memory tools](../../src/openchronicle/interfaces/mcp/tools/memory.py) | A retry after an ambiguous committed response has no operation-identity contract |
| Memory updates select by memory ID without requiring an expected revision | [SqliteStore.update_memory](../../src/openchronicle/core/infrastructure/persistence/sqlite_store.py) | Concurrent callers have no explicit stale-edit conflict contract |
| Context catch-up limits the number of memories; compact serialization uses a 120-character preview | [Context tools](../../src/openchronicle/interfaces/mcp/tools/context.py), [serializers](../../src/openchronicle/interfaces/serializers.py) | Count and preview limits do not establish a complete response-token budget |
| Retrieval benchmark fixtures contain private memory content and are untracked | [Benchmark module documentation](../../scripts/benchmark_embeddings.py) | Outside contributors cannot reproduce the same evaluation from the repository alone |
| The store has one connection protected by an RLock; semantic retrieval loads embeddings into NumPy for similarity ranking | [SQLite adapter](../../src/openchronicle/core/infrastructure/persistence/sqlite_store.py), [embedding service](../../src/openchronicle/core/application/services/embedding_service.py) | Measure contention and corpus effects before choosing a new state tier |
| CI and Docker install from pyproject.toml rather than consuming the tracked lock as a frozen resolution | [CI](../../.github/workflows/test.yml), [Dockerfile](../../Dockerfile) | Reproducible dependency consumption remains existing unfinished work |

These observations establish capability boundaries. This review did not
reproduce a live duplicate-write incident, lost update, or tenant-isolation
failure, and does not relabel deliberate v3 exclusions as defects. Memory
edit concurrency is also distinct from the embedding-publication CAS
protection already implemented under ADR 0005.

## Repository assessments

### Basic Memory — closest product and usability reference

[Repository](https://github.com/basicmachines-co/basic-memory) · advertised
repository license: AGPL-3.0.

Basic Memory exposes human-readable Markdown knowledge, explicit
relationships, and integrations with multiple AI clients. Its
[context service](https://raw.githubusercontent.com/basicmachines-co/basic-memory/main/src/basic_memory/services/context_service.py)
supports bounded relationship expansion with depth, result, related-item,
and time controls. The
[note format](https://raw.githubusercontent.com/basicmachines-co/basic-memory/main/NOTE-FORMAT.md)
is another useful interoperability reference.

**Transfer:** navigable memory views, stable references, readable exports,
client onboarding, and bounded context expansion. These can be adapted
while keeping SQLite canonical. Markdown as canonical storage and file
watchers remain outside the adopted OpenChronicle direction.

**Maintenance evidence:**
[v0.23.2](https://github.com/basicmachines-co/basic-memory/releases/tag/v0.23.2)
was listed on 2026-08-25. The review also inspected the upstream
[test workflow](https://raw.githubusercontent.com/basicmachines-co/basic-memory/main/.github/workflows/test.yml).
Neither observation establishes that all tests were green or that the
repository has been audited.

### Graphiti — strongest reference for changing facts

[Repository](https://github.com/getzep/graphiti) · advertised repository
license: Apache-2.0.

Graphiti models temporal knowledge with provenance back to source episodes.
Its [edge model](https://raw.githubusercontent.com/getzep/graphiti/main/graphiti_core/edges.py)
includes episode references and separate fields for creation, validity,
invalidation, and the source episode's reference time. It also provides an
[MCP server](https://github.com/getzep/graphiti/tree/main/mcp_server).

**Transfer:** distinguish when a statement was recorded from when it was
true; preserve evidence and predecessors when facts change. These semantics
can be explored in OpenChronicle's existing persistence model without
committing to a graph database.

**Fit limit:** the broader graph infrastructure and model-driven ingestion
introduce operational and inference costs beyond the current memory-only
server. Automatic fact invalidation should not be imported as a default
without an accepted ownership and correction policy.

**Maintenance evidence:**
[v0.30.2](https://github.com/getzep/graphiti/releases/tag/v0.30.2)
was listed on 2026-09-08. This does not pin the inspected main-branch source.

### Hindsight — strongest retrieval research reference

[Repository](https://github.com/vectorize-io/hindsight) · advertised
repository license: MIT.

Hindsight's [retrieval implementation](https://raw.githubusercontent.com/vectorize-io/hindsight/main/hindsight-api-slim/hindsight_api/engine/search/retrieval.py)
has semantic, keyword, graph, and temporal retrieval components. Its
[retrieval documentation](https://hindsight.vectorize.io/developer/retrieval)
describes fusion, reranking, and results constrained by a token budget.
The [reranker](https://raw.githubusercontent.com/vectorize-io/hindsight/main/hindsight-api-slim/hindsight_api/engine/search/reranking.py)
is a concrete place to study interactions between relevance and secondary
ranking signals.

**Transfer:** explicit response budgets, per-stage retrieval diagnostics,
and controlled evaluation of additional retrieval channels. OpenChronicle
already has RRF; adding RRF again is not an improvement. A new reranker or
channel must demonstrate value against that baseline.

**Fit limit:** model-driven reflection and extraction belong to a broader
system. Global temporal decay is not a recommended OpenChronicle default:
an old standing rule can remain the right answer.

**Maintenance evidence:**
[v0.9.2](https://github.com/vectorize-io/hindsight/releases/tag/v0.9.2)
was listed on 2026-08-25. Published accuracy claims were not reproduced.

### Mem0 — mutation history and developer experience

[Repository](https://github.com/mem0ai/mem0) · advertised repository license:
Apache-2.0.

Mem0 provides a broad integration surface. Its open-source
[history storage](https://raw.githubusercontent.com/mem0ai/mem0/main/mem0/memory/storage.py)
records old/new memory values, event type, timestamps, and actor/role fields.
This is a useful implementation reference for auditable mutations.

**Transfer:** clear write/history APIs and approachable client integration.
The history model is evidence of an available pattern, not proof that its
transaction boundaries can be copied unchanged into OpenChronicle.

**Benchmark qualification:** the
[repository's April 2026 algorithm section](https://github.com/mem0ai/mem0#new-memory-algorithm-april-2026)
explicitly says headline scores reflect its managed platform, including
proprietary optimizations unavailable in the open-source SDK. Those figures
do not establish what adapting public code would deliver. The review makes
no performance-equivalence or feature-parity claim between those products.

### Cognee — selective ingestion and provenance reference

[Repository](https://github.com/topoteretes/cognee) · advertised repository
license: Apache-2.0.

Cognee processes documents and code into connected memory. Its
[pipeline modules](https://github.com/topoteretes/cognee/tree/main/cognee/modules/pipelines)
and [provenance configuration](https://raw.githubusercontent.com/topoteretes/cognee/main/cognee/modules/pipelines/provenance_config.py)
are references for organizing ingestion and recording where derived data
came from.

**Transfer:** consider these patterns if an actual consumer requires
ingestion beyond curated memories and Git history. This is a lower-priority
fit today; a broad processing platform would substantially widen scope.
Document extraction, chunking, and graph construction are not scheduled
by this comparison.

### LangMem — selective client-side memory-management reference

[Repository](https://github.com/langchain-ai/langmem) · advertised repository
license: MIT.

LangMem separates memory operations during interactions from background
extraction and consolidation. Its
[memory manager](https://raw.githubusercontent.com/langchain-ai/langmem/main/src/langmem/knowledge/extraction.py)
exposes configurable mutation behavior. It is a framework library rather
than a directly comparable standalone memory MCP server.

**Transfer:** optional external agents could propose memory improvements
while OpenChronicle remains the authoritative store. A reviewed proposal
flow would be an OpenChronicle design choice; this review did not establish
that LangMem supplies that approval workflow. Its framework and model
dependencies need not become server dependencies.

### Official MCP memory reference — useful examples, limited target

The [official MCP server collection](https://github.com/modelcontextprotocol/servers)
describes its implementations as educational references, not
production-ready solutions. Its
[memory server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)
is therefore useful for protocol examples, but was not selected as the
primary persistence, recovery, or product architecture to emulate.

## Evaluation sources and comparison discipline

[LongMemEval](https://github.com/xiaowu0162/LongMemEval) tests extraction,
multi-session reasoning, knowledge updates, temporal reasoning, and
abstention. These offer a useful starting point for memory-quality cases.

[LongMemEval-V2](https://github.com/xiaowu0162/LongMemEval-V2) adds
environment-specific knowledge, dynamic state, workflows, gotchas, and
premise awareness. Its multimodal web-agent histories are a broader scope
than OpenChronicle's current text-memory model. It is a later benchmark
reference, not a drop-in evaluation with an assumed fair comparison.

Any future evaluation should:

1. Publish sanitized fixtures with known-relevant evidence and a fixed
   tuning/held-out split; retain private operational data outside the repo.
2. Separate retrieval quality from final answer quality and from ingestion
   quality. A better reader or richer extraction can change an answer score
   without demonstrating a better retrieval implementation.
3. Hold corpus, reader model, ingestion policy, context budget, and model
   configuration constant where making like-for-like comparisons. Document
   necessary differences and all preprocessing/inference costs.
4. Include FTS5-only and the current hybrid pipeline; include no-memory or
   full-context controls where appropriate to the downstream task.
5. Report recall, stale-memory selection, returned tokens, request latency
   (including relevant p50/p95/p99 measurements), responsiveness, failures,
   and downstream answer quality separately, with configuration and source
   revisions. Do not turn unrelated vendor scores into a common leaderboard.
6. Evaluate changed decisions, similar project names, conflicting evidence,
   duplicates, old but valid instructions, and questions with no supported
   answer. Successful abstention matters alongside successful retrieval.

## Prioritized development hypotheses

Every hypothesis is subordinate to accuracy first and speed/responsiveness
second, as recorded above. This is the research recommendation order, not
the active sprint order.
Effort labels are relative estimates; implementation has not been designed
or scheduled. Existing release and durability obligations retain their
current priority independently of the product ideas.

### 1. Public, reproducible memory-quality evaluation

**Effort:** medium. **Disposition:** proposed extension to an existing harness.

Publish a sanitized, distributable corpus and extend the current benchmark
to cover the cases above. The current private gold set remains useful for
local regression checks; it is not a public reproducibility artifact.

**Value:** contributors can demonstrate gains and trade-offs rather than
relying on intuition or vendor claims. This supplies the decision instrument
for subsequent lifecycle and retrieval changes.

**Acceptance:** another developer can reproduce the published evaluation
from documented inputs and configuration; tuning and held-out results are
separate; retrieval and reader effects remain distinguishable.

### 2. Predictable concurrent and retried writes

**Effort:** medium. **Disposition:** stable replay identity strengthens
existing resilience planning; edit-revision preconditions are a proposal.

Consider operation IDs for retry-safe creation and expected revisions for
updates. A committed write whose response is lost should be retryable; a
stale editor should receive an explicit conflict. Content equality alone is
not an operation identity, because repeated observations can be intentional.

**Value:** multiple clients can coordinate without inventing incompatible
retry and conflict behavior. This is especially relevant to the already
documented single-primary write-behind direction.

**Acceptance:** retrying one logical operation produces one logical write;
reuse of an operation ID with incompatible input is explicit; concurrent
stale updates cannot silently overwrite newer content. Define persistence,
scope, and retention of operation identities before promising replay safety.

### 3. Source-linked history and explicit supersession

**Effort:** larger. **Disposition:** new product scope; revises a deferred v3
decision if adopted.

Explore source references, immutable revisions, and an explicit supersedes
relationship. Keep recorded time distinct from validity time. For example,
"deployments use release tags" can replace "deployments track latest" for
current-state questions while retaining both statements for historical ones.

**Value:** engineering and operational memories change over time; preserving
their evidence can make corrections understandable and retrieval safer.
Revision history and temporal validity are related but different concepts.

**Acceptance:** current-state queries select the applicable decision;
historical queries can retrieve predecessors and evidence. Define unknown
validity, corrections, conflicting sources, export/import behavior, and
whether restoration creates a new revision before implementation.

The v3 plan explicitly defers edit history. A transport label such as
`source="mcp"` is also not an authenticated authority level. Provenance
must not silently turn client-supplied claims into trusted instructions.

### 4. Context retrieval with an explicit budget

**Effort:** medium. **Disposition:** proposed read capability; ranking changes
remain separately benchmark-gated.

Explore a deterministic operation that selects evidence within a caller's
declared budget and returns memory IDs, selection reasons, and omitted-item
counts. Reuse the existing search pipeline and explainable relevance data.

**Value:** agents can spend their context on useful evidence while making
omission visible. A row-count limit and a preview length solve different
problems from a complete payload budget.

**Acceptance:** specify the tokenizer or documented estimation contract;
account for the returned envelope and metadata; define behavior when even
one result will not fit; expose truncation explicitly. Evaluate retained
evidence and downstream quality at fixed budgets. A server can bound its
own payload, not all protocol wrapping and prompts a client later adds.

Additional graph/temporal channels, MMR, or a cross-encoder are separate
experiments. Each must earn its latency, memory, and inference costs on
held-out queries; none becomes mandatory through this proposal.

### 5. A small human-facing memory inspector

**Effort:** medium to larger. **Disposition:** new product-surface proposal.

Explore project browsing, search explanations, source links, and readable
exports. Once a revision model exists, add diffs and reviewed restoration.
The central user question is: "What does the system remember about this
project, where did it come from, and what changed?"

**Value:** people can inspect and correct their persistent context without
constructing API calls. This builds on Basic Memory's usability lesson
while preserving OpenChronicle's canonical store.

**Acceptance:** a person can locate and correct a memory through the same
application rules as MCP writes. Keep any new UI scoped to the existing
deployment/authentication model; project namespacing alone is not a
multi-tenant authorization boundary. Revision-dependent features wait for
the lifecycle design rather than inventing a second history mechanism.

### 6. Finish existing release and durability foundations

**Effort:** small to medium per bounded batch. **Disposition:** existing
work, not a newly accepted implementation queue.

The current assessment retains unfinished frozen dependency consumption,
cloud-backup work, and unresolved performance acceptance. Preserve their
existing owners, gates, and scope rather than creating duplicate work items.

**Acceptance:** use the relevant existing plans' criteria: reproducible
dependency resolution where claimed, a completed restore drill for backup
acceptance, and unchanged performance/noise budgets for metrics acceptance.
Source inspection or prototype timing does not replace a release gate.

The accepted scale sequence remains measurement, then justified SQLite
headroom improvements, then PostgreSQL/pgvector only when named triggers
fire. This comparison establishes no need for a language rewrite.

## Reconciliation with existing decisions

| Existing record | Relationship to this review |
|---|---|
| [0002 — OpenClaw](0002-openclaw-memory-review.md) | Preserve its shipped retrieval-integrity fixes. MMR, provenance, supersession, and corpus-quality ideas remain experiments or conditional proposals; this review adds references rather than declaring them new verified defects |
| [0003 — Ollama](0003-ollama-repository-review.md) and [0006 — provider review](0006-embedding-provider-review.md) | Extend the existing gold-set decision instrument; do not repeat already implemented embedding-identity and adapter work or schedule another provider switch |
| [0004 — NemoClaw](0004-nemoclaw-repository-review.md) | Replay identity and frozen dependency consumption already have provenance here; preserve those links and the distinction between committed writes and acknowledged responses |
| [0007 — scale and resilience](0007-long-term-scale-and-resilience.md) | Keep SQLite by default, persistence behind ports, single-primary write-behind, measured stage triggers, and restore-drill acceptance |
| [0010 — performance measurement](0010-performance-measurement.md) | Metrics work and acceptance remain unresolved on their own evidence; no new benchmark, optimization cycle, or enabling decision follows automatically |
| [V3_PLAN](../V3_PLAN.md) | Edit history is deferred; multi-user auth, automatic expiration, broad runtime behavior, and sync-as-store are not accepted by recording this document |

Do not infer a recommendation to transplant a complete upstream stack,
make graph infrastructure or inference mandatory, use global age decay for
all memories, or change the authoritative storage to Markdown. Optional
client-side consolidation and broader ingestion require separate consumer
requirements and designs. The proposed differentiator is a research
direction, not a replacement for the project's adopted working agreements.

## Later research entry points and stop conditions

When a proposal is selected, first pin the relevant upstream source and
recheck OpenChronicle's then-current implementation and roadmap. Define one
bounded design or experiment with its own acceptance and failure criteria.
Use the public evaluation extension as the first proposed research
instrument; it does not demote already adopted durability obligations.

Stop a candidate experiment if it cannot show a relevant benefit within
its agreed quality, latency, operational, and scope limits. Preserve negative
results. Accepting one candidate does not schedule the others, relax the
performance gates, or authorize publication or deployment.

This document is the retained research result. The design index provides
discovery, V3_PLAN records scheduling decisions, and CODEBASE_ASSESSMENT
records current implementation and verification status.
