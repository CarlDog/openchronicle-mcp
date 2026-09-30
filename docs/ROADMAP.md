# OpenChronicle development roadmap

**What this is.** The ordered plan for all open work: every idea, feature,
defect, gated item and decision, gathered in one place. It is sequenced into
phases **without dates**, because work happens in bursts.
[CODEBASE_ASSESSMENT.md](CODEBASE_ASSESSMENT.md) remains the source of truth
for *current state*. [V3_PLAN.md](V3_PLAN.md) and the
[design records](design/README.md) hold each item's full detail. This file
holds the order.

**Built:** 2026-09-28, from a full inventory of V3_PLAN, the assessment,
design records 0001-0021, OpenChronicle memories, GitHub issues and PRs,
long-lived branches and code comments. Reconciled at the 2026-09-29 phase-end
audit; the one work marker in the code is the `git_onboard_resync` placeholder
in `jobs.py`.
**Operator priorities:**

- persistent storage and production health first (Phases 1 and 2, done
  2026-09-28/29 apart from OPS-07, OPS-08's close-out and DATA-01's decision 5);
- accuracy first, then speed and responsiveness (2026-09-08).

## How to read and maintain it

- **Stable IDs.** Cite items by the IDs below (for example `OPS-03`), never by
  a position number. V3_PLAN's active-queue numbers shift whenever an entry
  is inserted; on 2026-09-24 one insertion broke about a dozen references.
- **Sizes:**
  - S: hours;
  - M: one to three days;
  - L: a week or more;
  - XL: multi-week.
- **Phases are an order, not a schedule.** Phase 0 can run alongside
  anything. A later phase can start early when its items are unblocked and the
  earlier phase is waiting on the operator.
- **Gates still apply.** Being listed here does not authorize an item. Gated,
  parked and research items need their named trigger or the operator's
  ratification, per the agent rules in AGENTS.md.
- **Upkeep.** When an item finishes, mark it done here in the same commit as
  the work. Every phase-end audit reconciles this file against all sources
  (see the AGENTS.md checklist).

## Phase 0 — Records and hygiene (small; any time, alongside other work)

| ID | Item | Size | Detail |
|---|---|---|---|
| HYG-01 | Close issue #27: all four findings shipped in the v3.4.0 tag, with CI green on the exact commit | S | **Done 2026-09-29:** closed #27 with an evidence comment naming each fix commit (`02f83d67`, `46c88ffc`, `eb23c7f4`, `0d292b79`, plus the review fixes in `93d68560`), each an ancestor of the v3.4.0 tag; assessment revs 201-204 and 233 |
| HYG-02 | Standards gaps in issue #17: tick UNI-05 (done in rev 200); add `.editorconfig` (UNI-06); add a `Last updated:` line to `STATUS.md` (UNI-08); add the `Fleet standards:` stamp (UNI-09); create GitHub Releases for the tags that lack one (every `v*` tag except v3.3.0, including v3.4.0 to v3.6.0; GitHub shows v3.3.0 as Latest while v3.6.0 runs in production) (UNI-19) | S | #17. **Done 2026-09-29:** `.editorconfig` copied verbatim from the fleet template; a `Last updated:` line on the `STATUS.md` pointer (it dates the pointer, not the assessment); the stamp in AGENTS.md and CLAUDE.md, naming the one open gap; GitHub Releases for all 14 tags that lacked one (notes from the CHANGELOG, release candidates marked pre-release), v3.6.0 now Latest. The audit against catalogue 3.0 leaves PY-04 red: it wants a group named `pip-dev`, but this repo moved to the `uv` ecosystem on purpose and its `uv-dev` group is auto-merge eligible under UNI-07. The check needs the fix, not the repo (fleet-kit, below). Six tags (`v3.0.0-rc2`, `rc7`, `rc8`, `v3.2.0`, `v3.3.0`, `v3.4.0`) are lightweight, where UNI-19 asks for annotated tags; not rewritten |
| HYG-03 | OpenChronicle memory cleanup (needs the API key now): a stale pinned "current state" memory (claims v3.1.0 live) floats into every search; a junk memory with content "test"; eight milestone-tagged memories describe the deleted Gemini branch; an obsolete v3.4.0 changelog draft; resolved `mcp-feedback` notes still open; portainer-mcp notes filed under this project | S | 2026-09-28 inventory. **Done 2026-09-29:** the current-state memory was rewritten to v3.6.0 as a dated pointer and unpinned; a pinned v3.6.0 release milestone was added; the "test" memory and the v3.4.0 changelog draft (the CHANGELOG has the real entry) were deleted; the eight Gemini-branch memories lost the `milestone` tag and gained `not-merged` and `gemini-branch` (each already opens with a NOT MERGED line); five `mcp-feedback` notes were tagged `resolved`, two with a resolution paragraph; the two portainer-mcp notes were re-saved under that project with their original dates and deleted here |
| HYG-04 | Delete stale branches and worktrees: `origin/v3/develop` (0 ahead of `main`, 290 behind); the `vigilant-mendel` worktree (on `c7f36a7c`) | S | **Done 2026-09-29:** deleted `origin/v3/develop` (0 ahead) and the remote `claude/ops-08-cloud-backup` (its one commit is in `main` as `fb0fea3f`); removed the `vigilant-mendel` worktree and two review worktrees, all clean; deleted 27 local branches, each checked to have no commit missing from `main`. Kept `main`, `v4/develop`, `archive/*` and the branches of open PRs #38, #45 and #46 |
| HYG-05 | Review and merge Dependabot PRs #45 and #46 on fresh CI | S | **Done 2026-09-30:** openai 3.16.2 → 3.19.2, ruff 0.16.8 → 0.16.9 and uvicorn 0.52.4 → 0.54.0, re-landed as one PR with Dependabot's exact `uv.lock` changes (see HYG-09 for why), `uv lock --check` clean. Release notes read: uvicorn 0.53-0.54 add only opt-in HTTP/2 and loop choices (the one default change trusts `::1` as a proxy, which the container never sees); openai 3.17-3.19 add API surface and fixes, and production embeds through Ollama |
| HYG-09 | **Dependabot PRs can never merge under `main`'s protection.** CodeQL default setup does not run on Dependabot branches (none of #45's four heads had a run; code scanning reports "2 configurations not found"), but `Analyze (python)` and `Analyze (actions)` are required checks, so every Dependabot PR sits BLOCKED. Options: move CodeQL to an advanced-setup workflow that runs on every PR, or accept re-landing Dependabot changes by hand as HYG-05 did. Operator decision; it touches branch protection | S | Found 2026-09-30 while doing HYG-05. The same gap blocks UNI-07's Dependabot auto-merge. **Decided 2026-09-30 (operator): keep default setup for now.** Dependabot changes are re-landed by hand as HYG-05 did, on a branch whose PR gets the CodeQL checks. The alternative is prepared but unpushed: a CodeQL workflow (commit `512d634f`, local branch `claude/hyg-09-codeql-workflow`; its full text is in OpenChronicle). Pushing it needs a token with the `workflow` scope, and default setup must be disabled first, because GitHub rejects a workflow's uploads while it is on. Revisit when the operator can do both |
| HYG-06 | Design-record status corrections still open: the 0002, 0003 and 0004 headers (0004's shipped ranks 2, 4, 5, 8 and 10, and rank 11's claim that CI never starts the image it publishes, fixed by the image smoke in rev 207); 0016's track-3 checkpoint still says "unmerged branch" | S | The design index and the 0001, 0016 and 0020 headers were corrected in the 2026-09-29 phase-end audit. **Done 2026-09-30:** the 0002, 0003 and 0004 headers and the index state what shipped; 0004's ranking table marks ranks 3, 7 and 11 done and points rank 9 at QUAL-06; 0016's checkpoint names its merge |
| HYG-08 | UNI-08 wants the status document itself at the root `STATUS.md`; here the root file points at `docs/CODEBASE_ASSESSMENT.md` | S | Deferred 2026-09-29: moving it relinks CLAUDE.md, AGENTS.md, the hygiene tests and every link to the assessment, which is a rewrite rather than an audit fix. The pointer passes the machine check honestly. Take it on only as its own change |
| HYG-07 | Decide whether to enforce "work lands through a PR" with branch protection on `main` (revs 201-211 were direct pushes) | S | **Done 2026-09-28 (operator decision):** classic branch protection on `main` requires a PR (0 approvals) and these checks: `ubuntu-latest`, `windows-latest`, `lint + format + types`, `Scan for secrets`, `Analyze (python)`, `Analyze (actions)`, and since 2026-09-28 (OPS-08) `Image smoke test`, the PR-only job that builds the image and runs both smoke scripts; it has no path filter, so it reports on every PR to `main`. The branch must be up to date (`strict`). It is enforced for admins too, so the operator's token, which agents use, cannot push directly. Force pushes and deletion are blocked. The same was applied to portainer-mcp. Emergency path: switch protection off briefly in Settings |

## Phase 1 — Persistent storage and data safety

| ID | Item | Size | Detail |
|---|---|---|---|
| DATA-01 | **Persistent-storage architecture review.** Covers: the volume is keyed to the compose project name; automatic backups share the data volume; the live log path is wrong; everything sits on one NAS; the `docker` share grants `Everyone` read; `/config` is mode 0777; whether `assets`, `output`, `plugins` and `oc-output` are still needed. Output: a reviewed target layout plus a cutover and rollback plan | M | V3_PLAN "Persistent-storage review". The premise was checked on 2026-09-24: the database has persisted since the 2026-05-06 cutover, and it survived the 2026-09-25 recreate (1,088 memories). **Review written 2026-09-28:** [0020](design/0020-persistent-storage-review.md), decisions 1-4 adopted as recommended on 2026-09-28 and step A (the log path, environment only) applied the same day. Step B deployed with OPS-03 the same day. Open: decision 5 for the share root (the `exports/` half was settled in rev 249) |
| DATA-02 | Cloud-backup Phase 0: Dropbox App Folder probe, two age keypairs with independent escrow, a two-identity decrypt drill. Answers the "one NAS" risk | S | **Done 2026-09-28** ([0001 Phase 0 record](design/0001-cloud-backup.md#phase-0-record-2026-09-28)): App folder verified, both identities decrypted the uploaded artifact to `integrity_check` `ok` and 99%/100% row counts. The one-NAS risk stays open until OPS-08 closes (nightly pushes since 2026-09-29) |
| DATA-03 | Dropbox retention decision: keep the account as the backup target; how much of the existing 6.75 GB to keep | S | 0001 §13 Q7. Decision |
| DATA-04 | Check that the restore path has a post-swap writeability probe (`BEGIN IMMEDIATE`); add it if missing | S | 0004 F8 step 5. **Done 2026-09-30:** it was missing (every post-restore check only read). `scripts/offline_restore.py` now probes after the swap in `activate` and `rollback`, records `write_probe` in `state.json`, and stops with the next step when it fails. `BEGIN IMMEDIATE` alone proved nothing (SQLite grants it on a read-only file), so the probe makes a change and rolls it back. After review: a `probe` action re-checks after a fix; `write_probe` reads `pending` from before each swap until probed; a held lock gets its own advice; an unwritable file is refused before SQLite opens it (whose read-only sidecars would outlast a fix); and the helper refuses root in `activate`, `rollback` and `probe` themselves |
| DATA-05 | Delete the NAS copy of the v2 pre-migration backup (`openchronicle.db.v2-rollback`, 24 of the 36 memories lost at the v3 cutover). Keep the laptop copy (`~/backups/pre-v3-cutover.db`, all 36): it is the only full recovery path for those memories, and their recovery was deliberately deferred (cutover triage item L3, OC memory `90ea9e73`). Delete it only after running L3 or deciding to abandon it | S | V3_PLAN Phase 9 Day 7; operator decision 2026-09-29 (phase-end audit). After DATA-01's inventory |
| DATA-06 | Remove the dead host directories `/volume1/docker/openchronicle/{assets,output,plugins,config}`, including the leftover database copies and `.tmp-wal`/`.tmp-shm` files in `config/` (assessment rev 230) | S | 0020 step 7. After a week of green nights from 2026-09-28, so from about 2026-10-05; operator-run with DATA-07 |
| DATA-07 | Clean up the frozen pre-v3.5.0 snapshots in `/data/backups/auto`, which the catalog never prunes | S | Assessment rev 250. Same operator session as DATA-06; keep them until an off-NAS copy of a current snapshot exists (OPS-08 provides it) |

## Phase 2 — Production health

| ID | Item | Size | Detail |
|---|---|---|---|
| OPS-01 | **Deploy v3.4.0** (env-only: move `OC_TAG`; `OC_LOG_FILE=/output/logs/openchronicle.log` is already set, as 0020 step A, 2026-09-28). Read back `package_version` and `build_revision`; check REST and MCP (with the key) and embedding status; have a tested rollback. Also retires 0014's interim restart control | S | V3_PLAN "v3.4.0 correctness release" and "Stack 151's detached compose"; CHANGELOG v3.4.0 deploy note. **Done 2026-09-28** (assessment revs 245-246): 3.4.0 / `9b1e83e6` live, revision `known`, reconcile generated 0, access checks pass. The rollback was drilled live, operator-approved: `OC_TAG=v3.3.0` came up on v3.4.0-written data (1,098 memories, `stale` 0), then back to v3.4.0 (revision `known`, reconcile "0 candidates") |
| OPS-02 | NAS restart gate for ADR 0005 §7 in both start orders: revision known within 60 s, `stale` and `space_mismatch` at 0 | S | 0005 §7; 0014 must-run 5. **Done 2026-09-28** (assessment rev 248). Order A (Ollama stopped, OC restarted, then Ollama started): OC booted `degraded` with the revision `unknown` and `stale` 0, and wrote nothing; Ollama's container started at 20:08:30.2 and OC verified the revision at 20:08:52.3, about 22 s later (the unknown-state re-probe interval is 30 s, so the worst case is about 30 s plus the probe). Order B (Ollama restarted and answering, then OC restarted): the new OC process started at 20:09:38.9 and verified the revision at 20:09:40.7, 70 ms after startup completed. Both reconciles found "0 candidates, nothing to do". Final: `stale` 0, `space_mismatch` 0, `missing` 0, `maintenance_degraded` false, and no manual restart was needed. Timings come from the NAS container and OC log timestamps, not the desktop monitor, whose first samples raced the restart |
| OPS-03 | **Reconcile stack 151's detached compose** (or re-attach it to Git). Covers: the `oc-observability` network against the bridge rule; the Host-list fix (PR #35); the `OC_LOG_FILE` default; the `/exports` bind mount; the hardcoded `OC_BACKUP_DIR`; `container_name: openchronicle-mcp`; an explicit API allowlist if metrics are ever enabled | M | V3_PLAN "Stack 151's detached compose"; 0016 track 3. Uses DATA-01's target layout. **Done 2026-09-28: merged (PR #50, `5a207070`) and deployed to stack 151** (file version 143, then `HOST_CONFIG_DIR` removed; 0020 step B, all checks passed). Operator decisions: the shared bridge for both services, with the collector scraping `host.docker.internal:18000`; stay file-based; drop the unreviewed Watchtower label; OPS-03 before OPS-01, on v3.3.0. `tests/test_nas_compose_shape.py` pins the external data volume, names, bridge, `/exports` and `container_name` (12/12 mutants caught); a three-dimension pre-deploy review found no data-safety or access regression, and its findings are fixed |
| OPS-04 | Next release, carrying 0017's nightly-backup change (catalogued, verified, quarantined) and the 0016 track-1 search fix, with its own deploy check and a design 0010 change-impact review | M | V3_PLAN 0017 entry 1; 0016 §5. **Done 2026-09-28** (assessment rev 251): v3.5.0 tagged on `d1c8be25` after its tag CI passed, and deployed (`package_version` 3.5.0, `backup_last_run_failed` false). Built as a release PR for v3.5.0 (0017 only; the 0016 track-1 search fix already shipped in v3.4.0). 0010 exception extended; decision 5 settled for `exports` (the operator is the only DSM user, so `1000:100 0750` is operator-only). The merge-integration review found no merge defect; its finding 1 (backup failures invisible in health) is fixed in the release, and finding 2 is QUAL-12 |
| OPS-05 | Deploy the `/exports` mount. Needs: a host directory owned by uid 1000 and restricted ACLs. Check: read a snapshot through the share, compare it with the off-NAS digest, run disposable restore checks, and measure request-tail impact | M | 0017 steps 4-5. After OPS-03 and OPS-04. **Done 2026-09-28** (rev 251): the mount deployed with OPS-03; the step-5 check ran on v3.5.0. Five catalogued snapshots were taken with `oc maintenance run-once db_backup` in the container console at 23:57:47-23:58:33Z: each is a 10,014,720-byte `.db` plus `.json` manifest pair in `/exports/backups/auto`, with `backups/` at `oc:users 0750` (filesystem-mcp is refused `EACCES`). The newest, read over SMB by the operator's account, has the manifest's SHA-256 (`7ebac5a1...20fe7f6`) on the share and in the off-NAS copy. A disposable restore was a standalone rollback-journal database: `integrity_check` ok, 0 FK violations, schema 4, 1,100 memories, 39 projects and 1,100 embedding rows (1,079 ok, 21 `content_too_long`), all matching the manifest; the project fingerprint recomputes; four memories saved that day are present; FTS search hits and the FTS5 integrity check passes; a write transaction works. Request tail during the snapshots, measured from the operator's desktop on `/api/v1/health` (the keyword search needs the key and was not scripted): 1,884 requests, 0 failures, idle p95 66.4 ms, during p95 68.9 ms (ratio 1.04, budget 2x and under 500 ms): PASS, also with the windows widened to +10 s. Two tail outliers (1.0 s and 3.0 s) fall in the first snapshot's window only; `run-once` starts a second, cold Python process, which the in-process nightly job does not. An idle capture before the run also had one unexplained 7 s outlier with no backup running. The verified copy is kept at `D:\Backups\openchronicle\step5-20260928\` |
| OPS-06 | Client migration after the auth change: every MCP client (Claude Code on each machine, and any other client) sends the bearer key; inventory non-Claude clients | S | Auth enabled 2026-09-25; 0014 F13 exposure. **Done 2026-09-28** (assessment rev 252). Second workstation: the operator configured Claude Code, Claude Desktop (through `mcp-remote`), Codex, Gemini CLI, Antigravity, VS Code and Visual Studio, and all seven passed `health`. Primary workstation, inventoried by inspecting each client's config file with key values redacted: Claude Code, Claude Desktop (`mcp-remote`), Codex (`http_headers`), Antigravity and VS Code (`mcp.json`) each carry an OpenChronicle entry with an authorization header; Gemini CLI and Visual Studio have no OpenChronicle entry. Of those five, only Claude Code was exercised live there; the other four were checked by configuration, not by a `health` call. The per-client recipes are in `mcp_client_setup.md` |
| OPS-07 | Decide whether to enable the MCP backup tools. Auth is on and production sets `OC_BACKUP_DIR` (since v3.5.0), so only the operator's call remains. Part of the call: whether to wait for PAR-01, whose scoped tokens would let the tools run under a key that cannot delete | S | 0017; decision |
| OPS-08 | Cloud-backup Phase 1: an rclone plus age job in the image, three health fields, compose lines and tests. Done when three green NAS nights pass plus a decrypt check | M | 0001 Phase 1. **Deployed 2026-09-29 in v3.6.0** (`99bd68cb`): the boot-time run pushed three snapshots and health reads `ok`. Plan reviewed (0001 amendments A1-A9); merged in PR #59 after a diff review; implemented with the `cloud_backup` job, `cloud_backup_status` in health (one field; `misconfigured` derived, not a third), rclone and age in the image, and a PR image-smoke job. The escrow decrypt of a daemon-pushed artifact passed 2026-09-29 (0001 Phase 1 record). Done still needs three green NAS nights, a deliberate-breakage check after them, and design 0010's request-latency sample during one nightly run (missed at deploy, rev 257) |

## Phase 3 — Timestamp ordering fix (draft PR #38)

| ID | Item | Size | Detail |
|---|---|---|---|
| TS-01 | Inspect the verified off-NAS copy's raw `created_at` values for naive or malformed timestamps | S | V3_PLAN "Chronological order ignores `created_at` offsets". **Done 2026-09-29:** read-only (`mode=ro&immutable=1`) against the step-5 copy, whose SHA-256, size and counts match its manifest and which passes `quick_check`. Across every timestamp column (5 columns in 4 tables) there are **no naive and no malformed values**. `memory_items.created_at`: 1,006 UTC (996 with microseconds, 10 without) and 94 with an offset (91 at -05:00, 3 at -06:00), all saved through MCP. Text order has 24 adjacent instant inversions, every one an offset row followed by a UTC row, and sorting by instant moves 175 of 1,100 rows. Counts only; no value was printed |
| TS-02 | Decide the policy for naive legacy rows, and whether rejecting naive input counts as MINOR or MAJOR under STABILITY.md | S | 0016 track 2; decision. **Decided 2026-09-30 (operator):** new input without a time zone is rejected with an error naming the field, as a MINOR change under a narrow STABILITY.md exception (the old behavior stored an ambiguous instant, the v3.4.0 blank-content reasoning). Legacy rows need no policy: TS-01 found none, and migration 005 still stops if one appears. The clause lands with PR #38 (TS-04) |
| TS-03 | Pre-migration gate: a fresh off-NAS copy, plus an old/new image-pair rehearsal. Also close the drill's coverage gaps: restoring the restart policy, Portainer freeze and recreation, the production host-source `stage` block, and the failure paths | M | 0017 steps 6-7; runbook "What that drill did not cover" |
| TS-04 | Rebase PR #38 (91 commits behind `main` on 2026-09-29; docs conflicts only as of 2026-09-24), then fresh CI, review, release, and a deploy with the rehearsed rollback | M | After TS-01 to TS-03 |

## Phase 4 — v4.0.0

| ID | Item | Size | Detail |
|---|---|---|---|
| V4-01 | Merge `main` into `v4/develop` (6 ahead and 133 behind on 2026-09-29; conflicts in `embedding_service.py`, `sqlite_store.py`, `cli/commands/memory.py`, the CHANGELOG and the assessment); run the v4 tests | L | Overdue under the "merge regularly" convention |
| V4-02 | v4.0.0 tag decision and release (ADR 0008 pins as ranking prior, `PIN_RANK_LIFT = 0`; MAJOR) | S | V3_PLAN "Pins as ranking prior"; decision |
| V4-03 | Sweep-harness hardening minors: the channel-integrity assertion, run-identity metadata, the `--sweep`/`--out` collision, and noise labels in verdicts | S | V3_PLAN "Pins as ranking prior" residual |

## Phase 5 — Correctness and code quality

| ID | Item | Size | Detail |
|---|---|---|---|
| QUAL-01 | **CLI contract gaps**, confirmed in code 2026-09-24: a blank project name is accepted; `--limit` and `--offset` are unvalidated; `show-project --json` prints plain text when the project is not found; no handler-level error guard (so `export --out <dir>` tracebacks); exporting an unknown project exits 0 with an empty envelope | M | Found in OC memory, not in any repo doc until now |
| QUAL-02 | Rev-209 deferred minors: push exactly the smoke-tested image, or pin the base digest; sort OpenAI `data` by index; `LC_ALL=C` for git children; redact `OLLAMA_HOST` userinfo in the TLS warning; a stop flag between backfill chunks | S-M | V3_PLAN "v3.4.0 correctness release" |
| QUAL-03 | Consolidate the three snapshot-inspection implementations (`BackupCatalog._inspect`, `offline_restore._inspect` and `_describe`) into one leaf module, with the helpers they duplicate: `_sha256`, `_fsync_dir`, the project fingerprint (four copies, including `BackupCatalog._current_identity`, which sorts in Python where the others sort in SQL), and one TypedDict for the inspection result. The free-space margins differ (1 MiB and 16 MiB); pick one deliberately | M | V3_PLAN 0017 deferred item; 2026-09-29 phase-end audit (the catalog copy already returns `size_bytes`, the offline copy does not) |
| QUAL-04 | `set_pinned` does not bump `updated_at`, and `projects` has no `updated_at` | S | 0001 §11.5 |
| QUAL-05 | Docs-parity gates: the CLI argparse tree, the MCP tool inventory, and `OC_*` env vars against the docs | M | 0004 F5; V3_PLAN "Docs parity gates". **Done 2026-09-29:** `tests/test_docs_parity.py` checks both directions for all three: every runnable command has its own `oc` heading in the CLI reference and every long option appears in its section; the registered default and gated MCP tools equal the spec's tables and its stated count; every `OC_*` literal in the source is in `env_vars.md`, and every name documented there or in `.env.example` is read. 11 deliberate breaks, all caught. It found five undocumented `--json` flags and the undocumented `OC_BUILD_REVISION_FILE`, now documented |
| QUAL-06 | Consume `uv.lock` in CI and Docker (`--locked`, pinned uv), audit the locked dependency graph, and drop unused dependencies | M | 0004 F6; V3_PLAN follow-ups |
| QUAL-07 | `_cosine_similarity` has no production caller | S | V3_PLAN follow-up |
| QUAL-08 | Persistent Ollama HTTP client, with NAS p50/p95/p99 evidence at 1 and 8 clients, cold and warm, across an Ollama restart | M | V3_PLAN "Persistent Ollama HTTP client"; 0014 salvage |
| QUAL-09 | MCP tool ergonomics from dogfooding: `memory_save` and `memory_update` echo the full content back; `memory_update` has no append or targeted edit; triage the reported "expected nonoptional" optional-parameter error (not reproduced) | M | OC `mcp-feedback` memories |
| QUAL-10 | Cache-friendly tool surfaces: keep tool descriptions and server instructions byte-stable and in a stable order, enforced by a test | S | 0019 lever 5; 0015 §1 |
| QUAL-11 | **MCP tools silently ignore unknown arguments.** `memory_search` counts with `top_k`, while its sibling `memory_list` uses `limit`. A caller who passes `limit` gets the default of 8, with no error: on 2026-09-28 `limit: 3` and `limit: 5` each returned 8 results (about 10 KB), and the 2026-08-16 "limit=3 returned 34" report is probably the same trap. Fix: reject unknown arguments on every tool, with INVALID_ARGUMENT naming the field and the valid one; optionally also accept `limit` as a `top_k` alias (MINOR under STABILITY.md). Test that a misspelled optional parameter is refused on all 18 tools | S-M | OC `mcp-feedback` memory `2a637611` (updated 2026-09-28) |
| QUAL-12 | **Boot-time `OC_BACKUP_DIR` errors miss the log file and can name the wrong cause** (v3.5.0 pre-deploy review, finding 2). `CoreContainer()` runs before `configure_root_logger()`, so the error goes to bare stderr, which a Portainer recreate discards, instead of `OC_LOG_FILE`. When the real cause is EACCES on a parent, `is_dir()` is False and the message says "must be an existing directory, not a symlink". The 2026-09-30 release review found a second case: an unrecognized `OC_SEARCH_FTS5_ENABLED` warning (added by audit C3) reaches bare stderr but not `OC_LOG_FILE`. Fix: configure logging before building the container, or re-emit the problem after logger setup; report permission errors separately. It touches every command's boot path, so it was kept out of the release | S | OPS-04 review. **Done 2026-09-30:** `oc serve` configures logging before it builds the container, so both boot problems reach `OC_LOG_FILE`; one-shot commands are unchanged. The backup-directory check uses `lstat`, so a parent that uid 1000 cannot traverse is reported as a permission problem, apart from a missing path, a file, or a symlink |
| QUAL-13 | One owner for backup-snapshot naming and the "published" rule. The stamp format, artifact-id reconstruction and "published" predicate live in both `backup_catalog.py` and `jobs.py`, and the job's "published" (a manifest file exists) is weaker than the catalog's (the manifest parses and its id matches). `BackupCatalog` should list the published auto snapshots as (stamp, path, artifact id) for retention and `cloud_backup` to share. Also one "N newest plus the newest per UTC day" helper: retention keys on file mtime, the cloud push on the filename stamp, so the two can disagree for a restored or copied file; moving retention to the stamp is a behaviour change to call out | M | 2026-09-29 phase-end audit, refactor scan findings 4 and 5 |
| QUAL-14 | Typed shapes that have settled: `cloud_backup_status` (a TypedDict with a `Literal` status), `_last_background_backfill`, and a `JobResult` for maintenance handler results (read today by duck typing on `skipped`/`failed`). In tests, one parameterized always-raising embedding port for the five near-identical fakes in four files | S-M | 2026-09-29 phase-end audit, refactor scan findings 9 and 10 |
| QUAL-15 | `embedding_service.py` grew from 758 to 1,117 lines in one phase and now holds background-backfill and refresher lifecycle, generation and backfill, and search. Record a size decision in ARCHITECTURE.md, or plan a split with the lifecycle first; not during an audit | S decision, M split | 2026-09-29 phase-end audit, refactor scan finding 6 |
| QUAL-16 | Close the stores that test fixtures open (about 245 unclosed SQLite connections per run, across about 25 test files, hidden because `ResourceWarning` is ignored by default), then make `ResourceWarning` an error in the pytest config so a new leak fails CI | M | 2026-09-29 phase-end audit item C7 (assessment rev 266), which fixed the production entry points. Rev 274 closed one more leak of this kind: a cancelled cloud-backup child's pipe transports, which leaked only when the loop closed at once, as in tests |
| QUAL-17 | Compose parity gate: every `OC_*` setting the source reads is wired into `docker-compose.nas.yml` as a `${VAR:-default}` line, and every `OC_*` name in the compose file is read by the source, with a short allowlist whose entries each carry a reason. Catches a setting that is implemented and documented but unreachable from Portainer (fleet docker rule 10). Known allowlist today: `OC_TAG` (compose-only image tag); `OC_MCP_HOST`, `OC_MCP_PORT` and `OC_MCP_TRANSPORT` (the stdio entry point only, not the served stack); `OC_DATA_DIR` (the entrypoint derives paths from it; the compose sets them directly); `OC_BUILD_REVISION_FILE` (a test override) | S | Follows QUAL-05; operator request 2026-09-29. **Done 2026-09-29:** three checks in `tests/test_docs_parity.py` (every setting the source reads is in the `oc` environment; every compose `OC_*` name is read; every value is `${SAME_NAME...}` apart from six container-wiring entries), each allowlist entry with its reason. The compose had no gaps; six deliberate breaks were all caught |

## Phase 6 — Measurement foundations

These produce the numbers that phases 7 and 8, and several gated items, wait
on.

| ID | Item | Size | Detail |
|---|---|---|---|
| MEAS-01 | Design 0010 disposition. Needs a new scoped decision first; then a quiet NAS window with interference attribution; a frozen acceptance run (C/A overhead, REST list p99, MCP list p99 with at least 1,000 samples); and the affected 4D checks. Also decide which layer owns "metrics must never break OC": the recorder's `_safe` guard (which counts what it absorbs in `recorder_errors`) or the 11 outer try/except wrappers (which log without counting); the 2026-09-29 phase-end audit recommends the recorder, keeping outer wrappers only where building a metric's arguments can raise, under this design's impact review. Also explain, or drop with a reason, the one unexplained 7 s request seen in an idle capture during v3.5.0's step-5 check (assessment rev 251). (Stack 216 was deleted and its history volume pruned on 2026-09-28.) | M-L | 0010 4C final disposition; the attribution record |
| MEAS-02 | Concurrency probe: reconcile V3_PLAN "Concurrency load probe" (the probe already exists as `scripts/probe_performance.py`), then measure store-lock contention at realistic fleet N | S-M | 0007 Stage 0 |
| MEAS-03 | OC-FT-01: measure duplicate query-embedding rate and the embedding share of latency | M | 0012 |
| MEAS-04 | Public, reproducible memory-quality evaluation on a sanitized corpus | M | 0011 H1 |
| MEAS-05 | Which clients (Claude Code, Codex, Gemini CLI and others) expose per-request token, time and cost counts | S | 0018 and 0019 research |

## Phase 7 — Prompts and LLM cost (the north star)

| ID | Item | Size | Detail |
|---|---|---|---|
| LLM-01 | Research pass. For 0019: memory and context layers against token use, gateway tools, and FreeToken re-read for generation cost. For 0018: DSPy and GEPA, TextGrad and OPRO; Langfuse and PromptLayer outcome-to-version linkage; comparing versions at small N | M | 0018, 0019 |
| LLM-02 | Provider SDK integration survey: Copilot SDK, OpenAI Agents SDK, Claude Agent SDK, Google Gen AI, Groq and Ollama SDKs. Define the setup path, auth, lifecycle, isolation, terms, and a provider-neutral abstraction while keeping OC's memory-service boundary | M | V3_PLAN "Provider SDK integration survey" (added 2026-09-24) |
| LLM-03 | Prompt-library Stage 0 pilot, with 0018's revision (track outcomes, attempts and savings). Choose isolation first. Operator-run and zero code, so it **can start any time** | S | 0015 §6; 0016 track 4; 0018; V3_PLAN "Prompt library Stage 0" |
| LLM-04 | Decisions before Stage 1: 0015 §7 Q1-Q5, Q7 and Q8, and 0018's architectural fork (agents propose edits, or OC runs an improver model) | S | Decisions |
| LLM-05 | Prompt-library Stage 1 build: Option B with the outcome log in the first stage, after a ratified ADR and a plan review | L | Gated on LLM-03's exit and LLM-04 |
| LLM-06 | Cost levers in order: a baseline of fleet spend per task (lever 1); memory instead of rediscovery (lever 2); result reuse (lever 6); a scope decision on a request-path gateway (lever 7, outside OC) | L-XL | 0019. After MEAS-05 |

## Phase 8 — Retrieval quality and memory features

Proposals from the comparative reviews. Each waits on MEAS-04's evaluation so
that any change can be shown not to hurt accuracy.

| ID | Item | Size | Detail |
|---|---|---|---|
| RET-01 | Context retrieval within an explicit budget: a tokenizer contract and visible truncation | M | 0011 H4; 0019 lever 3 |
| RET-02 | A read-only hygiene report for stale pins, duplicates and multiple current-state memories | M | 0002 F4 |
| RET-03 | Operation-identity ADR and an integer revision counter, then supersession and source-linked history | L | 0011 H2-H3; 0004 F7 |
| RET-04 | A small human-facing memory inspector | L | 0011 H5 |
| RET-05 | A score-aware fusion ADR for the hybrid R@1 deficit (RRF dilutes semantic top-1) | ? | 0008 out-of-scope note; 0006 Finding 4 |
| RET-06 | Benchmark MMR and other channels offline, without changing defaults | M | 0002 F5 |

## Phase 9 — Parity and beyond (#memory, design 0021)

The operator's aspiration (2026-09-28): do everything #memory (usememory.com) does, and better. Each item needs ratification first; none is scheduled. RET-04 covers their human interface. Suggested order: PAR-07 and PAR-01 first (small, and PAR-01 makes enabling OPS-07's tools safer), PAR-06 after MEAS-04, PAR-02 after RET-03's ADR, PAR-03 as its own design; PAR-04 and PAR-05 stay research.

| ID | Item | Size | Detail |
|---|---|---|---|
| PAR-01 | Scoped credentials: per-client tokens with `read`/`write`/`delete` scopes and a project or tag restriction, revocable one at a time; later OAuth 2.1 with PKCE and dynamic client registration | M, then L | 0021 gap 1. Would let the backup tools (OPS-07) and deletes run under a key that cannot delete |
| PAR-02 | Integration sync: idempotent upsert by an external reference with a source-timestamp staleness guard, `updated_since` cursor polling, and a deletion feed (their stated gap) | M | 0021 gap 2. After RET-03's operation-identity ADR |
| PAR-03 | Attachments: a blob store beside memories, extracted text and local-model captions joining hybrid search, with backup, export and offsite coverage | XL | 0021 gap 3. Its own design and plan review |
| PAR-04 | Per-project encryption at rest with an operator-held key, keeping search for unlocked projects | ? | 0021 gap 5. Research first; the self-hosted threat model differs from theirs |
| PAR-05 | Read-only, revocable sharing | ? | 0021 gap 6. Only if OC gains a second person; record, don't build |
| PAR-06 | Weigh tag matches above body text in the keyword channel (`bm25()` column weights) | S | 0021 gap 7. Gated on MEAS-04's evaluation |
| PAR-07 | Write down and test the telemetry boundary: metrics and logs never carry memory content, search text or tags | S | 0021 gap 8. `security_posture.md` plus a test over the metric label sets |

## Gated register (no phase until the trigger fires)

| ID | Item | Trigger |
|---|---|---|
| GATE-01 | 0007 Stage 1: read pool, chunked import writes, async adapters | Store-lock contention at realistic fleet N (MEAS-02) |
| GATE-02 | 0007 Stage 2: Postgres plus pgvector (supersedes the sqlite-vec ceiling) | About 10x corpus with semantic latency degradation, or sustained multi-writer contention |
| GATE-03 | 0007 Stage 3: a replicated app tier | An availability requirement beyond one host |
| GATE-04 | mcp 2.x migration, which carries the MCP `error_code` gap, the handshake version, `CONTENT_TOO_LONG` returned as 502, and prompt-list caching | Security advisory or 1.x end of life; a wanted 2.x capability; Python 3.15; a fleet sibling migrates |
| GATE-05 | `dimensions` optional-send, a Voyage adapter and an Azure auth check | A cloud embedding provider is wanted again |
| GATE-06 | Offline write-behind sync (single primary plus a client queue) | Scheduled; its ADR follows RET-03 |
| GATE-07 | OC-FT-02 exact-query embedding cache with singleflight | MEAS-03 shows material benefit |
| GATE-08 | Bounded provider admission; `keep_alive` and a timeout split; a whole-search deadline | Measured overlap, cold-load failures or client timeouts |
| GATE-09 | Shadow-index publication | A materialized vector index exists |
| GATE-10 | Import lineage; structured trust provenance; an opt-in secret warning | A bad batch needs rollback; automated ingestion is proposed; a credential incident |
| GATE-11 | Container containment pilot; full-SHA Action pins; a backup fsync durability model | Operator scopes each |
| GATE-12 | Move the git-onboard watermark to its own table | More git-onboard state, or a second repo per project |
| GATE-13 | Bulk-search endpoint | A mnemosyne burst pattern proves expensive |
| GATE-14 | A relevance threshold; ingest backpressure (open question 17); word heatmaps; a memory-only audit log | A consumer needs each |
| GATE-15 | Cloud-backup Phase 2: `oc cloud list/pull`, remote prune, restore from cloud, envelope co-push | Each item's own trigger (0001 §8) |
| GATE-16 | A save-response hint when a save is tombstoned | Operator experience asks for it |
| GATE-17 | Remove the inert `pinned_limit` | v5.0.0 |
| GATE-18 | Deduplicate the CLI `--confirm` branch | A third such command |
| GATE-19 | Metrics 4E enablement and 4F observation; Prometheus retention validation; later observability decisions | MEAS-01 passes, plus authorization |
| GATE-20 | Prompt-library Stages 2 and 3 | Stage 1 has shipped; mcp 2.x for Stage 3 |
| GATE-21 | Run backup verification in a killable subprocess | A verification outlives `cloud_backup`'s 900 s bound in production (0001 Diff review: cancelling the await does not stop the worker thread) |
| CAL-01 | Quarterly embedding-provider sweep | Next due about 2026-11-29 (0006) |
| CAL-02 | Quarterly cloud-restore drill: decrypt and verify an artifact older than the newest, the only coverage old artifacts get | Next due about 2026-12-29 (0001 Phase 0, "the first run of the restore drill": re-run quarterly, sampling an older artifact) |
| CAL-03 | Quarterly rclone bump (`COPY --from=rclone/rclone:<tag>` in the Dockerfile; Dependabot does not track it) | Next due about 2026-12-29; 1.75.1 was the latest release on 2026-09-29 |

## Operator decisions register

These wait on the operator, not on engineering:

- **Storage and data:**
  - DATA-01's decision 5 (the share root's access);
  - DATA-03 (Dropbox retention).
- **Production:** MCP backup tools (OPS-07).
- ~~**CI:** how Dependabot PRs get past the CodeQL required checks (HYG-09).~~ Decided 2026-09-30: keep default setup and re-land Dependabot changes by hand for now.
- ~~**Timestamps:** the naive-row policy and version classification (TS-02).~~ Decided 2026-09-30: reject, as a MINOR exception.
- **Releases:** the v4.0.0 tag (V4-02).
- **Measurement:** the next 0010 cycle (MEAS-01).
- **Prompts and cost:**
  - Stage 0 isolation and start (LLM-03);
  - 0015 Q1-Q8 and the 0018 fork (LLM-04);
  - the gateway scope (LLM-06).
- ~~**Process:** branch protection (HYG-07).~~ Decided and applied 2026-09-28.

## Belongs to other repositories

Found in the inventory, but not OpenChronicle work:

- **Fleet-kit:** lesson harvests, and whether the canonical `gitleaks.yml`
  scans only the pushed range. Two `standards_audit.py` defects found by HYG-02 (2026-09-29): PY-04
  requires a group named `pip-dev` even when the repo uses the `uv` ecosystem
  and UNI-07 already accepts `uv-dev`; and UNI-02b reports the hook inactive
  in a git worktree, where `.git` is a file and the hook lives in the common
  directory (the same repo passes from its main checkout).
- **portainer-mcp:** a Portainer configuration backup route, tracked in
  that repository's `STATUS.md` (done when one backup has been taken by the
  chosen route).
- ~~**Other repos:** `FUNDING.yml` missing in filesystem-mcp and
  mnemosyne-mcp.~~ Both have it (verified 2026-09-29).
