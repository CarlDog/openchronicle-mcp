# Application Performance Measurement

**Status:** 4C RECOVERY CYCLE COMPLETE; RELEASE/ENABLEMENT BLOCKED — the final
NAS B/A and C/A overhead comparisons remain inconclusive, and the final
maximum-cardinality responsiveness gate did not pass. Phase 1–3 implementation
is complete. Passed 4D collection/access/recovery evidence was explicitly reused
for the frozen recovery candidate after source/configuration impact review.
Production is unchanged; 4E/4F have not started. The subsequent recorder and
cached-prefix exporter patches are locally implemented; further NAS validation
requires a scoped decision.
**Date:** 2026-09-05.
**Release exception (operator, 2026-09-24):** v3.4.0 ships this
instrumentation, off by default, under an explicit exception to the rule that
an inconclusive B/A blocks release; see [the exception](#operator-release-exception-2026-09-24).
Enabling metrics in production still requires this design's gates.

**Work key:** `CarlDog/openchronicle-mcp:work-item:performance-observability-plan`.
This identifies the planning work, not a GitHub issue or an approved build.

**Revision:** 2026-09-05 — incorporates the five adversarial-review findings,
records the Phase 1 implementation, the Phase 2 implementation (probe
throttling, corpus drift, disabled-path overhead and rollback, scrape
responsiveness, all-attempt scrape-duration retention, and backfill failure
classification), the Phase 3 local collector configuration, the Phase 4
controlled-host gate and retest results, and the Phase 4D NAS collection,
access, and rollback evidence, followed by the bounded 4C recovery cycle.
Metrics remain disabled by default. The earlier responsiveness result is
superseded for the final candidate by the full-cardinality result below;
4D evidence was applicable to that frozen candidate. Any newer candidate needs
an affected-path impact review; live release/deployment observation is pending.

**Resolution plan:** [Phase 4 remaining-work plan](#phase-4-remaining-work-plan)
records the proposed sequence, evidence, and stop conditions following commit
`682c68f0`. The implementation is committed; production rollout is pending.
The [4C recovery plan](#4c-recovery-plan) adds the next bounded sequence after
4D: evidence integrity, baseline repeatability, enabled-cost diagnosis, a
targeted patch, and a new frozen comparison. Recovery execution is recorded in
the [execution checkpoint](#4c-recovery-execution-checkpoint): trustworthy
calibration reuse was explicitly approved after the validation-only correction.
The [final disposition](#4c-recovery-final-disposition) records the published
candidate, verified acceptance report, responsiveness limitations, and stop.

The subsequent operator-authorized diagnostic phase is recorded in the
[4C attribution report](0010-4c-attribution.md). It identifies shared-host CPU
interference and specific recorder/exporter work, rejects invalid mixed-thread
profile timings, and proposes patches. The operator subsequently approved
recorder-only Patch 1: ordered health transitions and bounded HTTP/embedding
child caches are implemented and verified locally (951 tests passed across
the full run and two-test fixture-isolated retry; quality checks passed).
Patch 2's local exporter prototype passed 53 contracts; full-matrix median scrape CPU fell
17.50 → 10.3125 ms in the single-thread Windows diagnostic. This is not a NAS
application-performance result. The subsequently authorized local integration
now uses one bounded prefix cache per enabled recorder, with fresh values,
standard fallback and unchanged scrape ownership. Regressions correct unusual
string cache hits and whole-scrape encoding errors; maintained Linux contracts
passed 106 tests on both Prometheus 0.26.0 and the 0.23.1 floor. This corrected
candidate has not been timed. The [integration checkpoint](0010-4c-attribution.md#local-integration-checkpoint)
records verification and the affected 4D checks still required. No new NAS
acceptance, publication or production action followed. Release/enabling remain
blocked; metrics are off by default.

A subsequent [read-only NAS readiness snapshot](0010-4c-attribution.md#nas-readiness-snapshot--completed-not-a-baseline-control-pass)
completed for all 42 running containers: 8.852% host busy CPU, no niced CPU, and
no heavy Docker workload identified to pause. Production was unchanged. The
53.267-second observation is not a baseline-control pass or historical spike
attribution; an agreed quiet window and unchanged control/noise gates still
precede a new acceptance decision. No load test or publication followed.

## Recommendation and intended outcome

**Source checkpoint, 2026-09-09 UTC:** commit/push of all current source and
documentation is operator-authorized. See the
[assessment checkpoint](../CODEBASE_ASSESSMENT.md#source-checkpoint--2026-09-09-utc).
This source publication leaves the pinned live build, default-off metrics and
the unresolved acceptance gates unchanged; earlier no-publication statements
describe their original checkpoints.

Add opt-in, bounded operational metrics to OC, implement the concurrency
probe already accepted in [design 0007](0007-long-term-scale-and-resilience.md),
and collect history with a local Prometheus instance. Reuse a fleet collector
if one exists; repository configuration is checked in Phase 3, while live host
inventory remains a deployment-gated verification.

The result should answer five questions:

1. Which REST operations and MCP tools are slow, and how often do they fail?
2. Is time spent waiting for SQLite, calling the embedding provider, or
   preparing and scoring search candidates?
3. What happens as concurrent clients and the memory corpus grow?
4. Did a release change latency, throughput, or process resource use?
5. How does the current observation window compare with the same window
   last week, once enough history exists?

Keep Python and the existing persistence architecture. A single SQLite
connection and its shared lock are confirmed in source; their practical
capacity under fleet traffic remains unmeasured. This proposal measures
that capacity before activating design 0007's later stages.

## Existing behavior and policy changes

| Existing facility | What it establishes | Remaining gap |
|---|---|---|
| [Health payload](../../src/openchronicle/core/application/use_cases/diagnose_runtime.py) | Runtime configuration, build identity, embedding coverage and failure state | No request latency or historical series |
| [Maintenance state](../../src/openchronicle/core/application/services/maintenance_loop.py) | Outcomes, process-local counters, persisted last-run and last-success times | No job-duration history |
| [Backfill results](../../src/openchronicle/core/application/use_cases/embed_memory.py) | Counts and elapsed time for a completed synchronous call; background progress through coverage | No queryable history of completed runs |
| [Embedding benchmark](../../scripts/benchmark_embeddings.py) | Retrieval quality, query timings, reindex duration | Not a concurrent REST/MCP workload or continuous production measurement |
| [Logging](../../src/openchronicle/interfaces/logging_setup.py) | Human/JSON records and an optional rotating file | No general performance aggregation |

Adopting this proposal would amend two explicit exclusions in
[V3_PLAN](../V3_PLAN.md): the prohibition on call counts, and the decision
to use only health and logs instead of a monitoring system. The amendment
permits aggregate **operational** counts and timings with a local collector.
Token accounting, billing, agent activity history, content collection,
distributed tracing, and external telemetry remain outside the proposed scope.

Design 0007's persistence rule continues to govern application data.
Disposable process counters and a separate monitoring database hold no OC
business state. OC must keep serving if collection stops or history is lost.
Phases 1–3 of this document are adopted for working-tree implementation, and
the Phase 4 probe verification is complete locally; collector history remains
separate from OC business state and does not change the memory persistence
policy.

## Implementation phases

Estimates are planning estimates for focused implementation work, not measured
durations. Each phase produces a reviewable change and has its own stop gate.

| Phase | Deliverable | Acceptance / stop gate | Estimate |
|---|---|---|---|
| 1. Establish baseline | Reusable disposable-instance probe, deterministic fixtures, machine-readable results | Correctness checks pass; latency/throughput and workload limits are reported honestly | 1 session |
| 2. Instrument OC | Optional metrics dependency, recorder wiring, timings/counters, guarded `/metrics` | Contract, concurrency, privacy, and overhead gates below pass | 2–3 sessions |
| 3. Keep history | Collector configuration, retention, saved queries, operating instructions | Scrapes work; samples survive an OC restart; unavailable data appears as a gap | 1 session |
| 4. Release and observe | Tagged release, verified deployment, comparison against Phase 1 | Live smoke and collection checks pass; observation window and remaining unknowns are recorded | 1 session plus elapsed observation time |

Phase 1 may start independently after implementation is requested. Phase 2 was
explicitly adopted on 2026-09-04 with the policy amendment and dependency
decision: the standard image and development environment include the metrics
extra, while the runtime default remains `OC_METRICS_ENABLED=false`. Phase 3
was continued on 2026-09-04: the repository now carries a profile-gated local
Prometheus configuration, retention settings, saved queries, and an operator
runbook. Phase 4 probe verification was then run locally, followed by the
disposable NAS 4D collection/access/recovery checks recorded below; neither
authorizes release, deployment observation, or enabling the runtime switch.

### Phase 1 — controlled workload and baseline

Implement `scripts/probe_performance.py` as a sibling of the embedding benchmark.
Start a disposable OC instance on loopback with an isolated temporary database,
then exercise its real REST or streamable-HTTP MCP interface. Refuse arbitrary
remote targets in this first probe. Seed synthetic, deterministic memories;
do not export the live corpus or load the credential vault.
Construct explicit temporary runtime/configuration paths and a sanitized child
environment so inherited OC paths or provider credentials cannot redirect the
probe. Disable scheduled maintenance in baseline cases; test overlapping jobs
only in a separately named, bounded scenario against the disposable store.
Explicitly set `OC_API_RATE_LIMIT_RPM=0` in the disposable child's environment
and report that setting. Otherwise all loopback clients share the default
600-request/minute quota and the probe measures throttling, not OC throughput.
This override must never modify the operator's environment or deployment.
Exercise the default limiter in a separate bounded correctness scenario;
expected 429s there are not performance samples. Any unexpected 429, application
failure, or timeout makes an overhead comparison ineligible, not a fast result.

- One invocation selects a workload lane, transport, corpus size, and provider profile.
  Default corpus: 1,000 memories; a separate 10,000-memory invocation tests
  growth. Fix and report content-size distribution, tags, projects, vector
  dimensions, and random seed; replay the same operation sequence for comparisons.
- Use a **fixed-corpus lane** for overhead comparisons: 90% search and 10% lists,
  with no writes during warm-up or measurement. Seed all required vectors before
  warm-up and assert that logical memory/vector counts and content fingerprints
  remain unchanged afterward. Maintenance and lazy fixture population must not
  change that state during a run.
- Keep 70% search, 20% small saves, and 10% lists in a separate **growth lane**.
  Report starting, post-warm-up, and final row/vector counts. Fixed-duration
  growth runs are descriptive, not causal overhead comparisons: faster runs
  save more rows and therefore perform searches against a different corpus.
  Fresh starting databases alone do not correct this. Write-overhead claims
  require a separate equal-work test with fixed save counts and the same input
  sequence from identical starting snapshots, not these timed growth results.
- Run keyword-only and semantic/hybrid profiles separately. Provider profiles are immediate stub
  and simulated 400 ms serialized embedding calls; the latter is a test input,
  not a claim about current NAS performance.
- Compare 1, 4, 8, and 16 concurrent clients. Per case: 5-second warm-up,
  60-second measurement, then bounded drain. Cap each invocation at 10 minutes
  including setup, with an abort and cleanup checkpoint. Bound client request
  timeouts and terminate only the probe's own child process if draining fails.
- Report attempted/completed/failed/timed-out operations, achieved throughput,
  completion rate, sample counts, and p50/p95/p99 by operation. Suppress p95
  below 100 completions and p99 below 1,000; label the sample insufficient.
  Report timeout counts and censored durations separately so successful-request
  percentiles cannot hide failures.
- This is a closed-loop concurrency experiment: clients wait for responses.
  It establishes behavior at a given client count, not capacity under arbitrary
  arrival rates. Include one bounded simultaneous burst; an open-loop capacity
  study is a separate decision if that question becomes necessary.
- Record commit, runtime/dependency versions, transport, host class, corpus
  shape, provider profile, instrumentation state, and scenario parameters.
  Use a fresh seed database per case so prior saves cannot inflate later cases.
  Exclude warm-up from the measurement window; fixed-corpus fingerprints must
  match across comparison conditions as well as before and after each case.
  Preserve sanitized reports as artifacts; always clean up the disposable store.

Phase 1 establishes endpoint behavior and records the exact uninstrumented
application revision, dependency set, and probe version for later reproduction.
Phase 2 reruns that baseline and the new build with internal timings to explain
it; a no-op recorder in the new build is not the uninstrumented baseline.
Store-lock wait share then means
`sum(outer wait) / (sum(outer wait) + sum(outer hold))` during the measured
window. It is a share of observed lock-acquisition/hold time, not CPU
utilization or a percentage of end-to-end request latency.

### Phase 2 — bounded metrics inside OC

Use the official `prometheus-client` package as the optional `[metrics]`
extra, resolved and verified at version 0.26.0 on Python 3.14. The standard
Docker image and development extra include it, while the runtime switch still
defaults false. Use a library registry/exporter rather than implementing
metric exposition.
The Python client supplies an [ASGI exporter](https://prometheus.github.io/client_python/exporting/http/asgi/).

Runtime switch: `OC_METRICS_ENABLED`, default false, using the existing
environment-parsing conventions. Disabled means no exporter route and a no-op
recorder. Explicitly enabled without the extra installed produces an actionable
startup configuration error. The NAS image must include the extra before the
operator enables it.

Create one registry per container/app lifecycle, not a module-global singleton.
The composition root injects a small typed recorder protocol into the store,
embedding service/adapters, and maintenance loop; drivers use the same recorder.
Place the protocol with the domain ports and the Prometheus implementation in
infrastructure. Domain/application code must not import Prometheus or interfaces.
This boundary serves several callers and supports both the exporter and a no-op
implementation; it does not change the persistence-port contracts.

Use monotonic time for durations and epoch timestamps for persisted last-success
values. Collect every event into fixed aggregates; never retain individual
request samples in the running application.

| Metric family (proposed) | Meaning and bounded dimensions |
|---|---|
| `oc_http_requests_total`, `oc_http_request_duration_seconds` | HTTP counts by normalized route, allowed method, status class; REST duration by route/method. Count MCP transport traffic separately, without treating connection duration as tool latency. |
| `oc_mcp_executions_total`, `oc_mcp_execution_duration_seconds` | Registered tool executions by fixed tool name; counter outcome: `ok`, `started`, `partial`, `rejected`, `error`, or `cancelled`. Duration by tool. |
| `oc_requests_inflight` | Admitted REST requests and MCP tool handlers, by surface; lifetime ends when the handler/request ends. This does not claim that a cancelled worker thread has stopped. |
| `oc_store_lock_wait_seconds`, `oc_store_lock_hold_seconds` | Outermost lock acquisitions, by fixed kind: read, write, or maintenance. Include explicit transaction contexts. |
| `oc_embedding_operations_total`, `oc_embedding_operation_duration_seconds` | Adapter operations by configured provider and single/batch operation; counter outcomes distinguish success, transient failure, permanent rejection, and other error. SDK-internal retries are included in elapsed time, not counted as observed HTTP attempts. |
| `oc_search_stage_duration_seconds`, `oc_search_fallbacks_total` | Fixed stages: keyword lookup, vector loading, candidate preparation/scoring, fusion/materialization. Fallback reasons: provider failure or over-length query. Stage boundaries must be pinned in tests. |
| `oc_job_runs_total`, `oc_job_duration_seconds`, `oc_job_last_success_timestamp_seconds` | Fixed maintenance names plus operator backfill; success/partial/failure/cancel/overlap outcomes, execution duration, and last successful completion. An overlap skip has no execution duration. |
| `oc_backfill_items_total` | Outcomes `generated`, `failed`, and `tombstoned`, accumulated from the corresponding existing `BackfillResult` fields. `failed` does not imply a transient or provider-only cause. |
| `process_*`, `oc_build_info` | Process CPU/RSS/start time where supported; one build/version information series per running process. |

Important measurement contracts:

- REST timing begins at ASGI receipt and ends on the final response body or
  abnormal termination. A pure ASGI observer must preserve streaming, bodies,
  guard order, status codes, and exceptions. Handled errors, unhandled 500s,
  cancellations, and early rejections must each be counted once. Exclude health,
  documentation, and metrics requests from application traffic measurements so
  scrapes cannot dominate the reported workload; use the collector's own scrape
  success/duration series to diagnose collection.
- MCP timing wraps the registered async handler, including its awaited worker
  work. Preserve signatures and annotations so existing FastMCP schema snapshots
  remain identical. SDK validation before handler admission and non-tool protocol
  messages are excluded from execution counts; transport status alone cannot
  identify JSON-RPC failures. Do not inspect request bodies to manufacture labels.
- A started background job is a successful start, not a completed job. Observe
  actual backfill completion in the shared execution path once, including manual
  and scheduled execution, without double-counting their wrapper layers. Preserve
  existing health counters and maintenance status semantics. Assign the fixed
  job name at the initiating boundary: scheduled backfill is `embedding_backfill`,
  explicitly started backfill is `operator_backfill`, and a backfill the
  revision refresher starts is `reconcile_backfill` (ADR 0005 §7, added
  2026-09-23); its completion is recorded
  under that name once. Seed scheduled last-success gauges from the existing
  persisted timestamps. Operator-backfill last-success is process-local, and
  absent until observed after startup; historical observations live in the
  collector. One-shot CLI invocations have no scrape guarantee and remain
  outside continuous collection, even though their shared execution emits events.
- Backfill's `failed` count includes non-tombstoned provider failures and
  persistence/internal exceptions. Preserve that generic meaning; do not infer
  retryability from it or relabel it as transient. Provider-specific failure
  counters come only from observed adapter operations. Tests must inject both
  provider and `save_embedding` failures, and prove that a persistence failure
  increments generic failed items without inventing a provider-failure event.
- Time both `_locked` and `transaction()` through a shared, reentrant-aware
  observation context. Record only the outermost wait/hold interval per thread;
  preserve all lock ownership and transaction behavior. Publish observations
  after releasing the store lock to avoid adding registry work inside it.
- `/metrics` serializes bounded in-memory aggregates; it never calls the full
  health builder, scans the memory/vector tables, or contacts a provider. Existing
  coverage/staleness diagnostics remain in health. Metrics failures must not
  replace application results; expose recorder failure state and a bounded warning
  so failed measurement cannot silently appear as a clean zero.
- Keep synchronous collection, serialization, and any compression off the ASGI
  event loop, using library exposition code in a bounded worker. The referenced
  [ASGI exporter implementation](https://github.com/prometheus/client_python/blob/master/prometheus_client/asgi.py)
  performs serialization synchronously inside its async handler; an async
  function or a collector-side timeout alone does not prevent request stalls.
  Recheck the selected dependency version during implementation. Allow at most
  one active serialization per app and no queued scrape backlog; after the usual
  access guards, return 503 for overlapping scrapes. A disconnected or cancelled
  waiter must not release that slot until its worker actually finishes. Prove
  responsiveness under maximum-cardinality scrapes in the separate gate below;
  moving work to a thread alone is not performance evidence.
- Register the standard process collector explicitly with the app's registry.
  It reports CPU, RSS and start time on Linux; unsupported development platforms
  must omit those series cleanly. These are process measurements, not NAS-wide
  or container-quota statistics. See the [collector documentation](https://prometheus.github.io/client_python/collector/).

Use counters and histograms, with duration units in seconds. Initial request,
provider, and stage buckets: 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5,
1, 2.5, 5, 10, 30, 60, plus infinity. Use finer lock buckets down to 0.0001
seconds and job buckets extending through 3,600 seconds. Review boundaries
against Phase 1 before shipping. Histograms provide approximate quantiles;
never average p95 values or subtract independently computed percentiles to
attribute latency. See [histogram guidance](https://prometheus.io/docs/practices/histograms/).

Privacy and cardinality are part of the metric contract. Permit only enumerated
operations, route templates, status/outcome categories, and configured provider
names. Normalize unknown routes/methods to fixed fallback values. Never label or
record content, queries, tags, project/memory/client IDs, IPs, URLs, raw paths,
headers, exception messages, or credentials. Build identity appears only in the
single information metric. Require fewer than 5,000 exported series and under
1 MiB uncompressed exposition after exercising every label combination and a
random-input test. Prometheus documents why [each label combination adds a series](https://prometheus.io/docs/practices/naming/).

Serve the exporter on the existing ASGI port at `/metrics`; verify exact path
and trailing-slash behavior. Preserve Host validation and configured API-key
authentication; never add metrics to the health authentication exemptions.
With the intentionally empty LAN API key, enabled metrics have the same trusted
LAN exposure as other non-exempt routes. Do not describe that as authenticated.
The collector must use an allowed Host and configured credentials when present.
Retain rate limiting initially; a throttled scrape is visible as a collection
gap, and any dedicated exemption requires a separately reviewed access policy.
The disposable probe's explicit rate-limit override is not a production exemption.

### Phase 3 — local history and useful queries

No compatible collector configuration was present in the repository. The
implemented optional Prometheus profile in `docker-compose.nas.yml` uses the
private `oc-observability` network, scrapes `oc:8000/metrics` every 30 seconds
with a 5-second timeout, and pins `prom/prometheus:v3.14.0`. The profile is not
started by the default compose invocation, and OC still defaults to
`OC_METRICS_ENABLED=false`. It has no service discovery or cloud remote-write
destination.

Configured starting retention: 14 days with a 1 GiB retention-size target and at least
2 GiB of allocated local storage. This is a starting budget to validate, not a
hard filesystem cap or a guarantee of 14 days: the first retention threshold
reached wins, and WAL/head/compaction space also matters. Validate observed
ingestion and disk use against the desired history window. Use a local
filesystem, not NFS. These constraints follow the [Prometheus storage model](https://prometheus.io/docs/prometheus/latest/storage/).

The saved query catalog is
[`docs/monitoring/promql.md`](../monitoring/promql.md), and the operator
runbook is [`docs/monitoring/runbook.md`](../monitoring/runbook.md). They cover:

- Per-operation request volume, errors, p50/p95 latency and sample counts.
- Provider latency/failures versus keyword/vector/scoring stages and lock waits.
- Backfill/job outcomes, durations and time since last success.
- Process CPU/RSS, restarts, build identity, and collector scrape success.
- Current windows versus equivalent windows seven days earlier; retain workload
  mix/count context and avoid attributing all changes to a release.

Use the collector's query/graph UI initially, or an existing Grafana instance.
At low traffic, use longer windows and show counts; no traffic is different from
a missing scrape. Counter resets must be handled with reset-aware rate/increase
queries. Never turn a missing series into a zero-latency or zero-error claim.

The compose profile uses a separate local Prometheus volume so history can
survive an OC restart. Requests between the last scrape and a crash can be
lost. A scraper on the same NAS cannot observe a whole-NAS outage from outside
that failure domain. Treat historical metrics as disposable operational
evidence, separate from OC's memory backups. A disposable Docker smoke check
validated target-up state, query results, and a pre-restart sample retained
after the OC restart. Live NAS scrape/restart behavior was verified in Phase
4D below; release/deployment observation remains a later gate.

### Phase 4 — verification, release, and observation

The implementation's required gates are:

1. **Semantic correctness:** deterministic fake-clock tests cover event counts,
   outcome classification, duration units, cancellation, background completion,
   reentrant transactions, and concurrent updates. No negative in-flight gauges;
   no lost metric increments in controlled concurrent tests. Snapshot collection
   during writes must not deadlock or mutate the store.
2. **Surface and privacy:** test real REST and MCP calls, disabled/missing-extra
   configurations, two app instances in one test process, auth/Host rejection,
   and secret-shaped/random user input. Existing MCP schemas and health parity
   pass unchanged. Confirm scrapes do no provider or database work.
3. **Measured overhead:** use the fixed-corpus lane on the same controlled host
   with three conditions: A, the recorded uninstrumented application revision;
   B, the new revision with metrics disabled; and C, the same new revision with
   metrics enabled and scraping at the configured interval. Use the same probe,
   fixtures, runtime, common dependency versions, and process launch settings;
   record unavoidable dependency differences. Run three matched blocks in
   rotating order (A/B/C, B/C/A, C/A/B), with fresh identical fixtures each time.
   Compare B against A and C against A independently; C versus B is additional
   diagnostic evidence, not the sole acceptance test. Proposed budget for both
   baseline comparisons: per-operation added p95 latency no greater than the
   larger of 1 ms or 5% of A, throughput loss at most 5%, and added OC RSS at most
   10 MiB at eight concurrent clients in the immediate-provider profile. Report
   every within-block delta and use the median for each gate; inconsistent,
   noisy, failed, or insufficient-sample results remain inconclusive. A B/A
   breach or inconclusive result blocks release of the instrumentation change
   even with metrics disabled; a C/A breach or inconclusive result blocks enabling
   metrics. This
   read-only lane does not establish write overhead; do not claim that it does.
4. **Scrape responsiveness:** use the full reachable label matrix from the
   cardinality test while serving the fixed-corpus REST/MCP workload at eight
   clients in the immediate-provider profile.
   Compare matched enabled-but-unscraped and enabled-and-scraped runs on the
   controlled host, including at least 30 completed scrapes during a bounded
   stress case, compressed and uncompressed responses if supported, and a
   separate overlapping-scrape case. Proposed budgets: each non-overlapping
   scrape completes within 1 second; maximum event-loop scheduling lateness
   (10 ms probe tick) increases by at most 10 ms over its control; per-operation
   application p99 increases by at most the larger of 5 ms or 10% of control.
   Require at least 1,000 successful samples per operation for that p99 comparison,
   and no unexpected application errors or timeouts. Report maxima and all
   per-scrape intervals as well as quantiles so brief pauses are not averaged
   away. Each invocation retains the 10-minute cap; insufficient samples or noisy
   controls are inconclusive and block enabling metrics, not grounds to extend
   indefinitely or relax the budget. Deterministic tests must also show that
   overlap rejection and waiter cancellation never queue extra serializations
   or release the active worker slot early. These proposed budgets are acceptance
   targets, not claims about current NAS performance.
5. **Repository verification:** run `pytest`, `ruff check src tests scripts`,
   `ruff format --check src tests scripts`,
   `mypy src tests --config-file=pyproject.toml`, and `npm run lint:md`.
   Keep timing thresholds out of ordinary shared-runner CI; CI verifies the
   probe and metric contracts with deterministic fixtures, while the controlled
   host report supplies the performance evidence. Before commits, update the
   required status/plan/sprint docs, maintain AGENTS/CLAUDE parity, and mirror the
   implementation work's verified state to OpenChronicle.
6. **Collection and release:** prove scrape success, error visibility, history
   across an OC restart, and unavailable/idle distinctions. Update environment,
   architecture, deployment, stability and operator docs. This additive feature
   belongs on `main` with a MINOR release; reconcile with `v4/develop` through
   the existing merge-forward workflow. Respect gated CI and tag-pinned deployment:
   moving `OC_TAG` is the deployment event. Verify the actual package/build
   revision, allowed/rejected Host behavior, and authenticated metrics when auth
   is configured using a disposable target before enabling the operator's stack.

Then collect an initial seven days for baseline interpretation using an explicit
scheduled follow-up if the operator requests one. No interactive session should
wait for that window. Week-over-week displays need an older populated comparison
window; do not call them validated on day one. Start with observation and saved
queries; notification routing and alerts are a later explicit decision informed
by volume and baseline, including minimum-sample rules.

### Phase 4 execution — 2026-09-04

#### Sequential NAS follow-up protocol

The operator approved using CARLDOG-NAS itself. Dedicated hardware is not an
application requirement: the 24-CPU check belongs only to the experimental
concurrent three-way CPU-partition harness. The sequential path below needs no
such partition and does not reserve exclusive CPUs or change the live stack.

`scripts/probe_sequential.py` runs twelve fresh disposable loopback cases in
three blocks: A/B/C/R, B/C/A/R, C/A/B/R. R repeats the uninstrumented A baseline
with a newly seeded database. A is the recorded clean revision; B/C use one
candidate source snapshot. A curated test image contains both source trees,
using the same Python interpreter and installed dependencies throughout.
Source-tree hashes, dependency versions, CPU placement, all case results, and
all within-block deltas are retained. The workload remains 1,000 memories,
REST hybrid/stub, eight clients, five seconds of warm-up, 30 seconds measured,
seed 20260904, and a 30-second direct scrape interval for C. RSS/scrape sampling
includes warm-up and final snapshots, identically to the existing probe.

The suite has a 600-second cap, plus bounded process-group cleanup. Missing,
failed, changed-corpus, insufficient-sample, or incomparable runs make the
suite inconclusive; none are silently excluded or replaced. R/A supplies an
empirical variability check, not a statistical confidence interval. Before
examining results, apply these conservative rules separately to each metric:

- Keep the existing throughput, per-operation p95, and RSS budgets unchanged.
- Normalize each within-block delta by that block's A-derived budget; retain
  the raw deltas and their actual median as well.
- Mark a metric inconclusive if any absolute R/A delta exceeds its budget,
  if candidate blocks straddle the budget, or if the candidate median is
  within the largest observed R/A variation of the budget.
- Otherwise classify the median against its budget. Any inconclusive metric
  prevents a comparison from passing; B/A and C/A remain independent gates.

`docker-compose.phase4-benchmark.yml` runs this one-shot job with the same
two-logical-CPU placement for every case. It has no external network, exposed
ports, production mounts, or restart policy, and uses bounded temporary
storage. Retrieve the final `OC_BENCHMARK_REPORT` from its container logs before
removing the job. This is a synthetic read-overhead check on the deployment
host, not a full production-capacity or Ollama/write-workload benchmark.
Exit zero means the report was written; only its `assessment` determines the
gate outcome.

The runner, curated `Dockerfile.performance`, and one-shot compose are built
and locally smoke-tested. After the upload's safety-review pause, the operator
said to continue and publication to the existing GHCR package was authorized.
Portainer deployed the immutable test image in disposable stack 204; actual
container inspection confirmed the intended isolation and CPU placement.

#### Sequential NAS result

All twelve cases completed in 505.56 seconds with **25,995 successful requests,
zero failures/timeouts**, identical unchanged 1,000-memory/vector corpora, and
successful C scrapes. The one-shot container exited zero without an OOM. The
final report matched all twelve independently fetched per-case log records,
and a local recalculation reproduced its assessment exactly. Report and
summary are retained under `data/performance/phase4-20260904/nas-sequential/`.

| Comparison | Median throughput loss | Search p95 delta | List p95 delta | OC RSS delta | Gate |
| --- | --- | --- | --- | --- | --- |
| B/A, metrics disabled | 4.678% | +7.143 ms | +0.213 ms | +0.633 MiB | Inconclusive |
| C/A, enabled/scraped | 8.344% | +12.240 ms | +0.624 ms | +1.648 MiB | Inconclusive |

The repeated A controls had throughput deltas of −0.843%, +0.662%, and
+5.331%; maximum absolute search/list-p95 changes were 14.079/4.741 ms.
Those controls exceeded the existing throughput/latency budgets, triggering
the predeclared noise veto. C's observed throughput loss exceeded 5% in all
three blocks, but this is not a clean causal estimate of instrumentation cost.
RSS passed; neither full overhead comparison cleared its gate. An OC tracking
update completed during block 1 B and may have added background load; no
cases were excluded. No more automatic repetitions or new-hardware requirement
follow from this result. Further profiling or optimization is a separate step.

The report was retained before deleting only the one-shot benchmark stack;
independent checks confirmed its removal and that production remained healthy
and unchanged at that checkpoint. Standard runtime metrics
remain off by default. No release, tag, or production deployment occurred.

#### Original local execution

The probe was completed for Phase 4 rather than treating its instrumentation
state flag as metadata. It now launches a validated local source root, sets the
disposable child's `OC_METRICS_ENABLED` state, records child working-set peaks,
and can run a bounded direct scrape loop that retains every attempted scrape
duration, including failures. The minimum scrape interval is 10 ms so the
retained report remains bounded. The clean A condition used detached
base revision `527f2294d254ff093ebedf71a42810f7a112967f`; B and C used the
current dirty working tree. All runs used the same fixed corpus of 1,000
synthetic memories, hybrid mode, stub provider, seed `20260904`, eight clients,
5-second warm-up, and 30-second measurement. Run order rotated A/B/C, B/C/A,
and C/A/B. Sanitized reports are retained under
`data/performance/phase4-20260904/`.

The A/B/C medians were:

| Comparison | Search p95 delta | List p95 delta | Throughput loss | RSS delta | Result |
|---|---:|---:|---:|---:|---|
| B versus A (metrics disabled) | +2.534 ms | +0.801 ms | 5.20% | 0.000 MiB | **Inconclusive / blocked** |
| C versus A (metrics enabled and scraped) | +4.617 ms | +0.005 ms | 6.22% | 0.000 MiB | **Inconclusive / blocked** |

The proposed limits are p95 increase no greater than the larger of 1 ms or
5% of A, throughput loss at most 5%, and RSS increase at most 10 MiB. B and C
exceed the throughput limit; C is the enabling decision and is therefore not
approved. Per the plan, the block-to-block throughput spread (B 2.63–8.33%, C
5.58–7.94%) is also treated as noise/inconclusive evidence, not as a reason to
relax the limit.

The matched scrape-responsiveness check passed on the controlled host. The
enabled-but-unscraped versus enabled-and-scraped runs used 150 seconds at eight
clients and produced 12,093/1,335 p99-eligible search/list samples. Scraped
minus control deltas were +1.726 ms search p99, +0.558 ms list p99, and
−11.114 ms maximum event-loop lateness; 1,555/1,555 scrapes completed with no
failures and a maximum scrape duration of 85.383 ms. The 100 ms stress interval
was intentional so the bounded run could exceed 30 scrapes; it is not the
deployment interval. The deterministic overlap/cancellation contract also
passed. These results do not override the blocked A/B/C overhead gate.

### Phase 4 retest — 2026-09-04

Three additional rotated blocks were attempted with the same fixed workload.
One clean-base A case in block 6 had 564 connection failures and was excluded
from gate calculations; its paired B and C reports are retained as diagnostic
evidence. Blocks 4, 5, and 7 were fully eligible, giving six valid matched
blocks when combined with the original 1–3. The valid within-block medians were:

| Comparison | Search p95 delta | List p95 delta | Throughput loss | RSS delta | Result |
|---|---:|---:|---:|---:|---|
| B versus A (metrics disabled) | +1.223 ms | +1.252 ms | 3.92% | 0.000 MiB | **Inconclusive / blocked** |
| C versus A (metrics enabled and scraped) | +5.202 ms | +2.143 ms | 5.90% | 0.000 MiB | **Inconclusive / blocked** |

Using the same six-block A medians, the p95 budgets were +6.611 ms for search
and +1.577 ms for list. B's median is within the throughput and p95 limits,
but its per-block throughput loss ranges from −3.62% to +8.33%. C exceeds the
throughput and list-p95 budgets, and its throughput range is −36.82% to
+12.90%. The A baseline also moved between roughly 102–109 completed requests
per second and 164–169 per second in adjacent retest runs; block 7's C case was
36.82% faster than its A case. This order/host-speed effect makes the retest
inconclusive, and negative loss is not evidence that instrumentation improves
performance. The release and enabling blocks therefore remain closed.

Retest reports, including the excluded case, are retained under
`data/performance/phase4-20260904/retest/`. The operator subsequently approved
the sequential NAS harness and repeated baseline controls described above to
address run-order/resource-state noise; thresholds must not be relaxed to
force a decision.

### Phase 4 affinity follow-up — 2026-09-04

A separate three-block matrix used explicit Windows process affinity to confine
each probe and its disposable server to the same two logical CPUs (mask `0x3`).
The one-CPU wrapper produced an internal probe error and was excluded from
evidence; the two-CPU pilot and all three rotated blocks completed with zero
application failures or timeouts. The run orders were A/B/C, B/C/A, and C/A/B,
with the same corpus, provider, seed, clients, warm-up, measurement duration,
and 30-second direct scrape interval as the earlier matrix. Each enabled case
completed its one scheduled scrape without failure; this was not a scrape-
responsiveness run.

The valid within-block medians were:

| Comparison | Search p95 delta | List p95 delta | Throughput loss | RSS delta | Result |
|---|---:|---:|---:|---:|---|
| B versus A (metrics disabled) | +5.119 ms | +0.243 ms | 3.91% | 0.000 MiB | **Inconclusive / blocked** |
| C versus A (metrics enabled and scraped) | +10.192 ms | +2.919 ms | 11.62% | 0.000 MiB | **Inconclusive / blocked** |

The A baseline still ranged from 150.83 to 163.83 completed requests per
second. B's throughput loss ranged from 0.18% to 14.08%; C's ranged from
8.69% to 16.18%. With median A p95 values of 98.384 ms for search and
22.407 ms for list, the corresponding 5% budgets were +4.919 ms and
+1.120 ms. B therefore narrowly exceeds the search-p95 budget as well as
showing an unstable throughput spread; C exceeds both p95 budgets and the 5%
throughput budget. Affinity did not remove the host/order effect, so this
follow-up does not clear either release or enabling gate.

Affinity reports are retained under `data/performance/phase4-20260904/pinned/`.

### Phase 4 same-run harness attempt — 2026-09-04

After the repository volume was restored following a reboot, the serialized-
setup process harness was checked with ruff, mypy, and 15 focused probe tests.
Its short A/B/C pilot passed with zero application failures or timeouts and
unchanged corpora. The full synchronized run then used the same fixed workload
as the earlier gate: corpus 1,000, eight clients, 5-second warm-up, 30-second
measurement, REST hybrid mode, stub embeddings, and a 30-second direct scrape
interval.

The full run was ineligible rather than a performance result. A, B, and C
recorded 2,438, 2,488, and 2,285 failed operations respectively; the
connection-failure counts were 2,206, 2,237, and 2,068. C's only scheduled
scrape also failed. A standalone clean-base A control at the same corpus and
client count completed with zero failures, so the failure is specific to the
three concurrent full probes on this host, not the corpus or baseline
revision. The sanitized diagnostic report is retained at
`data/performance/phase4-20260904/same-run/ABC.json`.

This attempt supplies no overhead delta and does not clear either release or
enabling gate. Repeating the same saturated concurrent setup is not justified;
the operator-approved next approach is sequential testing on CARLDOG-NAS, not
a requirement for another physical host. Metrics remain disabled by default, and
no release, deployment, rollback, or issue/PR mutation was run.

### Phase 4 resource-isolated same-run follow-up — 2026-09-04

To test the separately authorized resource-isolated path, the probe was
extended with one keep-alive REST connection per closed-loop worker and three
equal eight-logical-CPU partitions. The partitions rotate with the condition
order so A, B, and C each occupy every partition once across the three blocks.
The full workload and shared post-warm-up barrier were otherwise unchanged.
All three matrices were eligible: every condition had zero application
failures and timeouts, every corpus was unchanged, and the enabled C case had
successful scrapes with no failures. Reports are retained under
`data/performance/phase4-20260904/same-run/isolated-*.json`.

The within-block deltas were:

| Block/order | A throughput | B vs A throughput | C vs A throughput | B/C search p95 delta | B/C list p95 delta | B/C RSS delta |
|---|---:|---:|---:|---:|---:|---:|
| ABC | 135.700 req/s | +1.351% | −10.636% | +1.853 / −17.761 ms | −1.117 / +2.587 ms | −0.004 / −0.004 MiB |
| BCA | 174.433 req/s | +15.937% | +16.530% | +25.360 / +29.369 ms | −5.827 / −6.166 ms | −0.004 / −0.004 MiB |
| CAB | 153.067 req/s | −15.527% | +10.867% | −22.036 / +11.204 ms | +7.795 / +0.329 ms | −0.004 / −0.020 MiB |

**Aggregation correction:** recalculating the retained raw JSON gives median
losses of 1.351% for B and 10.867% for C. Median search-p95
deltas were +1.853 ms and +11.204 ms; median list-p95 deltas were −1.117 ms
and +0.329 ms. The previous narrative incorrectly reported maxima as medians.
Against median A p95 values of 110.434 ms for search and
15.284 ms for list, the 5% latency budgets are 5.522 ms and 1 ms. RSS stayed
within the 10 MiB budget. B's medians were within budget; C's throughput and
search-p95 medians exceeded budget. The signs and magnitudes reverse across
orders, so this is also noisy/inconclusive evidence rather than a clean
measurement of instrumentation cost.

Resource isolation therefore did not clear the release or enabling gate. No
additional concurrent matrix is planned. The operator-approved replacement is
the sequential CARLDOG-NAS protocol above, with repeated baseline controls;
dedicated hardware is not required. Metrics remain
disabled by default, and no release, deployment, rollback, or issue/PR
mutation was run.

At that milestone, release, tag movement, NAS deployment, and rollback mutations
were not run. The implementation was subsequently committed and pushed as
`682c68f0`; the runtime switch remains disabled by default.

Before deployment, record and retain the previous known-good image tag, digest,
build revision, and compatible configuration; rehearse both recovery paths on
a disposable instance. For an enabled-recorder/exporter-only failure, disable
`OC_METRICS_ENABLED`, recreate the same tagged service, and disable its scrape
target. If correctness, locking, startup, or performance regressions persist
with metrics disabled, restore the recorded previous image and configuration
instead: the switch does not remove new timing contexts or lock-observation
code. Verify the running package/build revision and REST/MCP read/write smoke
checks after either recovery. Stop scrapes against the previous image and
preserve the collector volume for diagnosis. This feature must introduce no
memory-database migration; rollback must not require restoring an older database
or discarding memories written since deployment. Actual deployment/rollback
mutations remain operator-authorized operations.

## Phase 4 remaining-work plan

**Status: 4A/4B and 4D are complete; the 4C run finished but its gate is
unresolved and retained-report integrity needs recovery. 4E/4F remain blocked.**
The implementation and tests landed in `682c68f0`; the original uninstrumented
comparator remains `527f2294`. The latest NAS measurements remain inconclusive.
Prior passing tests establish a starting point; they do not certify a future
changed candidate or its CI run.

The objective is to resolve the overhead evidence and produce a verified
release and observation report. CARLDOG-NAS remains the measurement/deployment
host. Runtime metrics
remain off by default, including after release; enabling the operator's
deployment is a separate configuration choice. Work is limited to this
instrumentation and its validation. Broader search/storage changes, a language
rewrite, new dashboards, alert routing, and new runtime dependencies are outside
this plan.

| Subphase | Work and deliverable | Exit condition | Planning allowance |
| --- | --- | --- | --- |
| 4A. Identify cost and noise | Source/profile comparison and NAS baseline repeatability report | Specific instrumentation cost or interference is evidenced, or a documented measurement limitation remains | One investigation session |
| 4B. Address evidenced cost | Small candidate patch and regression evidence, if justified by 4A | Correctness preserved and targeted cost reduced; otherwise record why no patch is warranted | One implementation session |
| 4C. Re-evaluate overhead | One complete sequential A/B/C/R report for a frozen candidate | B/A and C/A independently pass, fail, or remain inconclusive under existing rules | One 600-second suite plus setup/retrieval |
| 4D. Prove collection and recovery | NAS query evidence, access checks, and two rollback rehearsals on disposable targets | Retained history, error/idle distinctions, and recovery with data preserved are demonstrated | One verification session |
| 4E. Release and deploy | MINOR release, CI evidence, pinned deployment, and branch reconciliation | Applicable gates pass and running package/build identity and smoke checks match the release | One release session plus CI |
| 4F. Observe and close | Initial seven-day report, remaining unknowns, and final tracker state | Observation recorded honestly; unresolved failures or missing evidence remain explicit | Seven elapsed days plus one review |

The critical sequence is 4A → 4B when justified → 4C → 4E → 4F. Subphase 4D
can proceed independently, but NAS restarts, recovery drills, and tracking writes
must occur outside performance measurement intervals. Release also depends on
4D. Session allowances are checkpoints, not promises of completion or permission
for unlimited iterations.

### 4A — identify instrumentation cost and baseline variability

1. Verify the current repository/CI state and preserve the original NAS report.
   Record the baseline/candidate commits, source hashes, common dependencies,
   interpreter, probe settings, and image digest for every new diagnostic.
2. Inspect and profile the actual disposable OC request/worker paths for A, B,
   and C, with equivalent work. Include SQLite lock acquisition and nesting,
   search-stage timing, HTTP/MCP wrappers, histogram updates, label lookup, and
   recorder health updates. Existing code does timing and thread-local depth
   bookkeeping in `_observed_lock` even without recording; this is an
   investigation lead, not proof that it explains the measured regression.
   Profile the server workers, not just the load generator or its parent.
3. Keep profiler results diagnostic. Use bounded existing/standard-library
   tooling and report call counts and CPU/allocation evidence; profiled latency
   must never be substituted for an unprofiled acceptance measurement.
4. Before testing another candidate, run one baseline-only NAS calibration
   with three fresh A/R pairs using the existing workload and CPU placement.
   Retain every pair and apply the existing per-metric variability budgets.
   Record container resource limits and available host load/CPU/I/O evidence.
   Observe normal NAS services; avoid OC memory writes, deployments, builds,
   and active polling that adds workload during measurements. Buffer tracking
   updates until the interval ends.

**Exit:** a short attribution report names the next targeted change and the
evidence supporting it. If baseline variability still exceeds the budget,
retain the result and defer a full gate run until a concrete cause or protocol
change is identified. A quiet calibration is a readiness check, not acceptance;
the full suite must still pass its own repeated-baseline controls. Do not select
the best subset of pairs or repeatedly wait/run until one happens to pass.

### 4B — make only evidence-supported changes

First consider bypassing instrumentation-specific clocks, wrapper allocation,
and nesting bookkeeping when metrics are disabled, while retaining the original
RLock/transaction behavior. For enabled collection, consider bounded reuse of
label children or fewer redundant recorder operations only if the profiles
identify them as material. Preserve metric definitions, privacy limits, outcome
classification, failure visibility, and scrape cancellation/overlap guarantees.
Do not remove observations, sample events, or change histogram meanings merely
to meet the performance budget.

Use focused deterministic tests for each affected contract: disabled-path
bypass, nested transactions and concurrent writes, error/cancellation behavior,
exact enabled counts, and bounded labels. Run relevant tests after each patch;
run the full repository checks once the candidate is stable. Reuse unaffected
evidence, and rerun the responsiveness stress gate if exporter/recorder,
locking, request handling, or other changes could alter its result. Follow the
existing maximum-cardinality, p99-sample, overlap, and one-second scrape limits.
Use native Windows Python and Git Bash for local checks; WSL is not required.

**Exit:** a small reviewable patch with before/after diagnostic evidence and
passing correctness checks, or a documented no-patch conclusion. A local
microbenchmark improvement alone cannot clear B/A or C/A. Broader architecture
work requires a separate scope decision if targeted changes are insufficient.

### Phase 4A/4B execution checkpoint — 2026-09-05

The first local profile harness attempt was invalid because a reused stop
marker stopped the profiled server before measurement; it was excluded. After
the marker was corrected, a bounded server-side cProfile run covered A, B, and
C with fixed 1,000-memory corpora and zero request failures. Before the patch,
the retained top-time B entries included the REST metrics middleware
(`metrics.py:23 __call__`, 15,164 calls and about 1.000 seconds cumulative),
SQLite `_observed_lock` (74,566 calls and about 1.224 seconds cumulative), and
the SQLite instrumentation wrapper (37,283 calls and about 0.188 seconds
self time). Vector unpacking and hybrid search remained the dominant work, so
the evidence supported a narrow disabled-path change rather than broad
storage/search refactoring. Profiled throughput remains diagnostic and was
not used as acceptance evidence.

Before testing another candidate, Portainer MCP ran three fresh uninstrumented
A/R calibration pairs on CARLDOG-NAS. Every case used the immutable benchmark
image digest `sha256:d8e73c42c37d70630786d9ff71bd523b776e359e5acd940e2ef79f12789ae800`,
CPU placement `0-1`, network none, read-only/unprivileged execution, REST
hybrid/stub, eight clients, five seconds of warm-up, 30 seconds measured, and
seed `20260904`. All six cases completed with zero failures and the same
1,000-memory/vector corpus fingerprint.

| Pair | A req/s | R req/s | R/A loss | Search p95 delta | List p95 delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 76.7667 | 75.6667 | 1.433% | -2.826 ms | +0.938 ms |
| 2 | 76.2667 | 75.1333 | 1.486% | +0.474 ms | +1.036 ms |
| 3 | 74.1667 | 69.9333 | 5.708% | +27.078 ms | +3.597 ms |

The third repeated baseline exceeds the predeclared variability budget, so
calibration is inconclusive/readiness evidence only. No pair was selected or
repeated. The retained sanitized pair reports and timestamped logs are under
`data/performance/phase4-20260904/calibration/`.

The 4B candidate now skips the REST metrics middleware and MCP handler wrapper
when metrics are disabled, normalizes disabled SQLite recorders to no metrics,
and uses the original RLock without instrumentation timing/depth bookkeeping.
Enabled recording and RLock/transaction semantics are preserved. Focused
metrics contracts (14 tests), Ruff, formatting, and mypy pass. A post-patch
server profile completed; the retained top-time B list no longer includes the
REST metrics middleware or `_observed_lock`, while C retains its expected
enabled recorder work. This diagnostic result does not clear the NAS gate.
The next step was the frozen, unprofiled 4C sequential A/B/C/R run after the
candidate commit and full repository verification; its outcome is recorded
below. Runtime metrics remain off by default and production remains unchanged.

### Phase 4C execution checkpoint — 2026-09-05

**Evidence correction, found during forward planning on 2026-09-05:** the
retained JSON contains log timestamp text inside one condition value and two
metric keys. The current assessor rejects it with `condition state mismatch`
and returns no comparisons. The figures and independent-recalculation claim
below describe the earlier checkpoint; the saved artifact does not currently
reproduce that claim. Preserve it and recover verified evidence through
[4C.1](#4c-recovery-plan) before treating it as machine-verifiable evidence.

After explicit operator authorization, the committed 4B candidate
(`553a6e0b333574f716b783d90ca34419f3d90aae`) was published as a non-release
amd64 benchmark image. The immutable image reference used by Portainer was
`ghcr.io/carldog/openchronicle-mcp:phase4-4b-20260905-553a6e0b@sha256:a925745f4bf1c8645284276872b92adc83c70536c46c1e21b633ec5af8af2d2e`.
The candidate source hash was
`452d36e48cf7019b98f193a7f7e82e70fab8ae276f49015339582bb29ae920c9` and the
baseline hash was
`9d03ef95759d6b1f86d4b726aa4d1b062d775f15d2f133280fe9a63572c6f9ad`.

Portainer MCP created disposable stack 212 on CARLDOG-NAS with the frozen
security and placement settings: CPU set `0-1`, network none, user
`1000:1000`, read-only root, all capabilities dropped, no-new-privileges, no
volumes, and no ports. The unprofiled `ABCR`/`BCAR`/`CABR` suite completed all
12 cases with 27,272 successful requests, zero failures/timeouts, one
identical 1,000-memory/vector corpus fingerprint, and successful enabled
scrape checks. The container exited zero without OOM. The complete report was
reconstructed from Portainer logs, independently recalculated, and retained
with its summary under `data/performance/phase4-20260904/nas-sequential/`.

The independent result matched the runner: B/A median throughput loss was
0.129% with +0.121 MiB RSS, but B/A remained inconclusive because repeated-A
list-p95 noise reached 1.540 budget fractions. C/A median throughput loss was
7.769% with +2.258 MiB RSS, +9.367 ms search p95, and -1.182 ms list p95;
C/A was inconclusive overall under the existing veto. No threshold was
relaxed. Stack 212 was deleted and independently absent afterward; production
stack 151 remained pinned to `v3.3.0` with build revision
`7349f94ab8bd8b9a8c60e1def63ad4997f7f9a45`. Runtime metrics remain disabled
by default, and release/enabling remain blocked pending 4D and later gates.

### 4C — evaluate the frozen candidate on CARLDOG-NAS

Reuse `scripts/probe_sequential.py` and `docker-compose.phase4-benchmark.yml`.
Freeze the candidate, probe, source hashes, dependency set, image digest, and
measurement protocol before looking at results. Compare against the original
uninstrumented A, even if several candidate edits have occurred. Keep the
existing twelve cases (ABCR/BCAR/CABR), 1,000-memory corpus, eight clients,
hybrid/stub reads, warm-up, measurement duration, scrape interval, and CPU
placement. Any necessary protocol amendment must be documented before running
and must preserve the acceptance thresholds and comparable controls.

Run without profiling, retrieve all case records and the complete report,
verify corpus identity and application/scrape outcomes, and independently
recalculate the assessment. The existing limits remain: throughput loss at
most 5%, added per-operation p95 at most max(1 ms, 5% of A), and added OC RSS
at most 10 MiB. Apply the repeated-baseline veto and retain all attempted cases.
Exit zero from the container is not a passing performance gate.

| Evidence | Permitted next outcome |
| --- | --- |
| B/A and C/A pass | Proceed toward release and enabled collection after 4D and applicable responsiveness checks |
| B/A passes; C/A fails or is inconclusive | A metrics-disabled release may proceed after 4D; enabling and full Phase 4 closeout remain blocked |
| B/A fails or is inconclusive | Release of this instrumentation remains blocked, even with metrics disabled |

This remains a synthetic read-overhead gate. Report writes, real Ollama latency,
and production capacity as unmeasured; a passing result does not establish them.
If the suite remains inconclusive, deliver the evidence and a concrete decision:
defer rollout, undertake a separately scoped investigation, or explicitly
reconsider the acceptance policy. No threshold change or exception is implied.

### 4C recovery plan

**Status: bounded cycle finished with blockers, 2026-09-05.** This plan addresses the specific
remaining evidence and overhead problems. Its deliverable is a trustworthy
report classifying B/A and C/A separately, plus either a verified candidate or
a concrete unresolved limitation. A passing result is an outcome to establish,
not a promised result. The existing 4D evidence is retained, with affected
checks repeated if the candidate changes. The operator authorized execution;
publication and final acceptance are complete, but the gates did not pass.
No release is implied and no automatic rerun is authorized.

The starting evidence has three distinct limitations:

- The retained `phase4c-20260905-4b-report.json` parses as JSON but has timestamp
  contamination in `runs[4].report.instrumentation_state`, the search-throughput
  key in `runs[8]`, and the C/A search-p95 median key. Re-running `assess()` against
  its cases returns `inconclusive` with no comparisons. Syntactic JSON validity
  alone is insufficient evidence integrity.
- The earlier B/A summary reports 0.129% median throughput loss, but a repeated
  A list-p95 delta of 1.540 ms exceeds its 1-ms budget. There are only 201–228
  list samples per case. Sampling precision and shared-host interference are
  hypotheses to investigate; the file does not establish which caused the
  variation. B/A also crossed the list-p95 budget in one block.
- The earlier C/A summary reports 7.769% median throughput loss, with all three
  reported block losses above 5%, and +9.367 ms median search p95. The aggregate
  was inconclusive, but its throughput metric was classified as failing; that
  distinction must survive report recovery. A noisy latency metric cannot be
  used to dismiss the observed throughput regression. RSS was within budget.

| Step | Work and evidence | Exit / bound |
| --- | --- | --- |
| 4C.1 Evidence and report transport | Preserve the original; validate or replace it; prove report retrieval round-trips without corruption | One bounded recovery attempt and a tested artifact path; unavailable originals are explicitly unverified |
| 4C.2 Baseline repeatability | Freeze revised timing and run three fresh A/R pairs on CARLDOG-NAS | One calibration, 900-second total cap; failing controls block the final comparison |
| 4C.3 Enabled-cost diagnosis | Reuse profiles, then compare disabled, enabled-unscraped, and enabled-scraped request paths | One profile set and one paired scrape diagnostic, each at most 600 seconds |
| 4C.4 Targeted candidate | Optimize only the evidenced instrumentation cost; verify observable contracts | One patch batch and one before/after diagnostic; no improvement means no speculative patch |
| 4C.5 Frozen acceptance | Run the revised twelve-case A/B/C/R protocol and independently validate all evidence | One suite, 1,800-second total cap; every attempted case retained |
| 4C.6 Disposition | Record per-metric results, release eligibility, evidence reuse, and remaining limitations | Stop with a release-ready candidate or an explicit blocker; no automatic rerun |

#### 4C.1 — establish evidence integrity first

Hash and preserve the original report and companion summary unchanged. Attempt
recovery from independently retained raw case records, original runner output,
or another authoritative copy. The old benchmark container has been removed;
do not assume its logs are still available. If recovery needs timestamp removal,
write a separate derived file and retain the exact transformation, provenance,
and before/after hashes. Never repair fields solely to match the expected
performance figures. If no independent source or verifiable framing survives,
label the old artifact unverified and supersede it with the next valid run.

For subsequent runs, retrieve the report as bytes with a producer SHA-256 and
length. Prefer a direct file/archive retrieval from the stopped disposable
container, using a dedicated output location that survives process exit until
retrieval. If the available Portainer MCP surface only supports logs, use
bounded, numbered encoded chunks with total count, length, and checksum, and
verify the complete round trip before measurement. Never concatenate presumed
JSON log fragments or strip timestamp-looking text globally. Remove disposable
resources only after artifact validation.

Validate the report schema, exact condition states/order, required numeric
fields, finite values, counts, corpus identity, source/probe hashes, interpreter,
dependencies, CPU placement, timing, and measured scrape evidence. Recompute
the gate from cases, independently cross-check its arithmetic, and compare the
saved assessment. Add deterministic regression cases for the observed embedded
timestamp, split/missing/duplicate chunks, checksum mismatch, malformed state,
and an assessment that disagrees with cases. Preserve the existing aggregation
rule; present failed metrics even when the comparison is inconclusive overall.

#### 4C.2 — calibrate one amended measurement protocol

Predeclare a versioned protocol before looking at new performance results.
Keep the original uninstrumented `527f2294` source, the 1,000-memory fixture,
eight keep-alive clients, REST hybrid/stub profile, seeded 90% search / 10% list
mix, CPU set `0-1`, common dependencies, and fresh process/database per case.
Retain actual operation counts and query mix. Use the same final harness for
every condition. Document any necessary harness correction before calibration;
do not pool old 30-second cases with the amended runs.

Proposed timing: 15-second warm-up and 90 seconds measured per case, with a
180-second case cap including setup/drain/cleanup. Three A/R pairs have a
900-second suite cap; the final twelve cases have a 1,800-second suite cap.
These explicitly replace the original five/30-second timing and 600-second
suite limit only for this proposed protocol. They require parameterized runner
timings and parent/child deadlines; the current runner hardcodes the old values.
Add a baseline-only calibration mode to `scripts/probe_sequential.py` that
runs A/R pairs through the same case launcher and report checks as acceptance.
Retain cleanup time in every deadline and mark unstarted cases after a timeout.
Do not extend a case dynamically to obtain more favorable samples.

The longer window is intended to increase list observations and capture several
30-second scrape cycles. It cannot guarantee lower host noise. Keep the existing
minimum 100 samples per operation and existing uncertainty rules; report actual
counts and do not claim confidence intervals from the empirical veto. Align
scrape accounting with the measured interval, record timestamps/durations for
every attempt, and exclude setup/warm-up activity from measured scrape success.
For C schedule scrapes at measured offsets 0, 30, and 60 seconds; all must
complete successfully. Apply identical lightweight resource sampling in A/R/B/C.

Use read-only pre/post host observations for CPU topology, available frequency,
load, context switches, and I/O; identify unsupported readings explicitly.
CPU pinning is not exclusive CPU ownership, as the
[pyperf system guidance](https://pyperf.readthedocs.io/en/latest/system.html)
distinguishes. Avoid OC tracking writes, builds, deployments, and active remote
polling during measured intervals; buffer results locally until each bounded
job ends. Production workloads continue normally. Kernel tuning, service
stoppage, new monitoring agents, or different hardware are not prerequisites.

Every calibration pair must be eligible, and the maximum absolute A/R change
for each metric must remain within that metric's existing budget. Retain all
pairs. If calibration fails, stop the NAS acceptance path and report the
measurement limitation; 4C.3/4C.4 can still produce useful diagnostic work.
A passing calibration only permits the final comparison; that comparison must
independently pass its own repeated-baseline and block-variation rules.
Changing the common harness, dependencies, baseline, CPU placement, or timing
after calibration invalidates its readiness evidence. Record the need for a
new protocol decision instead of silently using the old calibration.

#### 4C.3 — attribute enabled instrumentation cost

Start from `diagnostics-after-4b/` and the committed 4B candidate. The retained
C profile includes 44,693 `_safe` calls and 31,128 `observe_store_lock` calls;
these are leads, not isolated CPU-cost estimates. Check profiling coverage of
the ASGI thread and worker threads, normalize counts/self time by completed
operations, and avoid adding overlapping cumulative timings together. Local
profiling guides changes; Linux/NAS evidence must establish deployment impact.

Use B (disabled), U (enabled without scheduled scrapes), and C (enabled with
30-second scrapes) for diagnosis. U is additional diagnostic evidence; A stays
the release comparator. Reuse existing profiles where sufficient; collect at
most one additional profile set. If scrape cost remains unresolved, use one
unprofiled U/C/C/U diagnostic with the proposed timing, capped at 600 seconds.
It does not replace the A/B/C/R acceptance run.

Identify the contribution of repeated label lookup, allocation of callbacks
and bounded sets, histogram updates, recorder-health bookkeeping, observed
lock wait/hold paths, and exporter serialization. The source performs these
operations repeatedly, but their materiality must be measured. Caching known
label children is a candidate consistent with
[Prometheus inner-loop guidance](https://prometheus.io/docs/practices/instrumentation/#inner-loops).
If evidence cannot isolate a tractable cost, retain that limitation and stop
optimization at this checkpoint.

#### 4C.4 — implement and verify one targeted patch

Prefer bounded reuse of metric children and immutable label sets, or removal
of proven redundant allocation/bookkeeping. Keep caches per recorder and bound
keys after normalization; account for any startup/RSS/cardinality effects.
Preserve exact counts, buckets, units, failure/outcome labels, health/error
visibility, lock semantics, and disabled-path bypass. Reducing sample frequency,
dropping metrics, changing lock duration boundaries, or relaxing access checks
changes the feature contract and is outside this optimization batch.

Test exact concurrent increments, nested transactions, final in-flight gauges,
error-to-recovery health transitions, unknown-label normalization, registry
isolation, bounded cache growth, and scrape overlap/cancellation. Use deterministic
fixtures to prove semantics rather than timing assertions in shared CI.
Require a same-method before/after diagnostic showing the targeted cost reduced,
then run the repository correctness, lint, type, Markdown, and pre-commit gates.
Use native Windows Python/Git Bash locally; WSL is not required.

Start with `pytest tests/test_metrics.py tests/test_probe_performance.py
tests/test_probe_sequential.py`; once the candidate is stable, run `pytest`,
`ruff check src tests scripts`, `ruff format --check src tests scripts`,
`mypy src tests --config-file=pyproject.toml`, `npm run lint:md`, and
`pre-commit run --all-files`. Record outcomes and avoid duplicating an unchanged
check already covered by the final hook run.

#### 4C.5 — perform one frozen comparison

Proceed only after evidence retrieval works, calibration passes, and any
candidate change passes correctness checks with a credible diagnostic benefit.
If no patch is warranted, record that decision and the justification for
remeasuring the unchanged candidate under the amended protocol. Freeze the
application/probe commits, source and artifact hashes, image digest, dependencies,
timing, and settings before execution. Publish a uniquely identified non-release
amd64 image through the established GHCR workflow and deploy the disposable
job through Portainer MCP using the existing session authorization.

Run `ABCR`, `BCAR`, `CABR` sequentially under the amended timing. Retrieve and
validate all twelve cases and the complete report before deleting the job.
Independently calculate each within-block delta, the three-block median, the
control-noise fraction, and pass/fail/inconclusive result. Keep throughput loss
at most 5%, added p95 at most max(1 ms, 5% of A), and added OC RSS at most
10 MiB. Do not drop the list endpoint, exclude a slow block, pool results from
other candidates, or weaken the baseline veto.

Recorder/exporter/locking changes also require the existing maximum-cardinality
scrape-responsiveness gate: at least 30 successful scrapes, at least 1,000
successful samples per operation for p99, and the original duration/lag/p99
budgets, within one 600-second invocation. Failure or insufficient samples
remain explicit. Assess the impact on 4D and repeat affected access, history,
and recovery checks on the final candidate; unchanged evidence may be reused
with an explicit source/configuration comparison.

#### 4C.6 — decide and stop

| Verified result | Next step |
| --- | --- |
| B/A and C/A pass; responsiveness and applicable 4D checks pass | Continue the existing 4E release workflow, then 4F observation when the selected deployment has collection enabled |
| B/A passes; C/A fails or remains inconclusive | A metrics-disabled release is eligible under the existing policy; enabled collection and full Phase 4 completion remain blocked |
| B/A fails or remains inconclusive, or report integrity cannot be established | Defer the instrumentation release and retain the exact blocker |

End after this single recovery/calibration/diagnostic/patch/acceptance cycle.
Further architecture changes, benchmark redesign, or reconsideration of the
acceptance policy require a new scoped decision. Runtime metrics remain false
by default. Update the same OpenChronicle work record with the disposition,
verification, artifacts, and verified commit references; issue status remains
separate. No automatic rerun or seven-day monitoring task is created here.

### 4C recovery execution checkpoint

The original damaged report and summary were preserved and hashed. One bounded
recovery attempt found no complete independent source; they remain unverified.
`scripts/probe_artifact.py` now transports short numbered base64 records with
byte length and a producer SHA-256. Retrieval rejects missing, duplicate, split,
mixed, or corrupted chunks, duplicate JSON keys, and non-finite numbers. The
consumer validates case identities/counts, source/harness/runtime metadata, the
measurement protocol, and the recalculated assessment. The runner retains every
scheduled case, including explicit errors/skips, and emits evidence before its
final validation so a validator failure does not erase the report.

The v2 runner implements `--suite-mode calibration|acceptance`, with the
15/90-second timing and 900/1,800-second caps above. Scrapes and RSS sampling now
start at the measured client barrier, after warm-up; C schedules scrapes at
0/30/60 seconds and retains every attempt's time/duration. Unavailable host
observations are explicit. An end-to-end Portainer smoke verified checksums,
persisted Compose, source identities, and isolation before measurement.

The single NAS calibration completed all six cases in approximately 674 seconds:
41,441 requests, zero failures/timeouts, matching corpora, and 672–685 list
samples per case. Independent arithmetic confirmed every A/R control within its
unchanged budget:

| Pair | R/A throughput loss | Added search p95 | Added list p95 | Added RSS |
| --- | ---: | ---: | ---: | ---: |
| 1 | -0.318% | +1.367 ms | +0.303 ms | -0.578 MiB |
| 2 | -0.509% | -1.703 ms | +0.249 ms | +0.164 MiB |
| 3 | -1.284% | -2.683 ms | -0.765 ms | -0.266 MiB |

**Validation correction and decision:** the job exited 1 after writing the
complete report because the new validator compared the probe's hexadecimal CPU
mask string (`"0x3"`) with an integer. The probe and inspected container both
used CPUs 0–1. The corrected check accepts the actual probe contract; a
regression test now obtains that field from the real metadata builder. The
unchanged 143,559-byte report verifies against producer SHA-256
`5ce3b6eb8065aece821203fa60d1bc521fed5708e816eef2c6490be917551af9` and passes
semantic validation/recalculation. AST comparison confirms only `validate_report`
changed; launch, workload, sampling, assessment arithmetic, and the other two
harness files are unchanged. **Operator decision, 2026-09-05:** reuse this
verified calibration for final acceptance. This is an explicit validation-only
exception to the frozen-harness rule, not a change to measurement or acceptance
budgets. No repeat calibration is authorized or needed. The corrected harness
and optimized candidate will be frozen before the single final comparison.

Enabled-cost work reused the earlier profile without treating overlapping
cumulative times as additive CPU estimates. Its 79,256 label lookups included
62,256 from lock observations; the profile includes warm-up, so its 1,806 recorded
HTTP completions are distinct from the 1,472 measured requests. No exporter
serialization was captured. One local U/C/C/U diagnostic completed 47,713
requests with zero failures and all six scheduled C scrapes; its 8.388% U/U
throughput drift prevents attributing the apparent 4.623% C/U loss to scraping.
It is diagnostic only and is not pooled with NAS evidence.

One targeted patch lazily reuses normalized lock, search-stage, and in-flight
metric children per recorder, with fixed bounds of 4/5/3 cache entries.
Exact observations, histogram buckets, error/health behavior, and disabled paths
are retained. A paired recorder-only diagnostic reduced median CPU time from
0.328125 to 0.1875 seconds per 5,000 synthetic cycles (42.857%); its profiled
cycles had 40,000 label lookups before and zero after priming the new caches.
This establishes a targeted cost reduction, **not whole-application overhead**.
Concurrency, counts, gauge balance, cache bounds/isolation, and error recovery
have regression coverage. The full suite passed 932 tests before the final
validator-only correction; 49 artifact/validator tests passed afterward, with
Ruff and mypy clean. The working tree contains 933 tests.

Evidence and reproduction inputs are retained under
`data/performance/phase4-20260904/recovery-20260905/`, including
`calibration-report.json`, `validation-correction.json`, `recorder-cost.json`,
the four enabled-cost reports, and both disposable Compose files. Retrieve a
future report with `python -m scripts.probe_artifact --logs <logs> --out <new-report>`;
the output path must not already exist. Both disposable stacks (217/218) were
removed only after evidence retrieval. Production remains healthy on v3.3.0,
build `7349f94ab8bd8b9a8c60e1def63ad4997f7f9a45`; the stopped 4D stack/history
remains untouched. Runtime metrics stay off by default. Publication and final
comparison were pending at this checkpoint; their completed disposition follows.
The candidate is not released and 4E/4F remain gated.

### 4C recovery final disposition

**2026-09-05 — this single bounded cycle is finished; release and enabled
collection remain blocked.** The operator approved reuse of the intact passing
calibration after the validation-only CPU-mask correction. Candidate commit
`ddd21dee87c647d6693368099b19b1d14da66c74` was frozen locally and published only as
`ghcr.io/carldog/openchronicle-mcp:phase4-recovery-20260905-ddd21dee`, digest
`sha256:84687ea06ddae1603d8a21c0c9efa0b3a993c6d393884ce528fd20f56def4240`.
The registry manifest, amd64 platform, embedded source/harness hashes, and common
dependency image were verified. No Git push, release tag, `latest` movement,
production deployment, or runtime enablement occurred.

Disposable NAS stack 219 ran the unchanged `ABCR / BCAR / CABR` protocol from
22:09:24 to 22:31:51 UTC (1,346.8 seconds, below the 1,800-second cap). Its
pre-harness inspection delay was outside measurement. All twelve cases were
eligible: 75,786 successful requests, zero errors/timeouts, identical corpora,
305–673 list samples per case, and all nine scheduled C scrapes completed.
The container exited 0 without OOM or restart. All 145 transport chunks yielded
294,930 bytes matching producer SHA-256
`883a1649965d9a8b4ede89d568c1503d4760bc3ce8768a9eb350db237497b290`.
Semantic validation and separate arithmetic matched the saved assessment;
source, harness, runtime, protocol and timing identities matched the freeze.

| Comparison | Median throughput loss | Median search p95 delta | Median list p95 delta | Median RSS delta | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| B/A — disabled | 0.399% | +0.786 ms | +0.554 ms | -0.203 MiB | Inconclusive |
| C/A — enabled/scraped | 6.392% | +8.327 ms | +0.181 ms | +2.133 MiB | Inconclusive |

The final repeated baseline fell from 76.200 to 35.556 requests/second:
53.339% loss, +175.427 ms search p95, and +78.091 ms list p95. The maximum
control-noise fractions were 10.668/25.556/78.091 for throughput/search/list;
RSS remained within budget. The first two baseline controls stayed within
budget. No block was discarded. The last R case's one-minute NAS load reading
rose from 1.73 to 15.10; this supports a host-interference concern without
identifying its cause. CPUs 0–1 were unchanged (sibling threads on one core),
not exclusive CPU ownership; CPU/I/O pressure counters were unavailable.

All three observed C throughput losses (8.475%, 6.392%, 5.716%) exceeded 5%,
and all three C search-p95 deltas exceeded their budgets. These observed
breaches are retained even though the repeated-baseline veto classifies those
metrics as **inconclusive**, not a validated fail. B's first block also crossed
both p95 budgets. Neither comparison is release evidence under the unchanged
policy; targeted recorder CPU savings do not establish acceptable app overhead.

The final local full-cardinality responsiveness invocation completed in
545.8 seconds, with 3,648 series, eight clients, and one-second stress scrapes.
Its four matched REST/MCP cases completed 37,174 requests and 250 scrapes with
zero failures. REST list p99 increased **9.086 ms against a 5-ms budget**;
MCP list samples were only **733/736**, below the required 1,000, so their p99
comparison is inconclusive. Search p99, scrape duration (maximum 102.943 ms),
and actual ASGI-loop lag deltas (REST +1.074 ms, MCP +6.134 ms) passed.
Gzip was unsupported; identity/gzip requests both returned uncompressed 200s.
A separate bounded full-cardinality overlap/cancellation check passed.
These results are not pooled with NAS overhead evidence. The earlier local
responsiveness pass does not clear this final candidate's failed/incomplete gate.

4D reuse is explicit: only normalized recorder-child caching changed from the
passed candidate. AST/source comparison confirmed unchanged registry labels,
buckets, exporter/worker ownership, error/health bookkeeping, access guards,
storage/schema, dependency declarations, and collector/rollback configuration.
The changed recorder paths have exact-count, concurrency, bounded-cache and
recovery tests plus the final runtime checks. No new history/restart/rollback
experiment is claimed. Stack 216 remains stopped with its history preserved.

Evidence is retained under `data/performance/phase4-20260904/recovery-20260905/`:
`acceptance-freeze.json`, `acceptance-report.json`, `acceptance-independent.json`,
`acceptance-closeout.json`, `responsiveness-verdict.json`, the raw stress reports,
and `phase4d-impact.md`. NAS stack 219 and both local diagnostic containers were
removed only after verification. Production remained healthy on v3.3.0, build
`7349f94ab8bd8b9a8c60e1def63ad4997f7f9a45`, with metrics off.

**Stop condition:** defer the instrumentation release. Repeatability under NAS
load, residual enabled-path cost, the REST list-tail breach, and sufficient MCP
tail sampling require a new scoped decision. No automatic calibration, retest,
optimization batch, deployment, or monitoring task follows this cycle.

### 4D — close NAS collection, access, and rollback evidence

Discover the observation stack dynamically through Portainer MCP and confirm
its current identity/configuration before operating on it. First inspect any
retained samples and restart timestamps: existing evidence may close the gap
without repeating a restart. If insufficient, record a fresh pre-restart sample,
restart only the disposable OC service, and query a fixed time range spanning
the restart. Retain actual sample timestamps before and after the restart,
`up`, build identity, and counter-reset/process-start evidence. Target recovery
alone does not establish historical retention. Preserve the Prometheus volume.

Demonstrate healthy idle traffic separately from an unavailable target: use a
bounded outage long enough for at least two scheduled scrapes, then restore
the test service and confirm recovery. Check scrape-failure visibility and
missing-series behavior. Verify REST/MCP and metrics allowed/rejected Host
behavior; exercise valid/missing/invalid bearer credentials on a disposable
authenticated configuration with a throwaway secret. Store only sanitized
results. Reuse checks tied to the final candidate when unchanged; repeat affected
checks if the candidate or deployment configuration changes.

Rehearse both documented recovery paths on disposable data: disable metrics on
the candidate and stop its scrape target; then restore the previous known-good
image/configuration for a fault that persists when metrics are disabled. Record
the previous tag, digest, and build revision beforehand. Confirm REST/MCP
read/write behavior and retain a synthetic memory created under the candidate
through rollback. Require no database migration or old-database restore.

**Exit:** a compact evidence checklist passes history, idle/outage, access, and
both recovery checks. Retain reports before removing only disposable resources
created for these checks; identify any observation stack retained for later use.

### Phase 4D execution checkpoint — 2026-09-05

After reboot, dynamic Portainer inventory showed no retained observation
stack, so a new disposable observation stack was created as stack `216` with
separate data/config/output volumes, a throwaway authenticated configuration,
and Prometheus v3.14.0. The OC target used the published non-release 4C
benchmark image by immutable digest, with the candidate source tree selected
explicitly for the candidate checks. The Prometheus container and its named
history volume were kept unchanged across the target restart and rollback.

The candidate passed authenticated REST and streamable-HTTP MCP initialize,
read, search, pin, and write checks. The bounded access matrix observed the
documented contracts for both REST and MCP/metrics paths: valid credentials
with an allowed Host returned `200`, an allowed Host with missing credentials
returned `401`, invalid credentials returned `403`, and a rejected Host
returned `421`. The idle target produced healthy scrapes and recorder-health
samples. During a bounded disposable-target outage, Prometheus retained
`up=0` and zero scraped samples for 12 consecutive five-second samples, and
`absent_over_time(oc_metrics_recorder_healthy[25s])` returned `1`; after
restart, `up=1`, samples resumed, and recorder health returned. A fixed query
range retained pre-outage, post-restart, and post-rollback history, with
process-start changes providing the restart identity.

Both recovery paths passed. Disabling metrics made the metrics route return
`404` while REST/MCP reads and writes continued, and stopping the disposable
target produced the expected Prometheus gap. Restoring the known-good
`v3.3.0` image/configuration removed the candidate source override; the
candidate-created synthetic memories remained readable and subsequent
REST/MCP read/write smoke checks passed. No database migration or old-database
restore was used.

The sanitized report and summary are retained under
`data/performance/phase4-20260904/phase4d-20260905/`. Both disposable
containers were explicitly stopped after verification; stack `216` and the
Prometheus history volume remain for later inspection. Production stack `151`
remained on `v3.3.0`, healthy and unchanged, and runtime metrics remain off
by default. The 4C overhead gate is still inconclusive, so no release,
production deployment, or metrics-enabling decision follows from this check.

**Exit:** 4D collection, access, idle/outage, and both recovery checks passed;
4E/4F remain gated by the inconclusive 4C overhead result and explicit release
authorization.

### 4E — release and verify the selected deployment

Recheck the final candidate's gates and CI. Run `pytest`,
`ruff check src tests scripts`, `ruff format --check src tests scripts`,
`mypy src tests --config-file=pyproject.toml`, `npm run lint:md`, and the
repository pre-commit checks as required for the final changed files. Update
release/version/changelog, stability, plan, status, and sprint documentation
together, maintaining AGENTS/CLAUDE parity. Merge forward into `v4/develop`
through the existing workflow and verify its tests without changing the planned
v4 release decision. Changes after measurement need an impact review and a new
gate run if they affect the measured code, dependencies, or launch behavior.

Prepare the MINOR tag and concrete rollout record, including image digest,
selected metrics configuration, previous image/configuration, and rollback
triggers. Execute release/deployment when authorized, using existing session
authorization where applicable. Wait for the tagged image's required CI gates
before changing `OC_TAG`; independently verify the deployed package/build
revision, REST/MCP smoke, Host/access behavior, and collection state. Runtime
defaults stay false. An enabled deployment additionally requires C/A and scrape
responsiveness to pass. Correctness, startup, access-control, or persistent
performance failures trigger the rehearsed recovery procedure.

### 4F — observe, report, and close

After verified deployment with collection enabled, start the initial seven-day
window and record its exact bounds. Observation follows deployment; it is not
a prerequisite that must somehow be accumulated before enabling collection.
Review request counts/mix, latency with sample counts, scrape health/gaps,
recorder errors, process resources/restarts, and available maintenance outcomes.
Do not create live errors or writes merely to populate charts. Report low-volume
or missing outcomes as unknown; they cannot validate percentiles or job reliability.

If scheduled follow-up is requested, use one thread heartbeat daily, limited to
seven days with a final review and stop condition. Keep unchanged/non-actionable
state quiet; report actionable failure, completion, or a required decision. If
no follow-up is requested, record the review date and end the interactive work.
Day seven provides an initial baseline; a full week-over-week comparison needs
two populated, comparable seven-day windows and is not a day-seven exit gate.

Close Phase 4 only when the applicable engineering gates, deployment/recovery
checks, and initial observation report are evidenced. A disabled-only release
or an observation period not yet accumulated is partial completion. Update the
same OpenChronicle work record with scope, verification, commit/release references,
remaining limitations, and work status; issue status changes only if explicitly
requested and verified.

### Execution bounds and handoff

Each diagnostic invocation has a 600-second cap; the calibration and full gate
are separate bounded invocations. The proposed initial investigation allows
one calibration, one profile set, one targeted patch batch when warranted, and
one full gate after readiness is established. Every command/external wait has
a finite checkpoint; follow the repository's retry limits. Do not repeat an
unchanged matrix or automatically begin another optimization cycle. If a cap,
failed gate, or unresolved limitation prevents completion, retain the artifacts
and hand off the specific blocker and smallest next decision.
The adopted [4C recovery plan](#4c-recovery-plan) explicitly amends calibration
and full-suite timing/caps for its next cycle; the existing protocol and its
historical results are not retrospectively changed.

## Operator release exception (2026-09-24)

This design says an inconclusive B/A (disabled-path) comparison blocks
releasing the instrumentation, even with metrics off. B/A remains
inconclusive. The measured median throughput losses were 0.129% (4C) and
0.399% (4C recovery), but the repeated-baseline noise veto prevents a verdict.
The v3.4.0 correctness fixes build on the metrics hooks and do not cherry-pick
onto v3.3.0 cleanly.

The operator granted an explicit exception so that v3.4.0 can ship from
`main`, for these reasons:

- metrics stay off by default (`OC_METRICS_ENABLED=false`);
- the disabled path has the 4B bypass;
- the measured disabled-path losses sit inside host noise.

The exception covers release only. It does not cover enabling metrics in
production, which still needs the unchanged C/A, responsiveness and 4E/4F
gates. The tagged release is not deployed by this decision.

## Completion and subsequent decisions

The planning deliverable is complete, Phases 1–3 are implemented, and Phase 4
has been evaluated and retested; implementation was committed in `682c68f0`.
The proposed remaining-work sequence is above. The current verification covers the
dependency, disabled default, exporter guards, bounded labels, registry
isolation, reentrant lock timing, REST/MCP instrumentation, embedding/search
stages, maintenance events, scrape cancellation/overlap behavior, Prometheus
YAML, compose configuration, the query/runbook contracts, the disposable
Docker scrape/restart smoke check, the rotated A/B/C matrix, and the matched
scrape-responsiveness run, the six valid matched retest blocks, and the three
valid two-CPU-affinity follow-up blocks, the post-reboot same-run pilot plus
its ineligible full matrix, and the three eligible resource-isolated same-run
blocks. The A/B/C overhead gate remains inconclusive and blocks
release/enabling. Phase 4D then passed on disposable NAS stack `216`: fixed
Prometheus queries retained history across an OC restart and rollback, idle
and outage states were distinguished, the REST/MCP/metrics access matrix
matched the documented `200`/`421`/`401`/`403` contracts, and both recovery
paths preserved data and restored service. The sanitized report and summary
are retained under
`data/performance/phase4-20260904/phase4d-20260905/`; both disposable
containers are stopped and the history volume is preserved. Production stack
`151` remained healthy and unchanged. No production release or release-tag
performance observation window is claimed.

After adoption, implementation completion requires the Phase 1–4 engineering
gates, a verified deployment if authorized, and explicit disclosure of observation
windows not yet accumulated. If deployment is not authorized, hand off the
verified implementation as awaiting deployment rather than claiming it live.

Baseline results should lead back to design 0007: investigate SQLite changes
when lock waiting demonstrably explains unacceptable latency; investigate
provider concurrency when provider queuing dominates; consider a vector-store
change when loading/scoring grows with the corpus. Set production latency
objectives from measured workload and operator needs. A programming-language
change requires separate evidence that application CPU is the relevant limit.

Per-query SQL tracing, distributed tracing/OTel, cross-host availability
monitoring, new dashboards/services beyond the collector, and performance
optimizations remain subsequent decisions. The sequential CARLDOG-NAS test is
complete as an attempted run; the [4C recovery plan](#4c-recovery-plan) now
specifies evidence recovery, repeatability, enabled-cost attribution, and one
bounded candidate comparison. The recovery checkpoint above records the work
and pending calibration-disposition decision. The
post-reboot non-isolated same-run barrier was invalidated by concurrent
transport saturation, and the equal-CPU-partition follow-up remained noisy and
over budget; process affinity on this host was already insufficient. Do not
enable the runtime switch in the operator's deployment until the overhead,
responsiveness, and release-readiness gates pass. The initial observation
window then follows the verified deployment. Phase 4E/4F remain pending and
are gated by the inconclusive 4C result and explicit release authorization.
