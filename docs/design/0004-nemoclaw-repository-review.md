# NemoClaw Repository Review — Applicable Lessons for OpenChronicle

**Status:** Research complete; instruction-authority and current-docs
findings closed in the 2026-08-28 review closeout; runtime findings and
design constraints recorded but unscheduled

**Assessment date:** 2026-08-28

**NemoClaw snapshot:** [`NVIDIA/NemoClaw` commit
`b7261ff`](https://github.com/NVIDIA/NemoClaw/commit/b7261ff7cc73c76a15deb3e95291c24b1624534e)

**Review checkout:** clean sibling checkout on `main`, matching
`origin/main`; 6,008 tracked paths; initialized `llm-router` submodule at
the recorded commit

**OpenChronicle snapshot:** `main` at
`68a4eebd947963d4aa87ae1470bd0ff4d06e0774`, package
`3.0.0rc8`

## Executive conclusion

NemoClaw is an agent-execution and sandbox-lifecycle platform.
OpenChronicle is a persistent memory data plane. NemoClaw has no semantic
memory retrieval engine to copy: the reviewed source contains no vector
index, RRF/MMR ranking, memory consolidation, or competing
`memory_search` implementation. It can configure an integrated agent's
own memory-search feature, but that engine remains agent-owned. Its agent
memories are opaque files and SQLite databases that NemoClaw protects,
backs up, and restores.

The useful transfer is therefore operational discipline, not product
scope. NemoClaw provides strong examples of versioned persisted state,
postcondition-checked replay, least-privilege child processes, immutable
build identity, verify-before-publish recovery artifacts, and generated
contract checks. Applied selectively, those patterns expose several real
OpenChronicle gaps without turning it back into an agent runtime.

| Disposition | Candidate | Why it qualifies |
|---|---|---|
| Closed in review closeout | Establish one canonical agent-instruction source | `AGENTS.md` is now canonical, `CLAUDE.md` is its byte-identical compatibility mirror, and a repository-hygiene test prevents drift |
| Verified current defect | Make the JSON export/import envelope a real versioned contract and publish exports atomically | Import accepts unsupported versions, treats missing arrays as empty, and can leak `KeyError`; export writes directly to its final path |
| Verified security hardening | Minimize the `onboard_git` child environment and decide an outbound destination policy | `git clone` inherits every server secret and accepts arbitrary remote hosts even though its consumer needs are narrow |
| Verified operational gap | Bake and expose immutable build revision | `package_version` cannot distinguish multiple short-SHA deployments from the same rc version |
| Closed in review closeout; broader guards proposed | Repair current CLI/MCP/security/config/deploy falsehoods and add narrow parity checks | The six snapshot inaccuracies are corrected; only the broader CLI/MCP/env inventory gates remain unscheduled |
| Existing backlog, strengthened | Consume a lock in CI and Docker, then audit the locked dependency graph | A prior unconstrained MCP resolve would have broken startup; an unconsumed lock is not reproducibility |
| Constraint on existing future work | Give offline replay a stable operation identity and postcondition check | The documented write-behind need otherwise duplicates a committed write after an ambiguous timeout |
| Constraint on existing future work | Bind live restore to a selected artifact and prove the installed DB is writable | The cloud-restore design already exists and the cutover history includes corrupt SQLite state |
| Independent corroboration | Composite embedding identity, validated SQLite backup publication, and truthful backfill health | These are already recorded in the OpenClaw/Ollama reviews; NemoClaw strengthens the evidence but creates no duplicate backlog item |
| Measure or trigger first | Built-image smoke, resource limits, persistent-memory secret warnings, backup `fsync`, and a dedicated git-onboard state table | Each is plausible, but the present evidence does not justify immediate standalone scope |
| Do not adopt | OpenShell sandboxes, model routing, credential brokerage, messaging, agent manifests, lifecycle state machines, broad policy engines, and enterprise release machinery | These solve NemoClaw's untrusted-agent and multi-maintainer problems, not OpenChronicle's memory-service problems |

The recommended approach is to adapt invariants in small native Python
changes. No NemoClaw component, submodule, runtime, or direct code copy is
needed.

## Scope and method

The review covered the pinned source, tests, manifests, workflows, and
official documentation for:

- product boundaries and integration architecture;
- manifest-declared portable, machine-local, and confidential state;
- snapshot, rebuild, checkpoint, replay, and SQLite recovery behavior;
- subprocess, credential, network-destination, and container boundaries;
- build provenance, dependency locking, configuration validation, and
  release identity;
- CLI/docs, environment/docs, and generated-fact parity checks; and
- test-lane and artifact-contract strategies.

Those mechanisms were compared with OpenChronicle's:

- memory/export/import contracts and git-onboard lifecycle;
- SQLite backup, maintenance, health, and cloud-restore designs;
- embedding identity and failure-reporting behavior;
- CLI, MCP, REST, configuration, deployment, and agent instructions; and
- current backlog, incidents, deployment shape, and explicit v3 scope.

The local NemoClaw checkout was kept read-only and clean. The initialized
`nemoclaw-blueprint/router/llm-router` submodule resolves to the exact
gitlink recorded by the parent commit. This was a source-level review: it
did not provision an OpenShell sandbox, run an agent, execute a model, or
load-test either project.

NemoClaw is
[Apache-2.0 licensed](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/LICENSE).
OpenChronicle is AGPL-3.0-only. Adapting architectural ideas requires no
code copying; any material copied code would still need its applicable
copyright and license notices. This is an engineering observation, not
legal advice.

## System-boundary comparison

~~~text
NemoClaw
  agent + model + credentials
    -> versioned onboarding and runtime receipts
    -> OpenShell sandbox and network/process/filesystem policies
    -> backup/rebuild/restore of heterogeneous agent state
    -> CLI, messaging, dashboard, and lifecycle operations

OpenChronicle
  typed memory + project rows
    -> one canonical SQLite database
    -> FTS5 and embedding retrieval fused with RRF
    -> MCP, REST, and CLI clients
    -> bounded maintenance and portable export/import
~~~

| Dimension | NemoClaw | OpenChronicle | Transfer implication |
|---|---|---|---|
| Product role | Runs untrusted, tool-using agents | Stores and retrieves caller-owned memory | Borrow state and safety invariants, not execution scope |
| Trust boundary | Host, gateway, sandbox, agent, model, and external networks | One server process, trusted home LAN, external embedding provider, user-supplied git URL | Harden the two real outbound boundaries only |
| Durable state | Many directories, config files, credentials, and SQLite DBs | One SQLite DB plus small maintenance state; JSON is a portable data envelope | Use smaller artifact contracts than NemoClaw |
| Resume model | Multi-phase side effects and destructive sandbox recreation | Transactional database operations; future client replay | Checkpointing matters only at ambiguous external boundaries |
| Build identity | Public version plus source revision and image/catalog digests | Package version and mutable/short-SHA image tag | Add source revision; digest machinery is optional |
| Documentation scale | Public docs site, many agents/platforms/providers | Small private repository and 18 MCP tools | Add targeted parity tests, not a docs platform |

## Transfer gate

A NemoClaw mechanism qualifies only when all of these are true:

1. It improves OpenChronicle ingestion, storage, retrieval, portability,
   security, or operation rather than agent orchestration.
2. A current defect, recorded incident, existing backlog item, or named
   near-term consumer establishes the need.
3. The smallest useful slice is materially simpler than adopting the
   upstream subsystem.
4. The behavior can be tested as an OpenChronicle invariant.
5. Trigger-gated ideas stay out of the live backlog until their trigger
   occurs.

That gate rejects most of NemoClaw while preserving the parts with real
value.

## Finding 1: agent instructions have two conflicting authorities

### Evidence

NemoClaw makes root `AGENTS.md` canonical and records `CLAUDE.md` as a
git symlink to it. Its root guidance also makes scope admission explicit:
a feature needs a current requirement, consumer, and protecting test.
The exact symlink is not portable to this Windows checkout—`core.symlinks`
is false and the file materializes as a short text file—but the
single-authority invariant is useful.

At the reviewed snapshot, OpenChronicle tracked `CLAUDE.md` but had an
untracked `AGENTS.md`. The latter was not a harmless copy:

- it says `main` is still v2 and v3 will later replace it;
- it says the current sprint and deployed image are rc5; and
- it omits the rc6-rc8 work that tracked `CLAUDE.md` and
  [CODEBASE_ASSESSMENT.md](../CODEBASE_ASSESSMENT.md) describe.

Codex loaded that stale file for this review, proving the drift could
direct an agent using operational facts the SSOT said were false.

### Closeout decision

The closeout chose canonical `AGENTS.md` because Codex consumes it
directly. `CLAUDE.md` is maintained as a byte-identical compatibility
mirror, and `test_agent_instruction_mirrors_are_identical` fails on any
drift. This preserves Windows portability without relying on a symlink.

The considered implementation choices were:

- generate `CLAUDE.md` from it;
- use a tool-supported include; or
- maintain a tiny checked mirror with a test that fails when their
  invariant sections diverge.

NemoClaw's literal symlink remains rejected because Windows checkout
behavior is not portable across contributors. Volatile sprint history was
removed from the instruction body; stable workflow rules remain inline
and current state links to the project SSOT.

**Disposition:** closed in the 2026-08-28 review closeout.

## Finding 2: the portable envelope is versioned in name only

### NemoClaw validates persisted state at its trust boundary

NemoClaw uses explicit schema versions, bounded values, exact or
allowlisted keys, identity matching, and distinct outcomes for corrupt,
legacy, and unsupported-future checkpoints:

- [`runtime-snapshot.ts`](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/state/registry/runtime-snapshot.ts#L7-L71)
  rejects the wrong schema version and a provider mismatch;
- [`onboard-checkpoint.ts`](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/state/onboard-checkpoint.ts#L388-L473)
  strictly validates a destructive transaction journal; and
- the same parser distinguishes unsupported-future, legacy, and corrupt
  input rather than interpreting it as current state.

The transferable principle is version dispatch followed by whole-envelope
validation before mutation.

### OpenChronicle accepts envelopes it cannot truthfully interpret

[`import_memory.py`](../../src/openchronicle/core/application/use_cases/import_memory.py)
currently checks only that `format_version` exists. It does not verify
that it equals `EXPORT_FORMAT_VERSION == 1`, or even that it is an
integer. It also:

- treats missing `projects` or `memory_items` as an empty list;
- assumes both values are iterable lists of mappings;
- reads `raw_project["id"]` and `raw_memory["id"]` before the error-
  translating `try` blocks, so malformed rows can leak `KeyError`; and
- starts mutation before every row has been validated, relying on the
  transaction for rollback but producing less useful diagnostics.

An envelope with `format_version: 999` and empty arrays is therefore
accepted as a successful import. A truncated-but-valid JSON object that
omits an array can look like a legitimate empty restore.

[`memory.py`](../../src/openchronicle/interfaces/cli/commands/memory.py)
writes an export directly to the final path with `Path.write_text`. A
process or storage failure can leave a partial file at the path an
operator believes is a backup, and no private permission is requested.

### Proposed contract

Keep format 1, but make it real:

1. Require a top-level mapping with an integer `format_version`.
2. Dispatch only to a validator for version 1; reject unknown versions
   with an actionable error.
3. Require `projects` and `memory_items` arrays and validate every row,
   type, required key, datetime, tag list, project reference, and UUID
   before opening the write transaction.
4. Report the failing collection, index, and safe row identifier through
   `ValidationError`; never leak `KeyError`/`TypeError` from the CLI.
5. Write exports to a unique sibling temp file, request owner-only
   permissions where supported, flush/close, then `os.replace` the final
   path. Add file/directory `fsync` only if the backup durability model
   calls for it across supported platforms.
6. Preserve the current transactional import and explicit merge-hazard
   warnings.

A payload digest is optional. JSON parsing and strict structure catch
many truncation cases, while the planned encrypted cloud artifact already
has cryptographic integrity. Add a digest only if a consumer needs to
select and re-verify an unencrypted envelope independently.

**Disposition:** ~~verified correctness defect in a disaster-recovery
surface; suitable for a focused implementation batch.~~ **✅ SHIPPED
2026-08-28** (assessment rev 116) after a validation pass re-confirmed
every sub-claim at HEAD — and found the defect had *accreted*: the
content-cap work added a third unguarded `raw_memory["id"]` after this
review's snapshot. Landed as proposed: version dispatch, required
arrays, whole-envelope row validation before the transaction with
errors naming collection/index/id, project references checked against
store ∪ envelope (closing an untranslated `IntegrityError` this review
had not named), duplicate in-envelope ids rejected, and `mkstemp` +
`os.replace` export publication. Point 1d above was overstated: the
loop was already one transaction at this review's own baseline, so the
pre-validation gain is diagnostics quality, not atomicity. The optional
payload digest stays unadopted, as specified.

## Finding 3: `onboard_git` crosses two avoidable trust boundaries

### Child-process credential scope is too broad

[`git_onboard.py`](../../src/openchronicle/core/application/services/git_onboard.py)
builds the `git clone` environment with `os.environ.copy()`. The child
therefore receives `OC_API_KEY`, `OPENAI_API_KEY`,
`OC_EMBEDDING_API_KEY`, raw `OC_GIT_TOKEN`, and every unrelated secret
in the server process. The code then derives a host-scoped GitHub Basic
header but leaves the raw token in the environment.

This is not evidence that Git currently exfiltrates those values. It is
an unnecessary blast radius: `git clone` has no consumer need for the
API or embedding credentials.

NemoClaw's credential design keeps raw provider credentials at the
host/gateway boundary and gives a workload only the binding required for
its egress. OpenChronicle needs no credential broker to apply that
principle.

Build a minimal child environment, or strip all known secret-bearing
variables before launch. Specifically:

- remove raw `OC_GIT_TOKEN` after constructing the host-scoped header;
- set `GIT_TERMINAL_PROMPT=0`;
- defensively redact the raw and derived authorization values from
  captured stderr;
- reject URL userinfo and credential-like query/fragment material; and
- use `--no-checkout` because the implementation reads Git history but
  never needs a working tree. Benchmark partial-clone filters separately;
  `--numstat` may still need blob metadata.

Tests should inspect the mocked subprocess environment and prove that an
unrelated sentinel secret cannot cross the boundary.

### Server-side clone destinations are unrestricted

The same service accepts arbitrary HTTPS, SSH, and scp-style hosts. It
blocks dangerous Git remote-helper and local-file transports, which is
good, but it does not reject loopback, link-local, metadata, private, or
mixed public/private DNS destinations. The NAS container can explicitly
reach `host.docker.internal`.

NemoClaw's
[`ssrf.ts`](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/nemoclaw/src/blueprint/ssrf.ts#L44-L129)
checks credentials, private names, every resolved address, and peer
pinning. Copying it wholesale would be disproportionate. OpenChronicle
first needs an explicit product decision:

- If MCP onboarding actually needs GitHub only, allow public HTTPS
  GitHub clone URLs on the server surface and keep broader/local paths in
  the CLI.
- If arbitrary Git hosts are a real requirement, reject unsafe address
  classes and cross-host redirects, including mixed DNS answers. A
  resolve-only preflight is insufficient unless the connection is bound
  to the validated peer.

Do not impose the same rule on `OLLAMA_HOST`; private Ollama connectivity
is an intentional operator configuration, not a caller-selected URL.

**Disposition:** ~~minimize the child environment in the next hardening
batch.~~ **✅ Child-environment half SHIPPED 2026-08-28** (assessment rev
117): allowlisted clone env (`_CLONE_ENV_PASSTHROUGH`) with a
sentinel-secret regression test, raw `OC_GIT_TOKEN` never in the child,
`GIT_TERMINAL_PROMPT=0`, `--no-checkout`, https userinfo and
query/fragment rejection, and clone-stderr scrubbing of token material.
Destination policy remains as written: a medium-high decision requiring
the actual non-GitHub consumer to be named.

## Finding 4: release version is not deploy identity

NemoClaw separates its public version from immutable source revision:

- [`generate-build-identity.ts`](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/core/generate-build-identity.ts#L7-L14)
  emits a build artifact;
- [`version.ts`](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/core/version.ts#L80-L135)
  validates revision shape and consistency; and
- managed-image contracts bind expected image, revision, release, and
  publication identity before reuse.

OpenChronicle CI already publishes a short-SHA image tag, and the NAS is
currently pinned to one. The process reports only `package_version`,
however. Several commits can legitimately share `3.0.0rc8`, so health
cannot prove which of those images is actually serving. This is a real
operator need: an earlier Portainer `OC_TAG` mismatch made a successful
push look deployed when the stack still ran old code.

The proportionate design is small:

1. Bake the full Git SHA into the image at build time; do not accept a
   runtime caller-supplied value as evidence.
2. Expose `build_revision` through the shared MCP/REST diagnostic payload
   and `oc version`.
3. Add OCI revision/source labels for external inspection.
4. Let post-deploy verification compare health to the expected revision.
5. Require an explicit `OC_TAG` in the NAS-specific compose file rather
   than silently falling back to `latest`.

Keep the minimal `/health` liveness probe static; build identity belongs
in the full diagnostic health response. Do not claim an image digest
unless the runtime can obtain it truthfully. Digest-pinned deployment is
optional hardening after source revision solves the demonstrated need.

**Disposition:** ~~verified operational gap; suitable for a small,
independent batch.~~ **✅ SHIPPED 2026-08-28** (assessment rev 118) —
smaller than scored: the validation pass found the OCI-label sub-claim
above was wrong at this review's own baseline (CI's
`docker/metadata-action` already emitted
`org.opencontainers.image.revision`), so what remained was baking the
SHA where diagnostics can read it. Landed: CI passes the full SHA as a
build arg, the Dockerfile writes `/app/build-revision`, health and
`oc version` report `build_revision` (file-read, not env-assertable;
`"unknown"` outside an image), and `docker-compose.nas.yml` requires
an explicit `OC_TAG`. Image-digest pinning stays optional hardening,
unadopted.

## Finding 5: duplicated public facts have current drift

NemoClaw uses generated or checked contracts where the same fact appears
in code and public documentation:

- a path-filtered
  [CLI/docs parity workflow](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/.github/workflows/docs-cli-parity-pr.yaml);
- a source-aware
  [environment-variable documentation check](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/scripts/check-env-var-docs.mts);
- generated platform/agent-variant facts backed by one matrix; and
- locked package installation plus built-package contract tests.

OpenChronicle does not need NemoClaw's docs site or large shell/TypeScript
validators. At the reviewed snapshot it had six concrete documentation
errors:

1. [CLI docs](../cli/commands.md) advertise `oc init --force` and
   `--no-templates`, even though those flags and template behavior were
   deliberately removed.
2. The same file describes `oc memory delete` only as a hard delete and
   omits its default preview/`--confirm` safety contract.
3. [MCP server docs](../integrations/mcp_server_spec.md) claim all 18 MCP
   tools map 1:1 to REST. `context_recent` and `onboard_git` are MCP-only,
   while maintenance status is API-only.
4. [Security posture](../configuration/security_posture.md) says
   `oc config show --json` reveals the full API key; implementation masks
   secrets in JSON and human output.
5. [Config docs](../configuration/config_files.md) say unknown
   maintenance jobs are silently dropped; implementation warns and
   skips them.
6. `docker-compose.nas.yml` calls the published image multi-arch while CI
   intentionally builds `linux/amd64` only.

The 2026-08-28 closeout repaired all six facts. One adjacent guard also
landed: the agent-instruction compatibility mirror now has a byte-parity
test. Three broader checks remain proportionate future candidates:

- introspect the argparse command tree and compare documented command
  paths/long options;
- compare registered MCP tool names with the documented MCP inventory,
  while documenting intentional transport-only exceptions; and
- statically collect literal `OC_*` accesses/helper calls and compare
  their names with `env_vars.md` and `.env.example`, using a small
  reasoned allowlist.

Do not force MCP/REST/CLI 1:1 parity; the current exceptions are sensible.
Do not generate every document. Generate or test only facts with multiple
consumers and demonstrated drift.

**Disposition:** current docs fixes closed in the review closeout. The
broader CLI/MCP/env inventory gates remain unscheduled and should be
considered before adding coverage metrics or more test lanes.

## Finding 6: a lock helps only when builds consume it

NemoClaw commits lockfiles, installs with `npm ci`, and audits the actual
resolved production graph. OpenChronicle's existing backlog already
records the opposite failure mode: an unconstrained MCP 2.0 resolve would
have built an image that fails at import, so the dependency was capped.

A tracked `uv.lock` now records the resolved graph for inspection, but CI
and Docker do not consume it. Committing the file alone does not make an
install reproducible.

When the existing lock/dependency-audit item is scheduled:

1. choose the runtime and development lock shape deliberately;
2. make CI and Docker fail on lock drift and install in frozen mode;
3. test supported Python/OS markers before replacing the current matrix;
4. audit and prune the exact locked runtime graph; and
5. retain Dependabot for updates and vulnerability notification.

Do not import NemoClaw's reviewed-npm exception ledger, publication
cohorts, SBOM, attestation, or signing machinery without a consumer that
will verify them.

**Disposition:** strengthens an existing backlog item; no new item and no
claim of reproducibility until frozen CI and Docker paths consume it.

## Finding 7: future offline replay needs idempotency, not retries

OpenChronicle has a demonstrated offline-write incident and a backlog item
leaning toward a client-side write-behind queue. Current `memory_save`
creates its UUID on the server. If a client times out after commit, a
blind replay creates a duplicate because the retry has no stable operation
or memory identity.

NemoClaw's resumable effects do not trust a completion receipt by itself.
Its
[`checkpoint-replay.ts`](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/onboard/checkpoint-replay.ts#L58-L130)
re-observes the postcondition and skips only when the current fingerprint
matches the recorded intent. Otherwise it reruns or reports disagreement.

When the queue is designed, start with the one demonstrated operation:
`memory_save`.

- Assign a stable operation ID and proposed memory ID before enqueue.
- Persist a queue schema version, canonical request hash, retry state, and
  private payload.
- On ambiguous delivery, read by the stable ID: matching hash means
  acknowledge; missing means send; different means conflict, never
  overwrite.
- Provide either optional caller-supplied `memory_id` or a narrow server
  idempotency-key seam. Choose in an ADR after checking MCP/REST parity.
- Protect the local queue because memory content itself may be sensitive;
  it cannot be secret-free like NemoClaw's onboarding checkpoint.

Do not expand the first iteration to offline reads, a shadow SQLite
replica, project reconciliation, leases, or a general side-effect engine.

**Disposition:** required design constraint on an existing, unscheduled
feature; not standalone implementation authorization.

## Finding 8: future restore should bind selection to mutation

OpenChronicle already has the right base: the SQLite online backup API, a
sibling temp file, and atomic replacement. The cloud-backup design also
requires candidate integrity validation, a pre-restore backup, WAL/SHM
cleanup, and restart. The 2026 cutover produced a corrupt migrated DB, so
this is not hypothetical disaster-recovery work.

NemoClaw adds two useful fences:

- [`state-file-restore.ts`](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/state/state-file-restore.ts#L19-L88)
  restores through SQLite's backup API into staging, runs
  `PRAGMA quick_check`, atomically swaps, deletes stale sidecars, and
  proves the installed DB accepts a write transaction; and
- snapshot recovery re-hashes the selected content immediately before
  destructive mutation and revalidates manifest identity.

Amend the existing live-restore design before implementing it:

1. Capture candidate size/hash when selected and recheck it immediately
   before swap.
2. Reject symlinked candidate, parent, destination, and staging paths.
3. Validate SQLite integrity and expected schema before mutation.
4. Require a successful pre-restore recoverable backup.
5. Stage, replace, remove stale `-wal`/`-shm`, restart, and perform a real
   `BEGIN IMMEDIATE`/rollback writeability probe.
6. Record explicit outcomes such as candidate invalid, pre-backup failed,
   swapped/restart pending, and post-restore validation failed.

Do not copy NemoClaw's directory-tree manifest; OpenChronicle's canonical
artifact is one database. Keep corrupt emergency copies explicitly
separate from recoverable backups: adding `quick_check` to normal backup
publication must not prevent forensic capture after integrity failure.

**Disposition:** constraint on the existing cloud-restore design.
NemoClaw also independently corroborates the staged-backup validation
already proposed by the Ollama review.

## Finding 9: critical maintenance state can look clean after restart

OpenChronicle correctly persists `last_run_at` and `last_success_at`, but
the critical outcome and `maintenance_degraded` flag are process-local.
After an integrity failure and process restart, the health boolean starts
false even though the timestamps can prove the last run did not succeed.
Also, `embedding_backfill` logs a completely failed batch but does not
raise, so the maintenance loop records that run as successful.

NemoClaw's larger readiness evidence model is unnecessary. Preserve the
small OpenChronicle model and make it truthful:

- derive database-integrity state from persisted success/run evidence or
  persist a small critical-job outcome enum;
- report `unknown`, not `ok`, before any verified integrity success;
- clear failure only after a verified successful check; and
- make an all-failed embedding backfill fail the job, while reporting a
  partial failure honestly.

The backfill portion is already proposed in the Ollama review. Record one
implementation item, not two.

**Disposition:** verified behavior; combine with existing maintenance and
provider-health debt rather than creating a NemoClaw-branded subsystem.

## Finding 10: operational state is still stored as user memory

The git-onboard watermark is explicitly machine-local, but it is stored as
a `MemoryItem` with `source=git-onboard-watermark`. Export and import now
hand-filter it after a real cross-device incident. That fix is correct,
but the representation still means:

- every public memory surface must remember whether to include it;
- stats and ordinary list calls can count/show operational state; and
- one watermark per project cannot distinguish two repositories or
  branches if that use case appears.

NemoClaw's manifests explicitly distinguish portable, machine-local,
confidential, and non-backed-up state. The proportionate OpenChronicle
lesson is a type boundary, not an agent manifest.

If git-onboard gains more state or a second-repository-per-project
consumer, move the watermark to a small dedicated table/port and migrate
the existing row. Key it by project today; add normalized repository and
branch identity only when the multi-repo consumer is real. Until then,
the current export/import filters are adequate and this cleanup should not
preempt correctness work.

**Disposition:** conditional architecture cleanup with a clear trigger.

## Bounded experiments and explicit triggers

| Candidate | What to test | Trigger required before adoption |
|---|---|---|
| Built wheel/container smoke | Install the built artifact, run `oc version`, migrate a temp DB, query diagnostics, complete one MCP initialize | A small CI experiment is reasonable; promote only if it catches packaging/runtime drift or stays cheap |
| Container containment | `read_only`, sized `/tmp` tmpfs, `no-new-privileges`, PID and file-descriptor limits | Prove entrypoint volume ownership and git-onboard workloads still function; do not `cap_drop: ALL` while startup needs `chown`/`gosu` |
| Persistent-memory secret warning | High-confidence patterns, redacted diagnostics, opt-in warn/reject, explicit bypass | First credential-capture incident, automated ingestion, or changed trust boundary |
| Backup `fsync` | File flush plus parent-directory durability on supported platforms | A written power-loss durability model and cross-platform test; maintenance state remains intentionally fail-soft |
| Full-SHA action pins | Dependabot-updated commit pins with version comments | Supply-chain policy requires immutable Actions; current mutable majors plus Dependabot are adequate |
| Image digest deployment | Resolve and verify digest at deployment | A verifier/operator workflow will actually consume it; source revision and SHA tag come first |

## Existing OpenChronicle choices this review validates

- **Keep v3 memory-only.** NemoClaw's value is complementary: its agents
  can consume OpenChronicle over MCP; OpenChronicle should not run them.
- **Keep SQLite online backup.** NemoClaw independently uses the same API
  for live agent databases and intentionally omits WAL/SHM from the
  backup artifact.
- **Keep caller-side context synthesis.** NemoClaw injects sandbox policy
  into agent prompts because it owns an agent runtime. OpenChronicle does
  not; adding a server prompt/context engine would reverse the v3 cut.
- **Keep the trusted-LAN auth decision.** Minimize subprocess credentials
  and caller-selected destinations without inventing a credential vault
  or enterprise multi-user policy layer.
- **Keep full-suite testing without a coverage ratchet.** NemoClaw's many
  lanes, changed-test graph, shuffle/leak diagnostics, and source-size
  budgets fit a much larger TypeScript product. Contract tests for the
  demonstrated drifts are more valuable here.
- **Keep transport exceptions explicit.** MCP, REST, and CLI do not need
  artificial 1:1 parity when a surface-specific consumer exists.

## Explicit non-fits

Do not incorporate these NemoClaw capabilities without a new, separately
approved product direction:

- OpenShell/Landlock/seccomp agent sandboxes and lifecycle controllers;
- model routing, inference gateways, GPU/runtime selection, or model
  catalogs;
- a credential broker/vault, secret rehydration, or provider-binding UI;
- messaging channels, device pairing, dashboards, agent plugins, or
  session supervision;
- broad network/process/filesystem policy engines or L7 egress proxies;
- directory-tree snapshot manifests and sanitizers for the canonical DB;
- a generic checkpoint/effect-replay framework around transactional
  memory operations;
- automatic transcript ingestion, dreaming/consolidation, replay markers,
  or shadow indexes without a measured retrieval need;
- a public docs platform, docs MCP server, `llms.txt`, or site-wide
  generation architecture;
- enterprise release plans, publication cohorts, reviewed dependency
  exceptions, SBOM/cosign/attestation machinery without a verifier; and
- audit-event chains already rejected for lack of a consumer.

Sanitizing memory content out of backups is especially inappropriate:
the content is the product data and may intentionally contain sensitive
incident evidence. Provider credentials are not stored in the database.

## Prioritized debt register at review time

The score follows the repository tech-debt convention:
`(Impact + Risk) × (6 − Effort)`, each input 1-5. A high score ranks work
*after it is eligible*; it does not bypass a feature trigger or authorize
implementation.

| Rank | Work item | Category | I | R | E | Score | Eligibility and business justification |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | Canonical agent-instruction source | Documentation / operations | 4 | 5 | 1 | 45 | **Closed 2026-08-28**; exact mirror plus regression test |
| 2 | Strict export/import envelope + atomic private export | Reliability / data safety | 5 | 5 | 2 | 40 | **✅ Shipped 2026-08-28** (rev 116); Finding 2 records the closeout |
| 3 | Content-bound, post-write-checked live restore | Reliability / data safety | 5 | 5 | 2 | 40 | Before cloud restore ships; the failure consequence is maximum, but no live restore exists yet |
| 4 | Least-privilege git child environment | Security | 4 | 5 | 2 | 36 | **✅ Shipped 2026-08-28** (rev 117); Finding 3 records the closeout. Destination policy (rank 8) stays open |
| 5 | Immutable build revision in diagnostics | Operations / provenance | 4 | 4 | 2 | 32 | **✅ Shipped 2026-08-28** (rev 118); Finding 4 records the closeout |
| 6 | Idempotent postcondition-checked offline replay | Reliability / feature design | 5 | 5 | 3 | 30 | Before the existing write-behind item ships; prevents duplicates after ambiguous timeout |
| 7 | Repair public docs + CLI/MCP/env parity checks | Documentation / correctness | 3 | 4 | 2 | 28 | **Docs closed 2026-08-28**; broader inventory gates remain unscheduled |
| 8 | Outbound clone destination policy | Security / SSRF | 4 | 4 | 3 | 24 | Decide now, implement after naming non-GitHub consumers; arbitrary remote hosts are accepted from a server-side tool |
| 9 | Lock consumed by CI/Docker + dependency audit | Build / supply chain | 4 | 4 | 3 | 24 | Existing backlog; a prior fresh resolve would have produced a startup-broken image |
| 10 | Durable integrity outcome + truthful backfill success | Operations / reliability | 4 | 4 | 3 | 24 | Combine with existing maintenance/provider-health debt; restart currently clears the visible degraded boolean |
| 11 | Built artifact/container contract smoke | Testing / packaging | 3 | 3 | 2 | 24 | Bounded experiment; current CI tests editable source but never starts the image it publishes |
| 12 | Dedicated git-onboard operational state | Architecture cleanup | 3 | 3 | 3 | 18 | Triggered by more state or multi-repo use; current filters contain the known cross-device problem |
| 13 | Container resource limits | Security / resilience | 3 | 3 | 3 | 18 | Pilot first; useful around untrusted repo history, but must not break entrypoint ownership setup |
| 14 | Backup publication `fsync` | Reliability hardening | 2 | 3 | 3 | 15 | Require a power-loss fault model and platform test before adding complexity |
| 15 | Opt-in persistent-memory secret warning | Privacy hardening | 2 | 2 | 3 | 12 | Trigger-gated; no incident, automatic ingestion, or changed trust boundary exists today |

## Recommended sequencing

### Phase A — restore documentation authority (partially closed)

1. ✅ Canonical `AGENTS.md`/`CLAUDE.md` ownership decided; volatile
   duplicated sprint facts removed; mirror parity tested.
2. ✅ Six verified documentation falsehoods corrected.
3. Pending: add narrow CLI, MCP-inventory, and environment-inventory
   checks when that validation batch is scheduled.

This is the smallest low-risk batch and prevents future agents from
implementing against false premises.

### Phase B — close current trust and identity gaps

1. Strictly validate the portable envelope and atomically publish export
   files.
2. Minimize the git child environment, disable prompting, and avoid a
   checkout.
3. Decide the supported server-side Git destination set; implement the
   smallest policy that preserves a named consumer.
4. Bake and expose the full source revision; require an explicit NAS
   image tag.

These changes are independent enough for separate commits and tests.

### Phase C — reproducible and truthful operations

1. Make one lock authoritative in CI and Docker, then audit that graph.
2. Persist or derive the integrity outcome and correct all-failed
   backfill reporting.
3. Run the built-artifact/container smoke as a bounded CI experiment.

### Feature-gated design work

- Add idempotency and revalidation before implementing offline
  write-behind.
- Add artifact binding, staged validation, sidecar cleanup, and a
  post-swap write probe before implementing live cloud restore.
- Move git-onboard state out of memory only when its state model or
  repository cardinality expands.
- Adopt containment, secret warnings, `fsync`, digest pinning, or action
  commit pins only when their stated trigger occurs.

## Options and trade-offs

| Option | Complexity | Fit | Consequence |
|---|---:|---:|---|
| Adopt NemoClaw/OpenShell components | Very high | Poor | Reintroduces agent/runtime scope, new services, policies, and credential custody without a memory-service consumer |
| Adapt the proven invariants in native OC code | Low to medium | Strong | Fixes demonstrated gaps while preserving the v3 architecture; recommended |
| Document only and change nothing | Low now | Poor for verified defects | Leaves stale agent authority, weak restore envelope, broad child credentials, and ambiguous deploy identity in place |

The middle option is intentionally selective. It accepts some duplication
of simple validation code to avoid importing a platform whose lifecycle
and security model OpenChronicle does not need.

## Source map

### NemoClaw

- [Repository and README](https://github.com/NVIDIA/NemoClaw/tree/b7261ff7cc73c76a15deb3e95291c24b1624534e)
- [Root contribution/scope guidance](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/AGENTS.md)
- [OpenClaw state manifest](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/agents/openclaw/manifest.yaml)
- [Hermes SQLite state contract](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/agents/hermes/manifest.yaml)
- [Strict agent-manifest readers](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/agent/manifest-readers.ts)
- [Checkpoint replay and postcondition checks](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/onboard/checkpoint-replay.ts)
- [SQLite state backup/restore](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/state/state-file-restore.ts)
- [Build identity](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/src/lib/core/version.ts)
- [SSRF boundary](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/nemoclaw/src/blueprint/ssrf.ts)
- [High-confidence secret scanner](https://github.com/NVIDIA/NemoClaw/blob/b7261ff7cc73c76a15deb3e95291c24b1624534e/nemoclaw/src/security/secret-scanner.ts)
- [Official architecture overview](https://docs.nvidia.com/nemoclaw/user-guide/openclaw/about/how-it-works)
- [Official agentic documentation architecture](https://docs.nvidia.com/nemoclaw/latest/user-guide/hermes/resources/engineer-agentic-documentation)

### OpenChronicle

- [Architecture](../architecture/ARCHITECTURE.md)
- [Live backlog](../V3_PLAN.md)
- [Current-state SSOT](../CODEBASE_ASSESSMENT.md)
- [Cloud backup and restore design](0001-cloud-backup.md)
- [OpenClaw memory review](0002-openclaw-memory-review.md)
- [Ollama provider/reliability review](0003-ollama-repository-review.md)
- [Export use case](../../src/openchronicle/core/application/use_cases/export_memory.py)
- [Import use case](../../src/openchronicle/core/application/use_cases/import_memory.py)
- [Git onboarding service](../../src/openchronicle/core/application/services/git_onboard.py)
- [SQLite backup implementation](../../src/openchronicle/core/infrastructure/persistence/backup.py)
- [Maintenance loop](../../src/openchronicle/core/application/services/maintenance_loop.py)
- [Maintenance handlers](../../src/openchronicle/core/infrastructure/maintenance/jobs.py)
- [Runtime diagnostics](../../src/openchronicle/core/application/use_cases/diagnose_runtime.py)
- [CI and image publication](../../.github/workflows/test.yml)

## Decision summary

NemoClaw should remain an external agent runtime that may consume
OpenChronicle, not a subsystem inside it. This closeout completed the
instruction-authority and current-docs work. The remaining immediate
OpenChronicle value is strict portable-state validation, a
least-privilege Git boundary, immutable build identity, and broader
targeted contract checks. Its replay and restore patterns should
constrain two already-planned features when those features are built.
Everything else needs a measured trigger or is an explicit non-fit.
