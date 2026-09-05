# Application Performance Measurement

**Status:** PHASE 4 EVALUATED — the Phase 1–3 implementation and local
controlled-host verification are complete; the A/B/C overhead gate is
inconclusive and blocks release/enabling. A post-reboot same-run harness
attempt without resource isolation was ineligible because three concurrent
full probes saturated the local transport; a resource-isolated follow-up
completed three eligible but noisy blocks. Live deployment observation has
not started.
**Date:** 2026-09-04.

**Work key:** `CarlDog/openchronicle-mcp:work-item:performance-observability-plan`.
This identifies the planning work, not a GitHub issue or an approved build.

**Revision:** 2026-09-04 — incorporates the five adversarial-review findings,
records the Phase 1 implementation, the Phase 2 implementation (probe
throttling, corpus drift, disabled-path overhead and rollback, scrape
responsiveness, all-attempt scrape-duration retention, and backfill failure classification), the Phase 3 local
collector configuration, and the Phase 4 controlled-host gate and retest
results, including the post-reboot same-run harness attempts. Metrics remain
disabled by default; local responsiveness passed, while the overhead gate
remains inconclusive and live release/deployment observation is pending.

## Recommendation and intended outcome

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
runbook. Phase 4 probe verification was then run locally; it does not authorize
release, deployment observation, or enabling the runtime switch.

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
  explicitly started backfill is `operator_backfill`; its completion is recorded
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
after the OC restart. Live NAS scrape/restart behavior remains a Phase 4
verification gate.

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
independent checks confirmed its removal and that production and the existing
observation stack remained healthy and unchanged. Standard runtime metrics
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

Release, tag movement, NAS deployment, and rollback mutations were not run.
The working tree remains uncommitted, and the runtime switch remains disabled
by default.

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

## Completion and subsequent decisions

The planning deliverable is complete, Phases 1–3 are implemented, and Phase 4
has been evaluated and retested in the working tree. The current verification covers the
dependency, disabled default, exporter guards, bounded labels, registry
isolation, reentrant lock timing, REST/MCP instrumentation, embedding/search
stages, maintenance events, scrape cancellation/overlap behavior, Prometheus
YAML, compose configuration, the query/runbook contracts, the disposable
Docker scrape/restart smoke check, the rotated A/B/C matrix, and the matched
scrape-responsiveness run, the six valid matched retest blocks, and the three
valid two-CPU-affinity follow-up blocks, the post-reboot same-run pilot plus
its ineligible full matrix, and the three eligible resource-isolated same-run
blocks. The A/B/C overhead gate remains inconclusive and blocks
release/enabling. The separate NAS observation stack has verified live test
scrapes and target recovery after an OC restart; retained history across that
restart has not been independently queried on the NAS. The sequential NAS
benchmark completed with an inconclusive overhead gate and retained evidence.
No production release or release-tag
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
complete; profiling the disabled/enabled paths is a possible next authorized
step before another overhead comparison. The
post-reboot non-isolated same-run barrier was invalidated by concurrent
transport saturation, and the equal-CPU-partition follow-up remained noisy and
over budget; process affinity on this host was already insufficient. Do not
enable the runtime switch in a deployment until the Phase 4 release and
observation gates are completed.
