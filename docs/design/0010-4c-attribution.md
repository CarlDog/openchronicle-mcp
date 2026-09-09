# 4C attribution and exporter experiments

**Status:** diagnostic phase finished; operator-approved recorder Patch 1 is
implemented and verified locally. Patch 2's retained exporter prototype is now
integrated behind opt-in metrics, with maintained contracts and Windows/Linux
verification. Metrics remain off by default. A bounded read-only NAS readiness
sample is complete; formal baseline controls and acceptance are still unexecuted
for this candidate and require a scoped decision.
The instrumentation release and enabled collection remain blocked.
**Date:** 2026-09-05 local; final diagnostics ended 2026-09-06 UTC.
**Work key:** `CarlDog/openchronicle-mcp:work-item:performance-observability-plan`.

## Result

**Source checkpoint, 2026-09-09 UTC:** the operator authorized committing and
pushing the integrated recorder/exporter, maintained tests and this evidence.
The [assessment checkpoint](../CODEBASE_ASSESSMENT.md#source-checkpoint--2026-09-09-utc)
records scope and the unchanged pinned live build. Historical local-only
statements below describe their original checkpoints. Source publication
provides no new timing, 4C/affected 4D acceptance or release authorization.

There are two distinct problems: shared-host CPU contention and instrumentation
cost. Target redundant recorder work first, and evaluate a bounded exporter
optimization separately. No language rewrite or dedicated host is justified.
The [final acceptance disposition](0010-performance-measurement.md#4c-recovery-final-disposition)
is unchanged: disabled/enabled overhead is inconclusive, REST list-tail
responsiveness failed, and MCP list-tail sampling is incomplete.

| Finding | Evidence | Limitation |
| --- | --- | --- |
| Competing CPU work accompanied the bad NAS control | Whole-host busy CPU rose from 22.267% in preceding B to 85.005% in R; niced CPU rose from 0.001% to 26.581% | Responsible process/job remains unidentified |
| Recording repeats health and label work | Per 1,000 isolated search-like recording cycles: 25,000 healthy-gauge writes and 4,000 remaining label resolutions | Identifies opportunities, not application-level savings |
| Full-cardinality exposition consumes CPU | Unprofiled single-thread median: 16.389 ms CPU per scrape; sample-line formatting uses about 66% of profiled cumulative CPU | Does not causally explain the previous REST p99 breach |

## NAS interference

Independent subtraction of the checksummed acceptance report's `/proc/stat`
counters gives the figures above. Bad R snapshots span **22:29:59–22:31:51 UTC**
on September 5 (17:29:59–17:31:51 CDT), including setup/warm-up as well as the
90-second measurement. Load rose from 1.73 to 15.10. The benchmark was confined
to logical CPUs 0–1 on an eight-logical-CPU host; those two CPUs are siblings
on one physical core. Aggregate activity cannot be explained by that benchmark
alone. This supports CPU interference without identifying its cause.

Recorded I/O wait was 0.197%, but this cannot exclude I/O problems: the kernel
warns about interpreting that counter. See the
[kernel's counter definitions](https://docs.kernel.org/filesystems/proc.html#miscellaneous-kernel-statistics-in-proc-stat).

Read-only checks covered Docker inventory and bounded logs for Tdarr, Ollama,
SABnzbd, Kometa, Watchtower and the maintenance worker. Unfiltered Portainer log
calls ignored the requested time bounds. Numeric bounds plus a Docker-timestamp
regex recovered nine Ollama metadata GET entries and no matching retained
Tdarr/SABnzbd stdout entries. Empty/bounded logs do not prove inactivity. The
existing Portainer dogfooding record was updated; its repository was not edited.
The exposed `/logs` archive and scheduler listings provided no process-level
incident evidence; the latest exposed host-log archive predates the incident.
No services were stopped, host settings changed, or NAS load test started.

**Remaining prerequisite:** obtain relevant DSM task/process history, or capture
process-level CPU evidence during a separately authorized bounded readiness
check. Then select an operator-approved quiet window or pause an identified
optional workload. Do not guess the culprit, discard bad controls, or repeatedly
test until controls happen to pass. A dedicated host is not required.

## Recorder/exporter evidence

Container diagnostics used the existing frozen image digest
`sha256:84687ea06ddae1603d8a21c0c9efa0b3a993c6d393884ce528fd20f56def4240`.
The candidate source hash matched the acceptance freeze. Only disposable
diagnostic hooks changed; containers had no network, ports or host mounts and
ran as UID/GID 1000 with all capabilities dropped.

The corrected mixed diagnostic finished in **120.009 seconds**, below its
240-second command cap: 4,929 successful requests, zero failures/timeouts,
matching 1,000-memory corpora and 30 successful one-second scrapes. The reused
full-cardinality fixture produced 3,648 series. All fifteen retrieved JSON
artifacts matched producer hashes.

### Rejected timings

The first mixed attempt failed because concurrent `cProfile` instances collided
over the interpreter profiling slot. A short lifecycle test reproduced that
error. Nonblocking selection and separate request/scrape cases removed the
collision, but cross-thread `thread_time` readings then produced negative
detailed durations. **Reject all mixed-run cProfile durations, including
positive-looking totals.** Raw files are preserved for audit. Mixed-run counts
remain useful, but selected worker calls are not a representative sample.
Only 29 of 30 scrapes entered the diagnostic timing window; the initial scrape
preceded hook activation. No new p95/p99 acceptance claim follows.

Profiling is diagnostic, not acceptance benchmarking; see the
[Python profiling guidance](https://docs.python.org/3.14/library/profile.html).

### Validated isolated costs

A separate **single-thread** diagnostic on the same image finished in 2.500
seconds. It asserted one live thread and nonnegative profile durations. Three
unprofiled batches each measured 1,000 recording cycles and ten full scrapes.
Median recording CPU was **38.543 microseconds per cycle**; median scrape CPU
was **16.389 milliseconds**. A cycle contains 17 read-lock observations, four
search-stage observations, one embedding, one HTTP observation and two in-flight
updates. This is a search-like recording microdiagnostic, not a complete request.

Validated single-thread profiles show:

- `_safe` writes the healthy gauge on every successful operation: 25,000 times
  per 1,000 cycles. Histogram work is also substantial; its exact observations
  and buckets must not be weakened to improve results.
- Existing lock/stage/in-flight caches are exercised. HTTP and embedding still
  perform 4,000 `labels()` resolutions per 1,000 cycles.
- Ten scrapes format 36,480 sample lines and perform 94,360 label-name escapes
  plus 94,360 label-value escapes. Sample-line formatting uses 0.919 of 1.392
  profiled CPU seconds; registry collection uses approximately 0.416 seconds.
  Cumulative figures overlap their children and must not be added together.
- The standard process collector uses only 0.0027 profiled CPU seconds across
  those ten scrapes. Removing process statistics is not the evidenced target.

These results identify work to target. They do not establish how much of the
NAS 6.392% enabled median loss it explains, or prove either patch will pass.

## Implementation scope

### Patch 1: redundant recorder work — approved and implemented locally

Limit the first patch to `prometheus_recorder.py` and focused tests:

1. Replace repeated healthy-to-healthy gauge writes with a state-transition
   helper. Define/test concurrent failure-success ordering. Every failure must
   still increment its error counter and set health to zero; the next successful
   recording operation restores health. A successful scrape must not acquire a
   new health-recovery meaning.
2. Extend per-recorder normalized child caches to the evidenced HTTP and
   embedding paths. Bound keys before lookup; preserve exact counts, sums,
   buckets, unknown-label normalization, lazy failure handling and registry
   isolation. Do not extend this batch to unprofiled MCP/maintenance paths merely
   for consistency.

Test normal/failed/recovered health transitions, concurrent ordering, no repeated
label resolution after priming, cache bounds, exact concurrent observations and
disabled bypass. Run focused metrics tests and quality checks; run full checks
when a candidate is stable. No percentage improvement is promised.

#### Implementation and ordering contract

`_mark_success` skips the gauge write while already healthy. Both success and
failure publish health under a short per-recorder lock; recording callbacks
remain outside it. Overlapping operations are ordered by their health
publication, not invocation start time. A long-running callback can therefore
restore health after another callback fails, or mark it unhealthy if it fails
after another succeeds. The lock keeps the cached state and gauge consistent.
Every failure still attempts a zero write and error-counter increment. If the
zero write itself fails, the counter is attempted independently and cached
health stays false so the next successful recording retries recovery. The
warning remains once per recorder. Successful scrapes do not restore health.

HTTP and embedding counters/histograms have separate lazy caches, keyed only
after normalization. Maximum entries are HTTP **432 counters / 72 histograms**
and embedding **75 counters / 15 histograms**, including unknown labels.
Histograms are shared across status/outcome variations. Counter increment still
precedes histogram lookup/observation, preserving partial results on failure.
Concurrent first-use lookups rely on the client's locked child creation; every
call still records its observation. No MCP/maintenance cache, exporter, bucket,
metric definition, dependency, default or acceptance-harness change was made.

Deterministic regressions cover healthy-write suppression, repeated failure and
recovery, broken gauge publication, both concurrent publication orders, both
overlapping callback outcomes, scrape-versus-recording recovery, every reachable
cache key, unknown normalization, registry isolation, forced simultaneous cache
misses, exact counts/sums/buckets, and lookup/observation failure at each stage.

#### Local verification

Patch 1 is complete in the working tree, not committed or published. **All 951
tests passed across the full run and a targeted environment-isolated retry**:
949 passed in the full run; two CLI Git-fixture tests initially failed before
application execution because an inherited template hook invoked unavailable
Bash. Prepending Git's Bash directory did not resolve it. Setting
`GIT_TEMPLATE_DIR` to an empty, workspace-local directory for the two-test retry
prevented machine hooks from being copied into those disposable fixtures; both
then passed. No tracked test, real-repository hook or persistent Git setting was
changed to obtain that result.

Pytest's default temp directory was inaccessible in the sandbox. Passing
workspace-local process temp-directory settings, a fresh `--basetemp`, and `-p no:cacheprovider`
resolved that separate setup issue. Commands run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_metrics.py -q -p no:cacheprovider --basetemp data/performance/phase4-20260904/recorder-patch1-20260905-temp/focused --tb=short
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp data/performance/phase4-20260904/recorder-patch1-20260905-temp/full --tb=short
.\.venv\Scripts\python.exe -m pytest tests/test_cli_smoke.py::TestOnboardGitCli -q -p no:cacheprovider --basetemp data/performance/phase4-20260904/recorder-patch1-20260905-temp/cli-isolated --tb=short
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
.\.venv\Scripts\python.exe -m mypy src tests --config-file=pyproject.toml
npm.cmd run lint:md
git diff --check
```

Focused metrics: 36 passed. Ruff lint and format: passed (187 files formatted).
Mypy: passed (179 source files). Markdown: 52 files, zero issues. Whitespace and
AGENTS/CLAUDE byte parity: passed. Source review found no additional required
change. Tests establish avoided writes/lookups and preserved behavior, not a
CPU/throughput improvement or an accepted application-performance result.

No exporter change, NAS readiness/load test, new 4D experiment, publication,
release, deployment, enablement, commit or push occurred. Prior 4D reuse was for
the old frozen candidate; this changed health path requires an affected-path
review before any future candidate claims reuse. All existing performance
budgets and unresolved gates remain in force.

### Patch 2: bounded exposition — prototype and local integration

Investigate reuse of **immutable sample prefixes/name-label formatting**, not
metric values or complete scrape responses. Read fresh process values, counters,
histogram buckets/sums and gauges on each scrape. Bound cached entries and
preserve errors, single-worker ownership, overlap rejection and cancellation.

The prototype was a separate experiment with a larger correctness burden, not
authorization to replace the application serializer. Require comparison with the standard exporter
over all reachable series, escaping, unknown labels, dynamic values and injected
errors. Keep the standard implementation if a bounded, maintainable optimization
cannot preserve those contracts. No global dependency monkeypatching, observation
sampling, histogram reduction, new runtime dependency or stale-response cache.

#### Prototype decision

**Prototype-stage decision:** retain the prototype as a candidate for separately
authorized integration; keep the standard exporter at that checkpoint. The
operator's subsequent `continue` authorized this bounded local experiment, not
an exporter replacement, publication or NAS run.

The prototype caches only immutable sample-name/label prefixes for legacy-name
counter, gauge and histogram families. Unsupported families/names and other
escaping schemes delegate to the installed standard exporter, using already
collected families. Values, timestamps, process samples and headers are fresh;
there is no complete-response cache or second registry collection. Cache bounds
are **4,096 entries and 1 MiB of retained UTF-8 key/prefix text**. Python object
overhead is additional. Saturation continues uncached formatting without dropping
samples. The existing per-recorder scrape slot, not a new queue or worker model,
provides ownership in disposable-instance tests. No dependency-global patching
or application-source change was made.

Options reviewed: retaining the standard exporter has the least maintenance;
the scoped cache plus standard fallback offers measured savings with an added
compatibility burden; a full serializer fork/global monkeypatch remains outside
the adopted scope. This is not a general-purpose replacement for the upstream
exporter. Compatibility with the actual deployment dependency set must be checked
before adoption; this experiment used **Python 3.14.7 / prometheus-client 0.26.0
on Windows**. It does not establish compatibility across the project's open
dependency range.

#### Correctness and measured trade-off

**53 prototype tests passed**, separate from the unchanged 951 application-test
baseline. They cover byte parity over the entire 3,648-series OC label matrix
and after updates; unknown labels; Unicode/escaping, timestamps, special numeric
values and created-series order; unsupported-family/name/escaping fallback;
invalid values/labels and collection errors; cache limits/isolation; fresh
single collection; and recorder health, overlap and cancellation behavior.

The unprofiled single-thread experiment retained all six alternating-order
blocks per fixture. Each exporter used 2,500 calls/block for sparse and 25 for
full cardinality, with ten warm-ups each. The completed invocation took
**9.702 seconds** against its 60-second cap. There were 30,000 sparse and 300
full measured collections, exactly one per exporter call; body hashes matched.

| Fixture | Series | Standard median CPU/scrape | Prototype median CPU/scrape | Median paired reduction |
| --- | --- | --- | --- | --- |
| Sparse | 28 | 0.178125 ms | 0.112500 ms | 36.207% |
| Full bounded matrix | 3,648 | 17.500000 ms | 10.312500 ms | 41.799% |

These reductions are medians of within-block ratios, not ratios of the two
median costs. All six full-cardinality reductions were positive: 40.741%,
48.276%, 45.161%, 39.286%, 42.857%, 39.286%. Median full wall time was
17.552 → 10.371 ms per scrape. These are **local exporter costs, not NAS
application throughput or REST/MCP p99 results**; the 4C gates remain unresolved.

At full cardinality, the cache held 3,648 entries and 558,533 text bytes. Traced
warm retained Python allocations were 2,034,012 bytes (about **1.94 MiB**), versus
64 bytes retained by the standard exporter. Warm peak traced allocations were
3,072,974 versus 1,224,286 bytes. This is allocation accounting, **not process
RSS**, and does not clear the 10-MiB RSS budget. The process-shaped fixture has
six controlled samples; native Linux `/proc` collection was not exercised.

Two pre-result corrections are retained rather than hidden: the initial
synthetic process fixture had an extra seventh sample, caught by the matrix
test and corrected against installed collector source before timing; the first
25-call sparse timing batch returned zero thread CPU time and aborted. One
documented recovery fixed sparse batches at 2,500 calls before usable results.
The full batch size, orders, cap and acceptance thresholds were unchanged.
No failed block was dropped from a completed comparison, and no further timing
run followed.

#### Evidence and next boundary

Artifacts, prototype, tests and the prospective experiment specification are in
`data/performance/phase4-20260904/exporter-prototype-20260905/`.
`result.json` SHA-256:
`e07eb88813d7016826b8fe5d345570baa71d03ed3cdad972f759877512f47165`.
Independent PowerShell readback verified that hash, all recorded input hashes,
orders, call/collection counts and arithmetic. The failed timing attempt has a
separate sanitized record. No artifact was overwritten.

Commands run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest data/performance/phase4-20260904/exporter-prototype-20260905/test_cached_exporter.py -q -p no:cacheprovider --tb=short
.\.venv\Scripts\python.exe data/performance/phase4-20260904/exporter-prototype-20260905/measure.py
.\.venv\Scripts\python.exe -m ruff check data/performance/phase4-20260904/exporter-prototype-20260905
.\.venv\Scripts\python.exe -m ruff format --check data/performance/phase4-20260904/exporter-prototype-20260905
.\.venv\Scripts\python.exe -m mypy data/performance/phase4-20260904/exporter-prototype-20260905 --config-file=pyproject.toml
```

Prototype tests, Ruff and format passed; mypy passed for four source files.
The application suite was not rerun because application source, tracked tests,
dependencies and the acceptance harness were unchanged during this experiment.
No new container, NAS job, publication, commit/push, release or enablement.

The subsequent integration must instantiate the cache once per **enabled** recorder,
preserve disabled-only dependency isolation and the current scrape guard, and
carry the parity/error tests into the maintained suite. That new candidate then
needs deployment-runtime compatibility, actual RSS/responsiveness and affected
4D review, plus bounded NAS readiness before one separately authorized frozen
acceptance run. No numerical acceptance budget has changed.

#### Local integration checkpoint

The next operator `continue` authorized local integration and correctness/runtime
verification, not publication or NAS testing. `CachedPrefixExporter` now lives
in the infrastructure observability package and is instantiated once inside
each enabled recorder's constructor. Disabled factory/module imports do not
import it or Prometheus. No dependency, metric name, label, bucket, content type,
environment default or acceptance-harness change was required. Collection stays
fresh; the recorder's existing worker, scrape slot, overlap rejection and
cancellation ownership are unchanged. Cache limits remain 4,096 entries and
1 MiB of retained key/prefix text, **not a total-memory or RSS cap**.

Review and reproductions exposed two prototype edge cases, corrected only in
the integrated candidate:

- A string subclass equal to a primed key could bypass standard fallback while
  changing escaping behavior. Exact plain-string checks now precede lookup.
- Per-family fallback could raise a UTF-8 encoding error before later families
  were collected, with a partial-body error context. Final-body encoding is now
  deferred to the whole scrape; sample-conversion errors still propagate with
  the standard family context and later collection/formatting failures keep
  their precedence.

The promoted tests cover all 3,642 OC series, a separately named six-sample
controlled process collector, fresh updates, escaping/numeric/timestamp parity,
fallback and errors, cache bounds/isolation, disabled dependency isolation and
scrape lifecycle. Test process names no longer conflict with native Linux
process metrics. A Linux-only contract verifies that the actual `ProcessCollector`
is called on every scrape and emits the six expected process samples.

The floor check also inspected the upstream
[0.23.1 exporter](https://github.com/prometheus/client_python/blob/v0.23.1/prometheus_client/exposition.py)
and [collector interface](https://github.com/prometheus/client_python/blob/v0.23.1/prometheus_client/registry.py).
Runtime checks used an isolated 0.23.1 wheel without changing the development
environment, plus the existing local benchmark image digest recorded above
(Python 3.14.6, Prometheus 0.26.0). The current candidate source and tests were
copied into that image for testing; **the image itself was not rebuilt**. All
seven recorded source/test/configuration hashes matched the workspace. These
checks verify those two dependency versions, not every possible future resolver
result; verify the final candidate image again before NAS acceptance.

Verification artifacts are in
`data/performance/phase4-20260904/exporter-integration-20260905/`:

- Windows Python 3.14.7: final full suite **1,020 passed, one Linux-only skip**
  in 44.37 seconds. Focused floor contracts passed **105 with the same skip**.
- Linux Python 3.14.6: **106 passed with 0.26.0 and 106 with 0.23.1**. Native
  process, HTTP access, error recovery and cancellation contracts all ran.
  Each run emitted one existing Starlette/AnyIO deprecation warning.
- Ruff lint and formatting passed (190 files); mypy passed (182 source files).
- Markdown passed (53 files); whitespace and AGENTS/CLAUDE byte parity passed.
- The initial offline Linux test setup lacked pytest's `py.py` file and then
  its asyncio plugin metadata. Completing those copied test-only dependencies
  allowed both bounded runs to finish; no application correction was needed.
- The disposable Linux container had no network, ports or host mounts, ran as
  UID/GID 1000 with all capabilities dropped, and had a 120-second outer timeout
  plus 45-second limits per test subprocess. Both JUnit reports were retrieved;
  successful exit and removal were independently verified. Its writable layer
  was removed; reports, original prototype artifacts and the base image remain.

Commands run from the repository root, with fresh workspace-local process
temp-directory settings and `GIT_TEMPLATE_DIR` pointing to an empty disposable
directory for CLI fixtures (no real hooks or persistent Git settings changed):

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cached_exporter.py tests/test_metrics.py -q -p no:cacheprovider --basetemp data/performance/phase4-20260904/exporter-integration-20260905/focused-1 --tb=short
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp data/performance/phase4-20260904/exporter-integration-20260905/full-1 --tb=short --junitxml=data/performance/phase4-20260904/exporter-integration-20260905/windows-junit.xml
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp data/performance/phase4-20260904/exporter-integration-20260905/full-final --tb=short --junitxml=data/performance/phase4-20260904/exporter-integration-20260905/windows-final-junit.xml
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
.\.venv\Scripts\python.exe -m mypy src tests --config-file=pyproject.toml
npm.cmd run lint:md
git diff --check
```

The initial full Windows run had 1,019 passes, one Linux-only skip and one
documentation hygiene failure: an environment-variable name in this report was
mistaken for a debt marker. Only the wording changed; the guard was not weakened.
The initial focused run preceded the Linux-only test and passed all 105 tests.
The floor run prepended the downloaded wheel to `PYTHONPATH` and asserted its
version before invoking pytest. The retained `runtime_check.py` records exact
Linux invocations and version/source checks; it is not a benchmark harness.

**Affected 4D review:** routes, authentication, configuration, storage/schema,
collector retention and deployment files are unchanged. Existing access tests
pass with the integrated exporter, and failure/recovery/overlap/cancellation
contracts cover the changed health/exposition path. Prior NAS history/rollback
evidence remains historical evidence for its frozen candidate, not certification
of this one. After candidate freeze, the affected live checks still required
are successful Prometheus parsing/scraping of full-cardinality output, outage
and recovery signals, restart/reset/history continuity and candidate rollback.
No new 4D live pass is claimed.

**Next boundary:** local integration does not clear shared-host readiness,
the actual 10-MiB RSS limit, REST/MCP p99 or overhead gates. The frozen prototype's
41.799% CPU reduction does not measure this corrected integration. A separately
scoped readiness step must identify/control competing NAS work before one frozen
candidate comparison and affected 4D checks. No NAS run, image publication,
release, deployment, metrics enablement, commit or push occurred in this step.

### NAS readiness snapshot — completed, not a baseline-control pass

The operator's next `continue` authorized a bounded current-workload/process
visibility check. It did not authorize image publication, acceptance load,
service pauses, new host mounts/privileges or production changes.

The one-shot sampler completed in **53.267 seconds**. It retained two snapshots
of all **42 running containers**, with a fixed 30-second gap after finishing
the first snapshot. All **84 stats requests and 84 process-list requests**
succeeded. Host CPU counters were read twice through the existing unprivileged
Ubuntu toolbox; no container was created, restarted or reconfigured. The host
counter interval was **01:12:29.437–01:13:10.921 UTC on September 6**
(20:12:29–20:13:10 CDT on September 5), approximately **41.485 seconds** because
the first inventory also took time. API requests had six-second timeouts, four
concurrent readers, response-size caps and no authentication redirects. The
existing configured Portainer credential was used only for its configured NAS
endpoint; no credential, environment dump or process arguments were retained.

| Current observation | Result |
| --- | --- |
| Whole-host busy CPU, excluding idle and I/O wait | **8.852%** |
| Niced CPU | **0.000%** |
| I/O-wait counter share | **0.978%**, not proof of I/O health |
| Logical CPU 0 / CPU 1 busy | **10.679% / 4.366%** |
| One-minute load average | **0.86 → 0.90** on eight logical CPUs |
| Sum of per-container CPU shares | **5.023% of host capacity**, approximate |
| Largest container shares | `wobblebot-live` **0.660%**, `tdarr` **0.621%**, `wobblebot-web` **0.595%** of host capacity |
| Production OC CPU share | **0.242% of host capacity** |
| Production identity | Same container, image, start time and zero restart count; healthy before and after |

The container figures are percentages of **all eight host CPUs**, not a single
core. Docker CPU deltas divided by system CPU deltas give that share; multiplying
by eight gives the familiar one-core-normalized percentage. Whole-host deltas
use the first eight `/proc/stat` fields, with idle and I/O wait excluded from
busy time. PowerShell arithmetic was independently reproduced in JavaScript.
Definitions: [Docker statistics API](https://docs.docker.com/reference/api/engine/version/v1.45/)
and [Linux CPU counters](https://docs.kernel.org/filesystems/proc.html#miscellaneous-kernel-statistics-in-proc-stat).

**Limits:** this is one short observation, including its own Portainer/Docker
overhead. Container reads are staggered, so their sum cannot be subtracted from
host busy CPU as an exact attribution. Process `TIME` has one-second resolution;
short-lived/disappeared processes and DSM-native processes are not fully covered.
One `seerr` process name contained a space, shifting Docker's returned columns;
the initial analysis rejected that row, and the pair was explicitly excluded
from process-time deltas without changing raw evidence or container accounting.
One additional process disappeared between snapshots. No NAS sampling retry ran.
The former high/niced-CPU spike was not reproduced or retrospectively explained.

**Disposition:** current visibility works, and no heavy Docker workload was
identified that warrants a pause. This does not certify a stable future window,
pass baseline variability controls, or change any 4C gate. Before the next fixed
benchmark, agree a window without planned heavy scans/backups/transcodes and
recheck contemporaneous host/container activity. Keep all baseline controls and
noise vetoes; do not reuse this short snapshot as an acceptance pass or rerun
until favorable data appear. Native DSM process evidence is still needed if
significant unexplained host activity recurs; no new privileged access is implied.

Artifacts: `data/performance/phase4-20260904/nas-readiness-20260905/` contains
the executed `sample.py`, raw `sample.json`, and `analysis.json` with all
container shares, process exclusions and limitations. Raw sample SHA-256:
`7317ca760a8a8f288a3b6eedfde32fa3b68b4432a59fd36d7efa1eb7b88f4ffb`.
Portainer MCP inventory/inspect tools established the endpoint and exact targets;
the configured Docker API supplied the missing stats/process surface. No
application, dependency or acceptance-harness file changed in this step. The
last full application test result remains 1,020 passes and one Windows platform
skip, with that native-process test passing on Linux. Documentation hygiene,
Markdown, whitespace and instruction-mirror checks validate this checkpoint.

### Validation and stop

Prospectively budget separate REST/MCP responsiveness pairs to obtain at least
1,000 successful samples per operation for p99. The prior 733/736 MCP list
samples are a test-coverage shortfall, not a demonstrated application regression.
Keep workload mix and thresholds; do not extend runs adaptively until they pass.

After an approved patch: verify correctness, pass bounded NAS baseline readiness,
freeze the candidate, then run one acceptance comparison and affected
responsiveness/4D checks. Exporter changes require a new 4D impact review;
existing reuse is not blanket permission for future changes. No retest,
publication, release, deployment, enabling or monitoring follows automatically.

## Retained diagnostic evidence

Artifacts: `data/performance/phase4-20260904/attribution-20260905/`.
The following is the diagnostic checkpoint, before the Patch 1 implementation.

- Original acceptance SHA-256 remains
  `883a1649965d9a8b4ede89d568c1503d4760bc3ce8768a9eb350db237497b290`.
- Mixed report SHA-256:
  `8325f0a583bee2d9bfe3f7950ce484d07ee12d0968e726ca4cf8015f249220f6`.
- Validated isolated report SHA-256:
  `cf72e7f53bca900943808ed94a787ef41aa8be988596931f98162b641e177764`.
- `analysis.json` recalculates host CPU deltas and explicitly rejects mixed
  profile timings. `isolated-cost.json` contains usable single-thread profiles.
- Three no-network lifecycle smoke variants passed after the profiler-slot
  correction. The isolated run verifies thread count and timing validity.
- Application code, dependencies, production configuration and acceptance gates
  are unchanged. No new full application-suite result is claimed.
- `npm run lint:md`: 52 Markdown files, zero issues.
- `python -m ruff check data/performance/phase4-20260904/attribution-20260905`:
  passed. The corresponding `ruff format --check` passed for five helpers.
- `git diff --check` and the AGENTS/CLAUDE byte-parity check passed. Full pytest
  was not rerun because no application, test, dependency or acceptance-harness
  code changed.
- All three stopped diagnostic containers were identity-checked and removed
  after evidence retrieval; independent listing confirmed their absence.
  Evidence files and the benchmark image were retained. No Git commit or push.
