# Changelog

Release history for OpenChronicle v3. One entry per Docker-tagged
release; the deployed release is whichever tag the Portainer stack's
`OC_TAG` env points at. Created 2026-08-16 (review Batch E),
reconstructed from the status-doc revision addenda for rc1-rc5.

## v3.7.0 — 2026-09-30

The hardening release: the 2026-09-29 phase-end audit's fixes (C1 to C7), the
pre-deploy review's fixes for `v3.6.0..733c89ed`, a write probe for offline
restores (DATA-04), boot problems and URL credentials handled correctly in the
log (QUAL-12), and dependency updates. No schema change.

**Status:** prepared 2026-09-30; not yet tagged. It is tagged once OPS-08's
three green nights and its breakage check pass.

**Deploy note.** `docker-compose.nas.yml` is unchanged since v3.6.0, so stack
151's stored file needs no update, and the release is one env change.
Tagging waits for OPS-08 to close, so all three of its nights ran v3.6.0.

1. Pick a time away from the nightly push. `/api/v1/maintenance/status`
   shows `cloud_backup.last_run_at`. Recreating the container cancels a push
   in flight, the cancelled run still stamps `last_run_at`, and the job then
   waits 24 hours, so health would read `stale` at the 48-hour mark.
2. Start the request-latency sample **before** the change. This is design
   0010's deploy check for this release; v3.6.0's sample was missed because
   its boot-time work finished before sampling began.
3. `portainer_set_stack_env` with `OC_TAG=v3.7.0` and
   `OC_BACKUP_MCP_ENABLED=true` in the same call, with `pull_image=true`. The
   second setting enables the MCP backup tools (operator decision 2026-09-30,
   ROADMAP OPS-07); production already sets `OC_API_KEY` and `OC_BACKUP_DIR`.
4. Verify:
   - `health.package_version` is 3.7.0, `health.build_revision` is the tag's
     full SHA, and `schema_version` is still 4;
   - `/api/v1/health` without the key omits `db_path` and `config_dir`;
   - the MCP tool list now includes `db_backup_create`, `db_backup_list`,
     `db_backup_verify`, `db_restore_plan` and `db_restore_stage`. Exercise
     create, list, verify and plan, but **do not call `db_restore_stage` as a
     check**: a stage that is never activated has no discard path except
     deleting it by hand with the service stopped (ROADMAP DATA-07);
   - the boot log has no warning from the new settings parser;
   - the latency sample's p95 is within budget.

Rollback is one env change: `OC_TAG=v3.6.0` and `OC_BACKUP_MCP_ENABLED=false`.
There is no schema change, and v3.6.0 reads the same maintenance state file.
Manual snapshots taken through the tools stay in `/exports/backups/manual`,
which nothing prunes (ROADMAP DATA-07).

- **Unauthenticated health omits filesystem paths** (#75). With a key set,
  `/api/v1/health` returns `db_path` and `config_dir` only to a caller that
  presents the key. A keyed caller, and every caller when auth is off, still
  gets the full payload, so REST and MCP health match. This narrows what an
  unauthenticated probe sees; the two fields were never in the OpenAPI
  schema, so it is a MINOR change. `scripts/smoke_test.py` checks
  `package_version` instead of `db_path`.
- **A non-ASCII key header is a wrong key, not a 500** (#83). The middleware
  and the health route share one constant-time comparison of the header's
  bytes. ASCII keys authenticate exactly as before.
- **Offline restores prove the database takes a write** (DATA-04, #86).
  `scripts/offline_restore.py` probes after the swap in `activate` and
  `rollback`, records `write_probe` in `state.json`, and stops with the next
  step when the probe fails. A new `probe` action re-checks after a fix. The
  helper refuses to run as root, refuses an unwritable or foreign sidecar,
  and refuses a database written since the swap. See
  [local_backup_restore.md](docs/configuration/local_backup_restore.md).
- **Boot problems reach `OC_LOG_FILE`** (QUAL-12, #88). `oc serve` configures
  logging before building the container, so an unusable `OC_BACKUP_DIR` or an
  unrecognized setting is in the durable log, not only in the stderr a
  Portainer recreate discards. A failed container build is logged as
  `Cannot start: <reason>` for `serve` and printed to stderr for other
  commands; before, the reason went to stdout. A bad backup directory now names
  its cause: missing, not a directory, a symlink, not writable, or a parent
  that cannot be checked.
- **URL credentials never reach the log** (#88). Both log formats strip URL
  userinfo from the whole line, tracebacks and JSON extras included, and
  `httpx`/`httpx2` request lines are kept to DEBUG.
- **One parser for yes/no settings** (audit C3, #68). Blank means the
  default, and an unrecognized value logs a warning naming the variable and
  keeps the default. **Behavior change:** an unrecognized
  `OC_SEARCH_FTS5_ENABLED` used to turn search off silently; it now keeps
  search on. An unrecognized `OC_MAINTENANCE_DISABLED` or
  `OC_METRICS_ENABLED` now warns too, keeping the same default.
  `OC_BACKUP_MCP_ENABLED` still logs at ERROR, with new wording. Stack 151
  sets none of the four (checked 2026-10-01), so production behaves as
  before.
- **Maintenance fixes** (audit C1, C2 and C4: #66, #67, #69). A total
  backfill failure is labelled `failure` in the job metric, not `partial`.
  The loop and health find the state file through one path, and a stored
  timestamp without an offset reads as UTC everywhere. The
  `git_onboard_resync` placeholder reports `skipped`, not `ok`.
- **A cancelled cloud-backup child cannot hold the maintenance lock** (#80).
  The job kills the child and drains it for at most 5 s, logging
  `left its pipes open after kill` when that bound is hit.
- **The `oc` CLI and the stdio MCP server close their store on exit** (audit
  C7, #72).
- **`oc maintenance run-once`'s help lists the registered jobs**, which now
  include `cloud_backup`.
- **Removed:** `scripts/migrate_v2_to_v3.py` and `scripts/verify_v3_db.py`, the
  one-shot v2 cutover tools (DATA-05, #90).
- **Dependency floors raised** (#81, #85): `uvicorn>=0.54.0`, `openai>=3.19.2`
  and `ruff>=0.16.9`. These are minimums, not the versions the image ships:
  CI and the Dockerfile resolve fresh from the floors, so the image gets
  whatever is newest at build time. A build from `main` on 2026-10-01
  installed openai 3.22.1 and pyjwt 2.15.1. `uv.lock` (openai 3.19.2, pyjwt
  2.14.0) is used by neither (ROADMAP QUAL-06). pyjwt arrives only through
  `mcp[crypto]`, and the security fixes in 2.14.0 do not reach
  OpenChronicle.
- **Development:** the commit hook's identity check is an allowlist on author
  and committer (audit C5, #70); docs-parity and compose-parity tests
  (QUAL-05, QUAL-17: #76, #78).
- **Design 0010:** the release exception is extended to v3.7.0 (operator,
  2026-09-30), on stated terms because this release does touch the
  instrumented files. Two changes run per request: the auth key comparison
  and the log-line redaction (measured at 2.1 µs per access line). Metrics
  stay off by default.

## v3.6.0 — 2026-09-28

The offsite release: a nightly, encrypted, append-only push of the newest
backup snapshots to a cloud remote (design 0001 Phase 1, ROADMAP OPS-08).

**Deployed 2026-09-29** in the A7 order: stack file version 144 on v3.5.0,
then `OC_TAG` and the cloud settings. The boot-time run pushed three
snapshots in about 15 seconds, and `cloud_backup_status` reads `ok`.

**Deploy note** (design 0001 amendment A7; the runbook is
[cloud_backup.md](docs/configuration/cloud_backup.md)). The job runs on its
first maintenance tick after boot, and a failed first run waits 24 hours, so
the order matters:

1. The operator installs the minimal `[ocdrop]`-only `rclone.conf` into the
   running v3.5.0 container's `/config` volume as uid 1000
   (`docker exec -i --user 1000:1000 ... 'umask 077; cat > /config/rclone.conf'`).
   The named volume carries it into the new container.
2. Tag `v3.6.0` and let its CI publish the image.
3. One stack update: `main`'s `docker-compose.nas.yml` (it adds the
   `OC_CLOUD_REMOTE`, `OC_CLOUD_AGE_RECIPIENTS` and `RCLONE_CONFIG` lines)
   together with `OC_TAG=v3.6.0`, `OC_CLOUD_REMOTE=ocdrop:openchronicle/nas`
   and `OC_CLOUD_AGE_RECIPIENTS=<primary>,<recovery>` (the escrowed public keys).
4. Verify `health.package_version=3.6.0` and `health.build_revision`; after the
   boot-time run, `cloud_backup_status.status=ok` and
   `/api/v1/maintenance/status` shows `cloud_backup` `last_outcome: ok`; the
   `cloud_backup: age recipients` log line matches escrow.

Rollback is moving `OC_TAG` back to `v3.5.0`: no schema change, v3.5.0
ignores the new variables, and the remote keeps what was pushed.

- **Nightly offsite push** (`cloud_backup`, daily). It selects the 3 newest
  published snapshots plus the newest from each of the 3 most recent UTC days,
  verifies each against its manifest, encrypts the `.db` and its `.json` with
  age to both escrowed recipients in a private temp dir under the backup root,
  and `rclone copy --ignore-existing`s them: the job never deletes or
  overwrites. The whole run is bounded at 900 s and a hung child is killed.
  It succeeds only when something fresh went offsite: an empty, stale (over
  26 h) or future-stamped source, a root run, a missing `rclone.conf`, invalid
  configuration, a manifest mismatch, or an age or rclone failure all fail
  the run. With `OC_CLOUD_REMOTE` unset it skips and never records a success.
- **Health gains `cloud_backup_status`** (additive, MINOR): `disabled`, `ok`,
  `stale` (no push within 48 hours, or ever) or `misconfigured`, which takes
  precedence. It never touches `maintenance_degraded` or
  `backup_last_run_failed`.
- **The image adds rclone 1.75.1 and age.** The entrypoint sets an existing
  `rclone.conf` to 600, and reports a failed `chmod` instead of hiding it.
- **`oc maintenance run-once`** prints `SKIPPED` with the reason when a job
  did nothing, instead of `OK`.
- **CI:** a PR-only `Image smoke test` job (now a required check) builds the
  image and runs the image smoke plus an end-to-end push, decrypt and
  append-only check.
- **Design 0010:** the release exception is extended to v3.6.0 (operator,
  2026-09-28); no metrics code changed.

## v3.5.0 — 2026-09-28

The backup release: design 0017's catalogued, verified snapshots, written to
an exposed backup root that is separate from the live database's volume.

**Deployed 2026-09-28** (ROADMAP OPS-04; the 0017 step-5 check passed).

**Deploy note:** stack 151 already runs the reconciled compose (OPS-03). It sets
`OC_BACKUP_DIR=/exports/backups` and binds `/volume1/docker/openchronicle/exports`
(owned by uid 1000, group `users`, mode 0750). The deploy moves only `OC_TAG`
to `v3.5.0`. Verify `health.package_version=3.5.0` and `health.build_revision`.
Then run 0017 step 5: a snapshot lands in `/exports/backups`, its digest matches
when read over SMB, and a disposable restore passes integrity, foreign-key, row,
ID and search checks. No schema change separates v3.4.0 and v3.5.0, so rolling
back is moving `OC_TAG` back.

- **Nightly backups move to `OC_BACKUP_DIR`** (0017). `db_backup`, and the
  backup `db_vacuum` takes first, write to `auto/` under `OC_BACKUP_DIR`
  (default `${data_dir}/backups`, the old location). Each snapshot is
  published in rollback-journal mode with a verified JSON manifest. Retention
  still keeps the 7 newest plus the newest per day for 7 days, and it counts
  only published snapshots. Snapshots without a manifest, including every
  pre-0017 file in `/data/backups/auto`, are never pruned, so the old ones stay
  for explicit review. A snapshot that fails verification is kept as
  `*.failed-verify` or `*.failed-quick-check`, and the job fails.
- **A failing nightly backup shows in health** (v3.5.0 pre-deploy review,
  finding 1). A new health field, `backup_last_run_failed`, reads true when
  the last scheduled `db_backup` run failed. It comes from the persisted run
  and success stamps, so it survives a restart. The next scheduled success
  clears it; manual backups do not. It is deliberately separate from
  `maintenance_degraded`, which still means "the database may be corrupt"
  (design 0001 section 6.2). Folding a backup failure into it would have sent
  operators to a restore. Usually the backup root is at fault, but a live
  database that fails its checks also fails the backup; the incident runbook
  says how to tell the two apart. Before this, a broken backup root failed every
  nightly backup while health read clean. The gap predates this release but
  mattered more once backups moved to an operator-managed host bind. The
  field is additive (MINOR).
- **Bad backup configuration never stops startup.** An unusable
  `OC_BACKUP_DIR` is logged at ERROR, and manual and scheduled backups fail
  until it is fixed. Under `restart: unless-stopped`, raising instead would
  crash-loop the memory service.
- **Backup MCP tools, off by default** (0017). `db_backup_create`,
  `db_backup_list`, `db_backup_verify`, `db_restore_plan` and `db_restore_stage`
  register only when
  `OC_BACKUP_MCP_ENABLED=true`, `OC_API_KEY` is set and `OC_BACKUP_DIR` is
  explicit. The default tool inventory is unchanged, so this is MINOR under
  STABILITY.md. Enabling them is ROADMAP OPS-07.
- **Guarded offline restore** (`scripts/offline_restore.py` and the runbook):
  `stage`, `activate`, `rollback` and `retire-stage`, drilled on the NAS on
  2026-09-24.
- **Design 0010 release gate:** the operator extended the v3.4.0 exception to
  this release (2026-09-28). v3.5.0 changes no metrics code, and metrics stay
  off by default. The exception covers release, not enablement.
- **Housekeeping:** `uv.lock` recorded the project as 3.3.0 because the v3.4.0
  release did not refresh it. It now matches.

## v3.4.0 — 2026-09-24

The correctness release: the four fleet-review #27 fixes, the model-revision
fix, the query-revision race fix, and design 0010's metrics instrumentation,
shipped **off by default** under an operator exception (below).

**Deploy note:** the tag was not deployed when it was cut. It was **deployed
2026-09-28** (ROADMAP OPS-01). By then OPS-03 had reconciled stack 151's
compose with the repository file and `OC_LOG_FILE` was already set, so the
deploy moved only `OC_TAG` to `v3.4.0` (`portainer_set_stack_env` with an image
pull). Verify `health.package_version=3.4.0`, `health.build_revision`
(`9b1e83e6`), and `model_revision_state`. No schema change separates v3.3.0 and
v3.4.0, so rolling back is moving `OC_TAG` back.

- **Blank content is refused before any write** (fleet-review #27 item 1).
  `memory_update(content="")` over MCP blanked the memory and deleted its
  embedding while reporting success. REST and the CLI let whitespace-only
  content through. The add and update use cases now refuse blank content
  ahead of any write, on every surface. Versioning: STABILITY.md allows
  tightening validation without a MAJOR bump when the value was already
  documented as invalid. Memory content already was: the REST schema
  declared `min_length=1` for add and update, and MCP `memory_save` refused
  blank content. This applies that rule consistently and closes a data-loss
  path, so it ships in a MINOR release.
- **Background backfill failures are visible** (#27 item 2). A failed
  `memory_embed background=true` run is logged at ERROR, and health gains
  `last_background_backfill` (`outcome`, `finished_at`, counts or
  `error_type`). Additive.
- **Maintenance overlap warnings are truthful** (#27 item 3). A job queued
  behind another logs one INFO line; a real overlap warns once per run,
  instead of once per tick (about 1,200 false warnings per long backfill).
- **OpenAI-compatible embedding responses are validated at the boundary**
  (#27 item 4). Non-finite, empty, mixed-length or surplus vectors are
  refused, sharing Ollama's validator.
- **An unknown model revision is no longer "no revision"** (design 0014 §1.1,
  ADR 0005 §7). A failed revision probe used to be cached as "no revision",
  which blanked semantic search while health read `active` and re-embedded
  the corpus. Adapters now expose a revision snapshot, writes refuse while
  it is unknown, and a service-owned refresher probes and reconciles. Health
  gains `model_revision_state` and `model_revision_verified_at`, and reads
  `degraded` while the revision is unknown.
- **Queries stay on one model revision** (PR #34, design 0016 track 1). A
  search snapshots the revision around the query embed, retries once on a
  change, falls back to keyword results when changes continue, and
  semantic-only search returns `MODEL_REVISION_CHANGED` (HTTP 502).
- **The NAS log file exists.** `OC_LOG_FILE` defaults to
  `/output/logs/openchronicle.log`, on the output volume; the old default
  was on no volume, so every boot fell back to stderr. httpx no longer logs
  request URLs, or any `OLLAMA_HOST` credentials, at INFO.
- **Smaller fixes:**
  - `onboard_git`'s local git calls get the allowlisted environment. An
    inherited `GIT_DIR` had walked the wrong repository.
  - The per-request MCP lifespan lines log at DEBUG.
  - A skipped maintenance backfill records `skipped` rather than `ok`.
  - Reconciliation honours a disabled `embedding_backfill` job.
  - `oc memory update --content ""` is refused.
  - The entrypoint's bootstrap line goes to stderr.
  - The repository NAS compose keeps the REST Host-list fallback (PR #35);
    it is compose-only, and stack 151 is detached.
- **Metrics instrumentation (design 0010), off by default.** Bounded
  Prometheus metrics and a guarded `/metrics` endpoint exist only when
  `OC_METRICS_ENABLED=true`; the disabled path bypasses the recorder. An
  optional local Prometheus profile ships in the NAS compose. **Operator
  exception, 2026-09-24:** design 0010 blocks any release carrying this code
  while its B/A (disabled-path) overhead comparison is inconclusive, and it
  still is. The operator released it anyway: metrics stay off, and the
  measured disabled-path median losses (0.129% and 0.399%) sit inside host
  noise. Enabling metrics still needs 0010's gates.
- **CI:** every image is smoke-tested before it is pushed (build revision,
  runtime imports, `/health`).
- **Housekeeping:** line endings normalized to LF (`.gitattributes`), and
  dependency updates (the uv runtime group, uvicorn, setuptools, wheel, and
  the smol-toml fix in the Markdown tooling).

Deliberately deferred low-severity follow-ups are listed in V3_PLAN item 9.

## v3.3.0 — 2026-08-29

The health-honesty release: ADR 0009 end-to-end (permanent
embed-failure classification) plus started-job reindexes.

**Deploy note:** after the redeploy, run one backfill
(`memory_embed` with `background=true`, or the maintenance loop's
next cycle) — it parks the 9 over-length rows as tombstones and
health flips `degraded`/`stale: 9` → `active`/`unembeddable: 9`.

- **Permanent embed-failure classification (ADR 0009) — over-length
  content parks instead of poisoning health** (additive/MINOR). Under
  ADR 0005's `truncate:false` contract, rows exceeding the embedding
  model's context failed visibly but were retried every backfill cycle
  and kept `embedding_status.status` reading `degraded` forever on a
  healthy system (observed live: 9 rows, `failure_count` 36 and
  climbing). Now the adapters classify the upstream over-length
  rejection as the new canonical `CONTENT_TOO_LONG` (Ollama: 400 +
  "context length", grounded in the captured rejection; OpenAI:
  structured `code` first, then a 4xx-gated message fallback grounded
  in a live capture of the real endpoint's body — generic
  OpenAI-compatible hosts that match neither conservatively keep
  retry-forever), and per-item consumers park the row as a
  `status='content_too_long'` tombstone inside the ADR 0005 identity
  (migration 004; empty payload, honest `dimensions=0`, written
  through the same CAS). A successful later save resurrects the row
  via `status = excluded.status`. Candidacy exclusion is emergent (a
  current tombstone reads as current to the status-blind freshness
  check); the park expires on content edits or space changes, and
  `force=true` retries. No failure counter moves for a classified
  outcome — save parks and returns normally (no caller traceback), an
  over-length query degrades to keyword-only, and backfill reports
  the additive `tombstoned` count (a tombstoned-only run is `ok` on
  MCP/REST, a maintenance-job success, and CLI exit 0). Health gains
  the additive `unembeddable` field (current tombstones);
  `embedded` refines to `count(status='ok')` — byte-identical on any
  pre-ADR database. **Deploy note:** the first backfill after the
  redeploy writes the 9 tombstones, reports `ok` with
  `tombstoned: 9`, and health goes `active` with `unembeddable: 9`.
- **`memory_embed` gains `background=true` — started-job semantics for
  full reindexes** (additive/MINOR, MCP + REST). The synchronous
  default remains for incremental backfills; the background path
  returns `started`/`already_running` immediately and progress is
  observed in health (`stale`/`missing` count down). Exists because
  the v3.2.0 cutover's own reindex (~20 min on the NAS) outlived every
  interactive transport: the MCP tool would have timed out, and even
  even the stopgap background REST call's connection dropped mid-run.
  One background backfill per service at a time (a second start is
  refused, not queued); overlap with the maintenance loop's periodic
  backfill remains safe via CAS publication.

## v3.2.0 — 2026-08-29

The embedding-identity release: ADR 0005 end-to-end (schema v2+v3
migrations, CAS publication, space-filtered search, truthful Ollama
contract, batched backfill), the generic cloud-provider path, and the
provider-benchmark hardening that cleared LAN-local `nomic-embed-text`
for the cutover this release deploys.

**Deploy note:** the migrations mark all pre-existing vectors stale;
run `oc maintenance run-once embedding_backfill` (or the `memory_embed`
MCP tool) after the redeploy — semantic search degrades to FTS5-only
until the reindex finishes (`stale` counts down in health).

- **The generic cloud-provider path is safe by construction.** The
  `openai` adapter's `settings_fingerprint` now includes `base_url`,
  so the same model label on different OpenAI-compatible hosts (Voyage,
  Gemini, Mistral, Together, ...) is a different vector space — a host
  switch triggers the standard reindex instead of silently mixing
  vectors. `OPENAI_BASE_URL` is Portainer-wired; the provider matrix
  lives in design/0006.
- **Backfill logs known provider failures as one line.** A categorized
  `ProviderError` (e.g. a `truncate:false` over-length rejection)
  already carries the actionable upstream message; it no longer emits
  a full traceback at WARNING — hundreds of them flooded the log
  during benchmarking. Stacks move to DEBUG; unexpected exception
  types keep theirs.
- **Local Ollama over HTTPS is first-class.** A scheme-less
  `OLLAMA_HOST` gets `http://` prepended instead of producing a broken
  URL; `https://` hosts work end-to-end (embed + capability probe);
  and `OLLAMA_VERIFY_TLS=0` permits LAN self-signed certs (default:
  verify, disabling logs a warning).
- **Content-egress notice for cloud embedding providers.** When the
  configured embedding endpoint is not clearly LAN-local, startup logs
  a WARNING naming the endpoint and the consequence (every save's full
  content and every semantic query leave this host), and health
  carries an additive `content_egress: "remote"|"local"` field.
  Fail-safe classification: ambiguous hosts warn. Applies to `openai`
  anywhere and to `ollama` pointed at a cloud host alike. A notice,
  not a control — the operator's cloud choice stands; the secure path
  remains a LAN-local provider.
- **`OC_LOG_FILE`: logs that survive a container recreate.** A
  Portainer redeploy recreates the container and its stderr history
  dies with it — observed mid-diagnosis when the v3.1.0 deploy
  destroyed the v3.0.0 logs a bug report needed. When set, the log
  stream is mirrored to a size-rotating file (5 MiB × 4, same
  format/level as stderr, fail-soft on unwritable paths); the NAS
  compose defaults it onto the output volume. stderr stays primary.
- **`memory_stats.by_tag` is bounded** (dogfooding feedback). The tag
  histogram now shows the `top_tags` most frequent tags (count-ordered,
  default 25, param on MCP + REST) with an `other_tags` rollup count —
  an unscoped call used to return the corpus's entire tag tail
  (~700 entries, mostly count-1) regardless of what the caller wanted.
- **Bounded batch backfill — ADR 0005 Phase D** (design 0003, Finding
  3). The backfill chunks through `embed_batch` (32 per chunk) instead
  of one HTTP round-trip per memory, with a per-item fallback that
  isolates a poisoned input from its chunk-mates and catches
  wrong-cardinality batch answers. The deploy-time reindex now runs at
  batch speed. All ADR 0005 phases are complete.
- **Truthful Ollama adapter contract + full space identity — ADR 0005
  Phase C** (design 0003, Findings 1+2). Schema v3 adds
  `model_revision` (nullable, `IS`-matched) and `settings_fingerprint`
  (one shared canonical-JSON hash, never per-adapter). The Ollama
  adapter now sends `truncate: false` (an over-length input fails
  visibly with Ollama's own actionable message rather than silently
  embedding a prefix), sends `dimensions` only when configured and
  validates the response against it, validates every returned vector
  (cardinality, emptiness, finiteness, batch consistency), surfaces
  structured error bodies, short-circuits empty batches, and derives
  `model_revision` from a cached non-fatal `/api/tags` probe. Health
  gains the dimensions-truth trio (`configured_dimensions` /
  `dimensions` / `stored_dimensions`) plus `model_revision`.
- **Composite embedding identity — ADR 0005 Phase B** (accepted after
  a three-critic adversarial review of the design). Schema v2 adds
  `provider` + `content_hash` to `memory_embeddings`; vector
  publication is compare-and-swap on the memory's current content
  (closing the slow-older-writer race); semantic search filters the
  full space identity — a wrong-provider row under the same model
  label, a wrong-dimensions row, or a pre-migration sentinel is
  invisible to ranking, never mixed or crashed. Health's `stale`
  becomes the sum of disjoint `space_mismatch` + `content_mismatch`
  buckets (a strictly more truthful refinement of the old
  model-string-only count — documented MINOR). **Deploy note:** the
  migration marks every pre-existing vector stale; run
  `oc maintenance run-once embedding_backfill` after the redeploy —
  semantic search serves FTS5-only for the few minutes the reindex
  takes, observable in health as `stale` counts down to 0.
- **`memory_list` gains filtered chronological enumeration** (design
  0002, batch B — the demonstrated Mnemosyne consumer). Additive on
  every surface (MCP, REST, use case, port): `tags` (require-all),
  `exclude_tags` (drop-any), and `order_by` — `"pinned_first"` keeps
  today's browsing order, `"created_at"` is pure chronology with no
  pin float. All predicates apply in SQL before pagination, so "the N
  newest rows carrying tag X but not tag Y" is one bounded call
  instead of a full-project compact scan plus per-row gets. MINOR;
  tool-schema snapshot regenerated.

## v3.1.0 — 2026-08-29

The comparative-review remediation release. A validation pass first
re-verified every claim in the four `docs/design/` review documents
against HEAD (all SHIPPED claims confirmed; ~14 of 16 defect claims
still held), then every implementation-ready verified defect shipped
as its own commit — assessment revisions 116-126, 688 → 758 tests.
MINOR: the surface changes are additive (`build_revision` in
diagnostics, `include_pinned` and the new provider-health fields), and
`top_k` becoming a total budget enforces the already-documented
contract.

- **Provider and maintenance health stop being success-shaped**
  (design 0003 Finding 4 + design 0004 Finding 9). An all-failed
  embedding backfill now fails the maintenance job instead of
  recording a nightly "ok" with zero vectors generated; provider
  failure counters cover search, save, AND backfill (new
  `failure_count`/`last_failure_at`/`last_failure_op` health fields
  drive the degraded status — a dead provider used to read `active`
  until someone searched); and `maintenance_degraded` derives from
  persisted run/success evidence as well as the in-process flag, so a
  container restart no longer clears a failed integrity check from
  the health surface. All additive.
- **Staged backups are validated before publication** (design 0003,
  Finding 5). The nightly backup staged to `.tmp` and atomically
  renamed with no check the artifact was openable. The staged file now
  must pass `PRAGMA quick_check` (read-only open) before it may
  replace the previous backup; a failing artifact is quarantined as
  `<dest>.failed-quick-check` for forensics — evidence the live DB may
  be corrupt — never deleted, never published, never pruned by
  retention.
- **`include_pinned` is available on every search surface** (design
  0002, batch A; operator decision). MCP `memory_search` and
  `GET /api/v1/memory/search` gain the visibility switch the CLI
  already had: `false` hides pinned items entirely — no float, no
  ranking, strict project scope — distinct from `pinned_limit=0`,
  which only stops the float. Additive optional parameter (MINOR);
  tool-schema snapshot regenerated.
- **`top_k` is now a total response budget** (design 0002, batch A;
  operator-decided contract). Floated pins and ranked results share
  one combined stream that `top_k` bounds and `offset` paginates — a
  `top_k=8` search returns at most 8 items, pins included, where it
  could previously return `top_k + pinned_limit`. Pin-heavy queries
  now yield fewer ranked hits per page; pagination walks the combined
  stream with no duplicates or gaps. `context_recent.memory_limit`
  becomes truthful transitively.
- **A content update invalidates its embedding before re-embedding**
  (design 0002, batch A). A failed re-embed used to leave the OLD
  vector in place with a current model string — semantic search ranked
  the old content indefinitely and backfill never saw the row. The
  vector is now deleted on every content change (provider configured
  or not) before regeneration is attempted: failure leaves it missing
  and backfill-visible, never stale. Tags-only updates keep it.
- **Semantic search filters eligibility before its top-N window**
  (design 0002, batch A). Similarity ranking used to run over the
  whole model-scoped embedding table with project/tag filtering
  applied only after the bounded top-N — unrelated vectors consumed
  the window and the best in-scope results could be missed. A new
  `eligible_memory_ids` store primitive (same scope + tags rules as
  ranked search, by construction) narrows the candidate set first.
- **Search tag filters apply in SQL, before LIMIT** (design 0002,
  batch A). Both branches used to over-fetch a bounded window
  (`limit * 4` FTS rows, a 200-row recency scan on the fallback) and
  tag-filter in Python — a valid tagged result past the window was
  silently omitted. Tag containment now runs inside the query via
  JSON1 `json_each` on both branches, so a tagged row is found
  regardless of how many untagged rows outrank it.
- **MCP `onboard_git` clones from github.com only** (design 0004,
  Finding 3, destination-policy half; decided 2026-08-28 — no
  non-GitHub consumer exists). The server-side tool used to point its
  own `git clone` at any HTTPS/SSH host, including loopback, RFC1918,
  and cloud-metadata addresses. `repo_url` is now gated to
  `https://github.com/<owner>/<repo>` before the worker thread runs;
  other hosts and local paths remain available through the
  `oc onboard git` CLI. Widening path, if a non-GitHub consumer ever
  appears: address-class rejection, not deleting the gate.
- **Deploy identity: `build_revision` in health, `OC_TAG` required**
  (design 0004, Finding 4). CI bakes the full git SHA to
  `/app/build-revision` (a file, not an ENV — a compose edit cannot
  assert a revision the image was never built from); the diagnostics
  payload on both health surfaces and `oc version` report it, so a
  same-version redeploy is finally verifiable from health alone.
  Outside an image it honestly reads `"unknown"`.
  `docker-compose.nas.yml` now *requires* `OC_TAG` (`${OC_TAG:?...}`)
  instead of silently falling back to `:latest`.
- **`onboard_git`'s `git clone` child runs least-privilege** (design
  0004, Finding 3, child-env half). The subprocess env was
  `os.environ.copy()` — every server secret crossed the boundary for an
  operation that needs none of them. Now an allowlist (binary
  discovery, Windows plumbing, locale, TLS roots, proxies, ssh-agent),
  sentinel-tested so a future secret cannot cross either; the raw
  `OC_GIT_TOKEN` never enters the child (only the derived host-scoped
  header does); `GIT_TERMINAL_PROMPT=0` fails a token-less private
  clone fast instead of blocking 300s on a prompt nothing can answer;
  the clone is `--no-checkout` (the walk reads history, never the
  worktree); https URLs carrying userinfo, query strings, or fragments
  are refused; and clone stderr is scrubbed of token material before it
  reaches an error message. Server-side destination policy (loopback /
  private / metadata addresses) is deliberately not changed here — it
  is an open product decision recorded in the review.
- **The portable JSON envelope is a real versioned contract, and export
  publication is atomic.** First implementation batch from the
  comparative reviews (design 0004, Finding 2). Import used to check
  only that `format_version` existed: `format_version: 999` imported
  "successfully", an envelope missing its arrays read as a legitimate
  empty restore, rows without an `id` leaked `KeyError`, and an unknown
  project reference or duplicate in-envelope id died as a raw
  `sqlite3.IntegrityError`. The whole envelope is now validated before
  the write transaction opens — version dispatch, required arrays,
  per-row types, project references against store ∪ envelope, duplicate
  ids — with every rejection a `ValidationError` naming the failing
  collection, index, and row id. Id *shape* and unknown keys are
  deliberately not validated (restore must not fail on data the store
  already held; newer-build envelopes must import). `oc memory export
  --out` now writes to a `mkstemp` sibling (0600 where supported) and
  publishes with `os.replace`, so a failed export can no longer
  truncate the previous good backup. 688 → 708 tests.
- **MCP migration readiness.** An mcp 2.x migration was assessed and
  deferred on named triggers rather than on a premise that turned out to
  be false. `pyproject.toml`, `.github/dependabot.yml` and
  `docs/V3_PLAN.md` had all justified the `mcp<2` cap by claiming 2.0
  "moved FastMCP to the standalone `fastmcp` package". Verified against
  the 2.1.1 wheel: `mcp.server.fastmcp` is a tombstone module raising
  `ModuleNotFoundError`, and FastMCP was **renamed in-tree** to
  `mcp.server.mcpserver.MCPServer`. The cap is still correct; the reason
  was not, and the wrong reason made migration look like a third-party
  dependency swap rather than a first-party rename.
- **The MCP tool signatures are now actually enforced.** `STABILITY.md` has
  bound since the v3.0.0 tag — a breaking change to a tool signature is a
  MAJOR event — and nothing checked it. All 18 schemas are snapshotted to a
  committed fixture, with a test that fails on any change and names the tool.
  Descriptions are deliberately excluded: they are the LLM-facing contract
  and worth getting right, but they are documentation, not signature, and a
  guard that fails on every reworded docstring gets regenerated reflexively
  until it guards nothing. Verified in both directions — a required-ness
  change fails, a description-only edit passes. It doubles as the
  pre-migration baseline: the only way to later prove lifting the `mcp<2`
  pin was schema-invisible is to diff against a snapshot taken before it.
- **Three MCP baselines, so a future migration can be proved
  schema-invisible rather than asserted.** The tool-schema snapshot now
  covers `outputSchema` as well as `inputSchema`; the client-visible
  error envelope is pinned across five failure shapes on mcp 1.29.0
  (previously zero coverage — no test referenced `isError`); and a forged
  `Host` is asserted to be rejected through the mounted `/mcp`, which
  mutation testing showed was one line from silent disablement.
  679 → 688 tests.
- **Dependency floor `mcp>=1.0` → `>=1.29`** in both the `mcp` and `dev`
  extras — the version those baselines were captured on. The old floor
  was fiction; nothing had verified the server against mcp 1.0.
  `uv.lock` regenerated, which also cleared a stale `3.0.0rc8` project
  version left over from the release.

## v3.0.0 — 2026-08-28

The first stable v3 tag. From here `docs/api/STABILITY.md` binds: the
REST schemas, MCP tool signatures, and `core.json` schema are under
semver, and a breaking change to any of them is a MAJOR event rather
than "the surface as designed".

Everything below shipped between rc8 (2026-08-17) and this tag.

- **`cluster_commits` no longer hangs forever on a non-positive cap.** With
  `max_clusters <= 0` the merge loop never terminated: once the list was down
  to one entry, `smallest_idx` was 0, the `len(merged) > 1` arm was false, so
  `merge_into` was 0 too — the pop was skipped, nothing changed, and `1 > 0`
  kept it spinning. This was reachable from outside: the `onboard_git` MCP
  tool passed `max_clusters` through unbounded while clamping its immediate
  neighbour `max_commits_per_cluster` one line above, and
  `oc onboard git --max-memories` had no bound either. An agent passing 0
  would wedge an MCP worker thread permanently. Now floored at both the tool
  boundary and inside the algorithm; a nonsensical cap degrades to one
  cluster rather than failing the run. 676 → 678 tests.
- **Ollama Cloud recorded as trigger-gated research, not a rejection.**
  Investigated against the live API 2026-08-28: it hosts 19 models, none
  advertising the `embedding` capability, and every known embedding model
  name 404s — so it offers OpenChronicle nothing *today*. That is not the
  same as a dead end. The 19-model baseline is recorded so a future check
  is a diff rather than a re-investigation, the re-check needs no API key
  (`/api/tags` is public), and the adopt-work is pre-scoped: the adapter
  already targets `/api/embed`, the correct cloud path, so the change is one
  `Authorization: Bearer` header. Filed in V3_PLAN's follow-ups for the
  quarterly audit cadence.
- **`_get_container` extracted from all five MCP tool modules.** It was
  byte-identical in each — one line, so the duplication cost nothing to
  read, but it hardcoded the lifespan's `"container"` key five separate
  times. That is the shape the extraction bar exists for: not volume, but a
  contract that drifts the day someone renames the key and updates four of
  five copies. Now one helper with the key as a named constant, pinned
  against `server.py`'s lifespan by a test that fails if either side is
  renamed alone.
- **PII scanning gets a CI backstop.** The home-path and personal-email
  checks existed only in the pre-commit hook, which is bypassable by design
  — `--no-verify`, an unset `core.hooksPath`, a fresh clone before the
  installer runs, a push from another machine. Now enforced in CI too, with
  the patterns kept generic (the file is public, so baking in a real name
  would leak what it guards) and findings **masked** in the failure message,
  since a test that prints the PII it caught into a public log defeats
  itself. Positive and negative controls ship with it — the negatives matter
  more, because a pattern that also flagged `users.noreply.github.com` or
  `/data/...` would fail on every commit and be deleted within a day.

  The repo's one historical gitleaks hit is now allowlisted by full SHA,
  after being identified rather than assumed: `generic-api-key` in a test
  file absent from HEAD, whose "secret" gitleaks itself renders as
  `REDACT…` — a placeholder. A full-history sweep now reports clean, so the
  next hit means something instead of being the standing one everyone
  learned to ignore.

  Also: `v3/develop` is no longer a CI trigger (121 commits behind `main`,
  none ahead, untouched since 2026-05-05) and SECURITY.md stops describing
  the v3 cutover as a future event; `.codex/**` and `uv.lock` join
  `paths-ignore`, both tracked and both exactly the docs/tooling commits the
  list exists to keep from rebuilding the image.

  The `gitleaks.yml` checkout pin was left to Dependabot rather than
  hand-edited, and PR #20 has since merged it — `actions/checkout` is now
  `@v7` across all four uses, and `gitleaks-action` is at `@v3`, verified
  green against the new commit-allowlist. The stated reason for deferring
  was wrong, though: this file is fleet-canonical, but the fleet had
  already split 2-2 on these versions, so the merge moved this repo onto
  the majority side rather than forking it. `downloader-mcp` and
  `portainer-mcp` still lag at v6/v2.
- **`oc config show` survives the config being broken.** It is the command
  an operator runs *because* core.json is wrong, and it was the one command
  with no error handling: pre-container commands bypass `_build_container`,
  and its `try/except` with them. Three compounding defects — a non-UTF-8
  core.json escaped as a raw `UnicodeDecodeError` (the file read sits inside
  the same `try` as the parse, but only `JSONDecodeError` was caught, losing
  the filename `ConfigLoadError` exists to attach); malformed JSON produced a
  traceback rather than an exit code; and an existing-but-empty core.json
  reported as "not found", sending the operator to look for a missing file
  instead of an empty one. All three reproduced before the fix and verified
  after. 659 → 666 tests.
- **Two conventions promoted from prose to enforcement.** The agent
  instructions say to use `utc_now()` rather than an inline
  `datetime.now(UTC)`; seven sites across six files had drifted past it.
  All now route through the helper, and an AST-based guard fails if a new
  one appears — AST rather than text matching, because the text version
  flagged a *comment* that merely mentions the call, and a guard that cries
  wolf gets deleted. This is not only style: a naked clock read is what
  makes time un-fakeable in a test.

  Separately, `scan_repository()` now refuses to return a corpus smaller
  than 50 files. Eight zero-tolerance tests iterate it and assert nothing
  matches their forbidden pattern, so a scan returning nothing turned all
  eight green while checking nothing — and the realistic trigger, the repo
  root resolving somewhere unexpected, is silent by construction. The real
  corpus is 197 files, so the floor only ever catches a broken scan.
- **The content cap is enforced in one place instead of four.** The
  100,000-character limit lived as hardcoded literals in two driver files
  and nowhere in between: MCP hand-rolled the check twice, the REST routes
  declared it twice via Pydantic, and the use cases had none. So the same
  store rejected a 200KB memory over MCP and HTTP while `oc memory add` and
  `oc memory import` accepted it — not a drift risk, an existing
  inconsistency. `MAX_CONTENT_CHARS` now sits beside `MemoryItem`;
  `add_memory` and `update_memory` enforce it, so every caller inherits it,
  and the drivers reference the constant as fast-fail decoration. Raising or
  lowering the cap is now one edit.

  `oc memory import` deliberately **reports** rather than enforces: a restore
  is not new input, an over-cap row can already exist from before this fix,
  and failing the disaster-recovery path on data the operator already owns
  would be the worse bug. Such rows import intact, are counted as
  `oversized_content`, and are named in a warning. A structural test now
  fails if any surface hardcodes the number again. Found by the first
  phase-end audit. 647 → 658 tests.
- **A blank path env var no longer outranks the default.** `env_vars.md`
  states that an empty-string env var counts as unset *at every config
  boundary*; the path boundary was the one place that didn't honour it.
  `os.environ.get` returns `""` for a blank var, `""` is not `None`, and
  `Path("")` is `Path(".")` — so `OC_DB_PATH=` silently relocated the SQLite
  store to the working directory, and a blank `OC_DATA_DIR` demoted every
  derived path to a bare relative name instead of falling through. Both are
  one `${VAR:-}` line away in a compose file, which is exactly the form the
  fleet convention pushes operator-tunable values toward. Empty and
  whitespace-only now fall through, matching the `is_disabled()` /
  `env_override()` precedent. The value itself is never rewritten — only the
  emptiness test strips — so a path an operator actually meant survives
  verbatim. Constructor params are deliberately not normalized: those are
  code, not operator input. A sweep of every other env read in `src/`
  confirmed no sibling violators. Found by the first phase-end audit.
  637 → 647 tests.
- **`pyproject.toml`'s description drops the semantic-search overclaim**, the
  same correction the GitHub repository description got earlier the same day.
  Semantic retrieval is opt-in, not shipped behaviour: the provider defaults
  to `none` and both compose files pass an empty `OC_EMBEDDING_PROVIDER`, so
  a stock container is keyword-only. Deliberately held back from its own push
  — `pyproject.toml` is not in `paths-ignore`, so shipping it alone would have
  rebuilt the image and bounced the live stack for one docstring. It rode
  along with the maintenance-merge fix instead.
- **`maintenance.jobs` merges onto the defaults instead of replacing them.**
  A `core.json` that named one job silently deleted every other — an
  operator halving the backup interval lost `db_vacuum`,
  `db_integrity_check` and `embedding_backfill` with no warning, because
  `load_jobs` only ever warned about *unknown* job names, never missing
  ones. The latent half was worse: the entrypoint seeds `/config` from
  `core.json.example` with `cp -rn`, and that example enumerates all five
  jobs, so the first release to add a sixth would have found every existing
  deployment quietly ignoring it. An entry now overrides the matching
  default by name and unmentioned jobs keep their defaults, which makes both
  failures impossible. Omitting a job no longer disables it — set
  `"enabled": false`, the way the shipped example already expresses "off"
  for `git_onboard_resync`. Job ordering follows `_DEFAULT_JOBS` rather than
  the file, so the status surface is stable however the JSON is arranged.
  MAINTENANCE.md and config_files.md now state the semantics; neither had.
  No effect on the live deployment, which runs the defaults. Flagged as
  §11.1 of the cloud-backup design and confirmed by the first phase-end
  audit. 632 → 637 tests.
- **The README's Docker badge actually renders now.** It had been showing
  shields.io's "404: badge not found" image on the public README: the literal
  hyphen in `openchronicle-mcp` made shields split the static-badge path as
  label/message/color in the wrong places. Escaped to `openchronicle--mcp`,
  matching the License badge's existing `AGPL--3.0`. Confirmed by fetching
  both URLs: the old one titles "404: badge not found", the new one titles
  "Docker: ghcr.io/carldog/openchronicle-mcp". Found by the first phase-end
  audit.
- **Five docs corrected that were wrong about runtime behavior.** Not
  stale prose — claims a reader would act on and be misled by, the same
  class as the `db_modified_utc` fix and the systemic theme of this window.
  `mcp_client_setup.md` told operators that `OC_MCP_TRANSPORT=stdio` plus
  `oc serve` avoids starting HTTP; `cmd_serve` never reads that variable and
  `create_app` mounts `/mcp` unconditionally, so the result was a bound port
  and a live streamable-HTTP endpoint — the opposite of what was promised.
  `oc serve --help` and `cmd_serve`'s docstring advertised `0.0.0.0:18000`
  when the effective defaults are `127.0.0.1:8000` (18000 is the host-side
  port the NAS compose maps onto 8000, never an application default), and
  `--help` is the surface a user actually reads. `ARCHITECTURE.md` listed
  `BudgetExceededError`, deleted long ago, and two CLI commands that do not
  exist in the argparse tree (`oc project ...`, `oc health`). Every
  correction verified against the code. Found by the first phase-end audit.
- **`OC_LOG_LEVEL` can no longer crash-loop the container.** `oc serve`
  handed the raw value to `uvicorn.Config`, which indexes its own
  `LOG_LEVELS` dict directly — so `OC_LOG_LEVEL=WARN` (the alias every
  other log tool accepts, and one `logging` itself defines) died with a raw
  `KeyError: 'warn'`. Under `restart: unless-stopped` that is an indefinite
  outage caused by one typo'd Portainer value. `uvicorn_log_level()` now
  validates against uvicorn's real table rather than a local copy that could
  drift, maps the `WARN`/`FATAL` aliases, and otherwise logs a warning
  naming the valid set and falls back to the default — the same fail-soft
  `configure_root_logger` already applied to this very variable, and the
  trap `parse_int_env`'s docstring exists to prevent. Found by the first
  phase-end audit; same bug class as the 2026-07-12 embedding fail-soft fix.
- **`memory_search` stops advertising a parameter it does not have.** Its
  MCP tool description told the model to pass `include_pinned=false` to hide
  pins. That switch is CLI-only (`oc memory search --no-include-pinned`); the
  registered MCP schema has no such parameter, so a model following the
  instruction emitted an unsatisfiable call. `mcp_server_spec.md` repeated the
  claim inside a table of MCP parameters. Both now state it is CLI-only and
  point MCP callers at `memory_list(pinned_only=true)`. Introduced 2026-08-23
  alongside the query-aware pinned float; found by the first phase-end audit.
- **Deploy verification no longer points at a checkpoint clock.** The
  agent instructions told operators a recent `db_modified_utc` confirms
  a new container is live. It does not: the store opens
  `PRAGMA journal_mode = WAL`, so writes land in the `-wal` sidecar and
  the main DB's mtime only advances on checkpoint — a memory written at
  14:47Z still read `db_modified_utc` 05:26Z a minute later.
  `health.package_version` is the signal, and the line now says so and
  names the wrong one explicitly so it can't be reintroduced. Caught
  while refreshing a session against the repo, one revision after the
  closeout that swept deploy facts. No code change.
- **Comparative repository-review closeout.** Added source-pinned
  assessments of OpenClaw (`894f254`), Ollama (`f96e7aa`), and NemoClaw
  (`b7261ff`) without importing their runtime scope. Closed the review's
  immediate documentation findings: `AGENTS.md` is canonical and
  byte-identical to the `CLAUDE.md` compatibility mirror, verified by a
  repository-hygiene test; stale CLI/MCP/security/config/deploy/README
  facts are corrected; and `docs/design/README.md` indexes the four
  numbered documents. Replaced nonportable/ineffective compaction hooks
  with one documented post-compaction OC reload. `uv.lock` is now
  tracked for dependency-graph inspection, while CI/Docker frozen
  consumption remains explicitly open. 625 → 626 tests; no runtime-image
  change.
- **The git-onboard watermark no longer leaks across devices via
  export/import.** The watermark is one device's git resume point,
  written as an ordinary memory row (`source="git-onboard-watermark"`,
  now the shared `WATERMARK_SOURCE` constant in `git_onboard.py`).
  Carried to another device it corrupts incremental onboarding — a hash
  unreachable in the destination clone forces a full re-walk and
  duplicate cluster memories, one *ahead* of the destination silently
  skips commits. `export_memory` now excludes it; `import_memory` drops
  it on read in both `merge` and `replace`, since every envelope written
  before the export fix still carries one and those are exactly the
  envelopes a first cross-device restore reads. Each drop is reported as
  `watermark_dropped`, counted apart from `memory_skipped` so it isn't
  mistaken for a collision. Closes §11.3 / §13.5 of the cloud-backup
  design — the last OC-side prerequisite it named. 620 → 625 tests.
- **`oc memory import --mode merge` stops losing edits silently.** The
  semantics are unchanged and deliberate — merge is a union by id, with
  no update branch — but it had two lossy edges invisible in the data: a
  collision keeps the destination's copy and discards the envelope's,
  and an item deleted here since the export gets re-inserted. A caller
  also could not tell "0 added, nothing to do" from "0 added, everything
  collided." Now `export_memory` stamps `exported_at`,
  `import_memory.execute` returns `projects_skipped` / `memory_skipped`
  alongside the added counts, and merge logs one unconditional warning
  naming both edges with the counts plus a second when the envelope's
  `exported_at` predates the destination's newest `updated_at`. The
  staleness check reads `updated_at`, never `created_at` — `onboard_git`
  sets cluster `created_at` from the commit author date, so one
  future-dated commit would make every legitimate envelope read as stale
  forever. No `format_version` bump: old envelopes still import, new ones
  still import into older builds. Flagged as §11.4 of the cloud-backup
  design, which makes cross-device restore a goal and so manufactures the
  trigger. 607 → 620 tests.
- **`JobState.last_success_at`** — a persisted per-job "when did this
  last actually *work*" timestamp. `last_run_at` keeps advancing forever
  on a job that raises every time, so it cannot answer that question;
  `last_success_at` advances only on a run that completed without
  raising and is never cleared by a later failure. Persisted (not
  in-process) because every push to main bounces the container, which
  would otherwise give a job that has been failing for weeks a clean
  surface after each redeploy. Surfaced on
  `/api/v1/maintenance/status`. Prerequisite for the cloud-backup
  staleness alarm.
- **The pinned float is query-aware (fixes an rc8 regression).** A
  pinned memory now leads search results only when it *matches* the
  query, and — the important half — a pin that doesn't win a float slot
  still ranks normally instead of disappearing. rc8's cap alone made
  pins past the cap unreachable by **any** query, because the ranked
  query excluded all pinned rows: pins reached callers only via the
  prepend. Proven live before the fix: an exact-phrase search for a
  pinned memory's own verbatim content returned nothing with
  `pinned_limit=0`, while a gibberish query returned every pin.
  `pinned_limit=0` now means "don't float" (pins still rank);
  `include_pinned=false` is what hides them. New port primitive
  `search_pinned` (the float query) plus `exclude_ids` on
  `search_memory`; the float policy moved from the store up to the
  application layer, so no caller infers which rows floated from their
  position. 589 → 597 tests.

## v3.0.0-rc8 — 2026-08-17

- **Bounded pinned prepend (`pinned_limit`):** `memory_search` caps the
  pinned prepend at the newest 10 pins by default (tunable 0–1000 via
  `pinned_limit` on MCP/REST/CLI; 0 = none). Observed live right after
  the rc7 deploy: a `top_k=2` unscoped search against the 85-pin NAS
  store returned 87 results. Capped-out pins are omitted entirely —
  the exclusion set still covers all pins, so they can't re-enter
  through the keyword or semantic ranking. Enumerate every standing
  rule with `memory_list(pinned_only=true)`. 589 tests.

## v3.0.0-rc7 — 2026-08-17

Review Batch E (docs SSOT + test debt), the post-review polish batch,
the dead-code sweep, the embedding-store port + AST boundary guard,
and the Q20/Q21 search-surface v2; 563 → 582 tests.

- **Search-surface v2 (2026-08-17, Q20/Q21):** `memory_search` (and
  `context_recent` with a query) explains every result. Each hit
  carries a `relevance` object — `channel`
  (`pinned`/`keyword`/`semantic`/`hybrid`), `rrf_score`,
  `semantic_similarity` (unit cosine, the only roughly interpretable
  score), `keyword_rank` — across MCP, REST, and CLI;
  `search_memory.execute` returns `list[ScoredMemory]` from all three
  paths. New `mode` parameter (`hybrid` default / `keyword` /
  `semantic`): keyword never touches the embedding provider; semantic
  requires one — missing provider is a 422 and a provider failure is a
  502 `PROVIDER_ERROR` via a new global handler, never a silent
  keyword fallback. New `phrase` flag matches the whole query as one
  adjacent-token FTS5 phrase (whitespace-normalized substring on the
  non-FTS5 fallback) — the server-side answer to mnemosyne-mcp's
  client-side keyphrase matching. No `min_confidence` threshold
  shipped by design: RRF scores are rank-fusion values, not calibrated
  confidence.

- **Error honesty:** a wrong `project_id` on memory_save answers 404
  "Project not found" instead of a raw FK-constraint 500; malformed
  `created_at` answers 422 with an ISO 8601 hint on both surfaces;
  `memory_get`'s 404 carries the `code` field like its siblings;
  MCP `project_update` with neither field raises the 422-mapped
  validation error instead of a bare store ValueError; Ollama
  connection-refused reports `CONNECTION_ERROR`, not `TIMEOUT`.
- **Parity by construction:** the health payload and the embed outcome
  mapping each live in one shared builder instead of verbatim copies
  per surface.
- **Ops:** `oc memory import` is transactional (a bad row rolls back
  the whole restore instead of half-applying); the rate limiter sweeps
  idle clients' expired windows (slow leak fixed).
- Removed the dead `oc onboard git --no-llm` flag.
- **Dead-code sweep (2026-08-17):** unused error codes +
  `BudgetExceededError` deleted and the canonical-code guard's regex
  hole closed; `oc init --force/--no-templates` (parsed, did nothing)
  and the `plugin_dir` kwarg removed; tests-only helpers deleted;
  `normalize_unit` extracted as the one home of the
  dot-product=cosine invariant; `search_hybrid`'s pagination rule
  deduplicated. Test count 591 → 559 — the delta is deleted tests of
  deleted code.
- **Architecture close-out (2026-08-17):** embedding persistence is
  part of `MemoryStorePort` (the service is typed against the port, not
  concrete SqliteStore), and the hexagonal boundary guard is an AST
  scanner that sees TYPE_CHECKING / function-body / relative imports —
  the hole the old regex guard had — with the two container-token
  exemptions enumerated and self-tests pinning the once-missed shapes.
  Every code-level finding from the 2026-08-15 review is now closed.

- The v2 documentation archive `docs/archive/v2/` actually exists now —
  Phase 7's move had been silently swallowed by a v2-era `.gitignore`
  rule; restored from the `archive/openchronicle.v2` branch.
- The status doc is a current-state snapshot (this CHANGELOG absorbed
  its release narrative); V3_PLAN declares which sections are live;
  CLAUDE.md's sprint holds only in-flight work.
- Test debt: end-to-end CLI smoke pass (the surface was ~80% untested);
  handler tests for the six uncovered MCP tools incl. `memory_embed`'s
  outcome mapping at both surfaces; structural guards (all tools are
  coroutines, `confirm` stays default-free on project deletes,
  unconditional `mcp` import so a failed pin resolve can't silently
  skip the suite); mock containers stopped fabricating v2 attributes.

## v3.0.0-rc6 — 2026-08-16

The 2026-08-15 full-repo review, Batches A-D (~40 findings fixed;
510 → 563 tests). First release where `health.package_version` reports
the real version.

- **Search correctness:** hybrid search honors `include_pinned=False`
  (pinned rows no longer re-enter via the semantic channel); the
  embeddings `dimensions` column records the actual vector length and
  reads unpack by blob length (healing poisoned rows); semantic search
  is scoped to the active embedding model (stale-model rows no longer
  crash the matmul or corrupt ranking cross-space).
- **`context_recent`** with no query now lists recent items instead of
  searching `""` (which returned pinned-only on FTS5 deployments);
  REST search rejects empty queries (422) for MCP parity.
- **`onboard_git` robustness:** watermark anchors the ancestry head
  (`commits[0]`), not max author date; unreachable watermarks
  auto-fall-back to a full walk (memories kept, `watermark_unreachable`
  flagged) instead of a raw git error; new `branch` param with the
  resolved branch + head SHA echoed on every response; CLI and MCP
  share one orchestration (`onboard_git_prepare`) — the CLI now saves a
  watermark and runs incrementally. Breaking:
  `extract_commits_from_url` returns `ExtractedHistory`;
  `run_git_onboard_raw` → `materialize_clusters`.
- **Transport & security:** stateless streamable-HTTP (no
  session-per-abandoned-client leak); Host-header allowlist on the REST
  surface (`OC_API_ALLOWED_HOSTS`, falling back to
  `OC_MCP_ALLOWED_HOSTS`) closing the DNS-rebinding gap `/mcp` was
  already guarded against.
- **Config honesty:** empty env vars fall through to `core.json`
  everywhere (compose `${VAR:-}` injection was silently shadowing file
  config); six previously Portainer-unreachable vars added to compose;
  four remaining crash-loop startup paths fail soft with a warning.
- **Ops:** maintenance job schedule persists across restarts
  (`maintenance_state.json`); backup retention keeps newest-7 ∪
  newest-per-day×7 so same-day bursts can't evict older days;
  Dockerfile dependency layer survives source edits.
- **Release integrity:** Python floor declared `>=3.14` (it already
  was, de facto); version single-source moved to `3.0.0rc6` with a CI
  tag↔version guard; `oc init-config` (a v2 zombie writing config v3
  never read) deleted; README quick starts fixed.

## v3.0.0-rc5 — 2026-07-24

Read-surface + delete-safety batch (433 → 510 tests; 17 → 18 tools),
plus the 2026-07-02 hardening batch. Driven by three dogfooding
memories.

- Required `confirm` on `memory_delete` / `project_delete` (omission
  raises / 422s instead of returning a success-shaped preview).
- Project-scoped `memory_list`; `name_contains` on `project_list`;
  opt-in `compact` projection across the read surface.
- Bounded, honest `onboard_git` cluster detail
  (`max_commits_per_cluster`, `include_commit_detail`, chronological
  presentation, `Showing: n of N`); watermark advances past
  filtered-out HEADs.
- New `project_delete_bulk` (per-item reporting, all-or-nothing
  durability).
- `health` gains `package_version`, `schema_version`,
  `maintenance_degraded`, `fts5_active`; `oc version` fixed (looked up
  the wrong distribution name).
- From 2026-07-02: SQLite connection serialized behind an RLock; all
  MCP tools async with `asyncio.to_thread`; git-onboard multi-line
  body fix + clone-URL transport allowlist.

## v3.0.0-rc4 — 2026-05-11

- Rate-limit default raised 120 → 600 RPM (mnemosyne burst incident).
- Full project CRUD (`project_get`/`project_update`/`project_delete`
  with preview/confirm) across port, use cases, REST, MCP, CLI;
  symmetric `confirm` flag added to `memory_delete`. 17 tools.

## v3.0.0-rc1 / rc2 / rc3 — 2026-05-06

Phase 8 NAS cutover day (turbulent — full account in
[docs/cutover-2026-05-06-triage.md](docs/cutover-2026-05-06-triage.md)).

- rc1: first v3 image live on stack 151; the migrated v2 DB arrived
  corrupt and v3 restarted against a fresh volume (36 v2 memories not
  carried forward; v2 DB preserved on disk).
- rc2: MCP transport fixes — mount path-doubling and the
  `OC_MCP_ALLOWED_HOSTS` Host-header allowlist (421 gotcha).
- rc3: senior-dev review batch — numpy vectorized semantic search
  (~265x), API consistency cleanups, ruff backlog cleared, real MCP
  initialize handshake in the smoke test.

## Pre-release

v3 phases 0-7 (the v2 → v3 slimming: interfaces, application,
infrastructure/domain, migration framework, ASGI unification,
maintenance loop, docs sweep) are chronicled in
[docs/V3_PLAN.md](docs/V3_PLAN.md). The v2 era is frozen at
`archive/openchronicle.v2` and documented in
[docs/archive/v2/](docs/archive/v2/README.md).
