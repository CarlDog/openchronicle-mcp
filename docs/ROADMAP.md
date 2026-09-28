# OpenChronicle development roadmap

**What this is.** The ordered plan for all open work: every idea, feature,
defect, gated item and decision, gathered in one place. It is sequenced into
phases **without dates**, because work happens in bursts.
[CODEBASE_ASSESSMENT.md](CODEBASE_ASSESSMENT.md) remains the source of truth
for *current state*. [V3_PLAN.md](V3_PLAN.md) and the
[design records](design/README.md) hold each item's full detail. This file
holds the order.

**Built:** 2026-09-28, from a full inventory of V3_PLAN, the assessment,
design records 0001-0019, OpenChronicle memories, GitHub issues and PRs,
long-lived branches and code comments (the code carries no work-marker comments).
**Operator priorities:**

- the persistent-storage review first;
- production health next;
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
| HYG-01 | Close issue #27: all four findings shipped in the v3.4.0 tag, with CI green on the exact commit | S | Evidence in assessment revs 201-204 and 233 |
| HYG-02 | Standards gaps in issue #17: tick UNI-05 (done in rev 200); add `.editorconfig` (UNI-06); add a `Last updated:` line to `STATUS.md` (UNI-08); add the `Fleet standards:` stamp (UNI-09); create GitHub Releases for the tags that lack one (every `v*` tag except v3.3.0, including v3.4.0) (UNI-19) | S | #17 |
| HYG-03 | OpenChronicle memory cleanup (needs the API key now): a stale pinned "current state" memory (claims v3.1.0 live) floats into every search; a junk memory with content "test"; eight milestone-tagged memories describe the deleted Gemini branch; an obsolete v3.4.0 changelog draft; resolved `mcp-feedback` notes still open; portainer-mcp notes filed under this project | S | 2026-09-28 inventory |
| HYG-04 | Delete stale branches and worktrees: `origin/v3/develop` (0 ahead of `main`, 290 behind); the `vigilant-mendel` worktree (on `c7f36a7c`) | S | |
| HYG-05 | Review and merge Dependabot PRs #45 and #46 on fresh CI | S | |
| HYG-06 | Design-record status corrections still open: the 0002, 0003 and 0004 headers (0004's shipped ranks 2, 4, 5, 8 and 10); 0016's track-3 checkpoint still says "unmerged branch" | S | Design index rows were corrected on 2026-09-28 |
| HYG-07 | Decide whether to enforce "work lands through a PR" with branch protection on `main` (revs 201-211 were direct pushes) | S | Decision. The same gap bit portainer-mcp on 2026-09-28: with no required checks, `gh pr merge --auto` merged at once, before CI finished (its STATUS.md now carries the matching item, PR CarlDog/portainer-mcp#36). Likely fleet-wide |

## Phase 1 — Persistent storage and data safety (HIGH PRIORITY)

| ID | Item | Size | Detail |
|---|---|---|---|
| DATA-01 | **Persistent-storage architecture review.** Covers: the volume is keyed to the compose project name; automatic backups share the data volume; the live log path is wrong; everything sits on one NAS; the `docker` share grants `Everyone` read; `/config` is mode 0777; whether `assets`, `output`, `plugins` and `oc-output` are still needed. Output: a reviewed target layout plus a cutover and rollback plan | M | V3_PLAN active 14. The premise was checked on 2026-09-24: the database has persisted since the 2026-05-06 cutover, and it survived the 2026-09-25 recreate (1,088 memories). **Review written 2026-09-28:** [0020](design/0020-persistent-storage-review.md), decisions 1-4 adopted as recommended on 2026-09-28 and step A (the log path, environment only) applied the same day. Step B deployed with OPS-03 the same day. Open: decision 5 (the share root's access) |
| DATA-02 | Cloud-backup Phase 0: Dropbox App Folder probe, two age keypairs with independent escrow, a two-identity decrypt drill. Answers the "one NAS" risk | S | **Done 2026-09-28** ([0001 Phase 0 record](design/0001-cloud-backup.md#phase-0-record-2026-09-28)): App folder verified, both identities decrypted the uploaded artifact to `integrity_check` `ok` and 99%/100% row counts. The one-NAS risk stays open until OPS-08 pushes nightly |
| DATA-03 | Dropbox retention decision: keep the account as the backup target; how much of the existing 6.75 GB to keep | S | 0001 §13 Q7. Decision |
| DATA-04 | Check that the restore path has a post-swap writeability probe (`BEGIN IMMEDIATE`); add it if missing | S | 0004 F8 step 5 |
| DATA-05 | Delete the v2 pre-migration backup (its condition, a verified v3 backup, is now met) | S | V3_PLAN Phase 9 Day 7. After DATA-01's inventory |

## Phase 2 — Production health

| ID | Item | Size | Detail |
|---|---|---|---|
| OPS-01 | **Deploy v3.4.0** (env-only: move `OC_TAG`; `OC_LOG_FILE=/output/logs/openchronicle.log` is already set, as 0020 step A, 2026-09-28). Read back `package_version` and `build_revision`; check REST and MCP (with the key) and embedding status; have a tested rollback. Also retires 0014's interim restart control | S | V3_PLAN active 9 and 13; CHANGELOG v3.4.0 deploy note. **Done 2026-09-28** (assessment rev 245): 3.4.0 / `9b1e83e6` live, revision `known`, reconcile generated 0, access checks pass. No schema change, so rollback is `OC_TAG=v3.3.0` (not exercised live). OPS-02 now proves the revision fix across a real restart |
| OPS-02 | NAS restart gate for ADR 0005 §7 in both start orders: revision known within 60 s, `stale` and `space_mismatch` at 0 | S | 0005 §7; 0014 must-run 5. After OPS-01 |
| OPS-03 | **Reconcile stack 151's detached compose** (or re-attach it to Git). Covers: the `oc-observability` network against the bridge rule; the Host-list fix (PR #35); the `OC_LOG_FILE` default; the `/exports` bind mount; the hardcoded `OC_BACKUP_DIR`; `container_name: openchronicle-mcp`; an explicit API allowlist if metrics are ever enabled | M | V3_PLAN active 13; 0016 track 3. Uses DATA-01's target layout. **Done 2026-09-28: merged (PR #50, `5a207070`) and deployed to stack 151** (file version 143, then `HOST_CONFIG_DIR` removed; 0020 step B, all checks passed). Operator decisions: the shared bridge for both services, with the collector scraping `host.docker.internal:18000`; stay file-based; drop the unreviewed Watchtower label; OPS-03 before OPS-01, on v3.3.0. `tests/test_nas_compose_shape.py` pins the external data volume, names, bridge, `/exports` and `container_name` (12/12 mutants caught); a three-dimension pre-deploy review found no data-safety or access regression, and its findings are fixed |
| OPS-04 | Next release, carrying 0017's nightly-backup change (catalogued, verified, quarantined) and the 0016 track-1 search fix, with its own deploy check and a design 0010 change-impact review | M | V3_PLAN 0017 entry 1; 0016 §5 |
| OPS-05 | Deploy the `/exports` mount. Needs: a host directory owned by uid 1000 and restricted ACLs. Check: read a snapshot through the share, compare it with the off-NAS digest, run disposable restore checks, and measure request-tail impact | M | 0017 steps 4-5. After OPS-03 and OPS-04 |
| OPS-06 | Client migration after the auth change: every MCP client (Claude Code on each machine, and any other client) sends the bearer key; inventory non-Claude clients | S | Auth enabled 2026-09-25; 0014 F13 exposure |
| OPS-07 | Decide whether to enable the MCP backup tools. Auth is on now, so only an explicit `OC_BACKUP_DIR` (from OPS-05) and the operator's call remain | S | 0017; decision |
| OPS-08 | Cloud-backup Phase 1: an rclone plus age job in the image, three health fields, compose lines and tests. Done when three green NAS nights pass plus a decrypt check | M | 0001 Phase 1. After DATA-02 and OPS-03 |

## Phase 3 — Timestamp ordering fix (draft PR #38)

| ID | Item | Size | Detail |
|---|---|---|---|
| TS-01 | Inspect the verified off-NAS copy's raw `created_at` values for naive or malformed timestamps | S | V3_PLAN active 12. Unblocked now |
| TS-02 | Decide the policy for naive legacy rows, and whether rejecting naive input counts as MINOR or MAJOR under STABILITY.md | S | 0016 track 2; decision |
| TS-03 | Pre-migration gate: a fresh off-NAS copy, plus an old/new image-pair rehearsal. Also close the drill's coverage gaps: restoring the restart policy, Portainer freeze and recreation, the production host-source `stage` block, and the failure paths | M | 0017 steps 6-7; runbook "What that drill did not cover" |
| TS-04 | Rebase PR #38 (37 commits behind `main` on 2026-09-28; docs conflicts only as of 2026-09-24), then fresh CI, review, release, and a deploy with the rehearsed rollback | M | After TS-01 to TS-03 |

## Phase 4 — v4.0.0

| ID | Item | Size | Detail |
|---|---|---|---|
| V4-01 | Merge `main` into `v4/develop` (6 ahead and 79 behind on 2026-09-28; conflicts in `embedding_service.py`, `sqlite_store.py`, `cli/commands/memory.py`, the CHANGELOG and the assessment); run the v4 tests | L | Overdue under the "merge regularly" convention |
| V4-02 | v4.0.0 tag decision and release (ADR 0008 pins as ranking prior, `PIN_RANK_LIFT = 0`; MAJOR) | S | V3_PLAN active 1; decision |
| V4-03 | Sweep-harness hardening minors: the channel-integrity assertion, run-identity metadata, the `--sweep`/`--out` collision, and noise labels in verdicts | S | V3_PLAN active 1 residual |

## Phase 5 — Correctness and code quality

| ID | Item | Size | Detail |
|---|---|---|---|
| QUAL-01 | **CLI contract gaps**, confirmed in code 2026-09-24: a blank project name is accepted; `--limit` and `--offset` are unvalidated; `show-project --json` prints plain text when the project is not found; no handler-level error guard (so `export --out <dir>` tracebacks); exporting an unknown project exits 0 with an empty envelope | M | Found in OC memory, not in any repo doc until now |
| QUAL-02 | Rev-209 deferred minors: push exactly the smoke-tested image, or pin the base digest; sort OpenAI `data` by index; `LC_ALL=C` for git children; redact `OLLAMA_HOST` userinfo in the TLS warning; a stop flag between backfill chunks | S-M | V3_PLAN active 9 |
| QUAL-03 | Consolidate the three snapshot-inspection implementations into one leaf module | S | V3_PLAN 0017 deferred item |
| QUAL-04 | `set_pinned` does not bump `updated_at`, and `projects` has no `updated_at` | S | 0001 §11.5 |
| QUAL-05 | Docs-parity gates: the CLI argparse tree, the MCP tool inventory, and `OC_*` env vars against the docs | M | 0004 F5; V3_PLAN active 7 |
| QUAL-06 | Consume `uv.lock` in CI and Docker (`--locked`, pinned uv), audit the locked dependency graph, and drop unused dependencies | M | 0004 F6; V3_PLAN follow-ups |
| QUAL-07 | `_cosine_similarity` has no production caller | S | V3_PLAN follow-up |
| QUAL-08 | Persistent Ollama HTTP client, with NAS p50/p95/p99 evidence at 1 and 8 clients, cold and warm, across an Ollama restart | M | V3_PLAN active 15; 0014 salvage |
| QUAL-09 | MCP tool ergonomics from dogfooding: `memory_save` and `memory_update` echo the full content back; `memory_update` has no append or targeted edit; triage the reported "expected nonoptional" optional-parameter error (not reproduced) | M | OC `mcp-feedback` memories |
| QUAL-10 | Cache-friendly tool surfaces: keep tool descriptions and server instructions byte-stable and in a stable order, enforced by a test | S | 0019 lever 5; 0015 §1 |
| QUAL-11 | **MCP tools silently ignore unknown arguments.** `memory_search` counts with `top_k`, while its sibling `memory_list` uses `limit`. A caller who passes `limit` gets the default of 8, with no error: on 2026-09-28 `limit: 3` and `limit: 5` each returned 8 results (about 10 KB), and the 2026-08-16 "limit=3 returned 34" report is probably the same trap. Fix: reject unknown arguments on every tool, with INVALID_ARGUMENT naming the field and the valid one; optionally also accept `limit` as a `top_k` alias (MINOR under STABILITY.md). Test that a misspelled optional parameter is refused on all 18 tools | S-M | OC `mcp-feedback` memory `2a637611` (updated 2026-09-28) |

## Phase 6 — Measurement foundations

These produce the numbers that phases 7 and 8, and several gated items, wait
on.

| ID | Item | Size | Detail |
|---|---|---|---|
| MEAS-01 | Design 0010 disposition. Needs a new scoped decision first; then a quiet NAS window with interference attribution; a frozen acceptance run (C/A overhead, REST list p99, MCP list p99 with at least 1,000 samples); the affected 4D checks; and keep-or-remove for stack 216 | M-L | 0010 4C final disposition; the attribution record |
| MEAS-02 | Concurrency probe: reconcile V3_PLAN active 3 (the probe already exists as `scripts/probe_performance.py`), then measure store-lock contention at realistic fleet N | S-M | 0007 Stage 0 |
| MEAS-03 | OC-FT-01: measure duplicate query-embedding rate and the embedding share of latency | M | 0012 |
| MEAS-04 | Public, reproducible memory-quality evaluation on a sanitized corpus | M | 0011 H1 |
| MEAS-05 | Which clients (Claude Code, Codex, Gemini CLI and others) expose per-request token, time and cost counts | S | 0018 and 0019 research |

## Phase 7 — Prompts and LLM cost (the north star)

| ID | Item | Size | Detail |
|---|---|---|---|
| LLM-01 | Research pass. For 0019: memory and context layers against token use, gateway tools, and FreeToken re-read for generation cost. For 0018: DSPy and GEPA, TextGrad and OPRO; Langfuse and PromptLayer outcome-to-version linkage; comparing versions at small N | M | 0018, 0019 |
| LLM-02 | Provider SDK integration survey: Copilot SDK, OpenAI Agents SDK, Claude Agent SDK, Google Gen AI, Groq and Ollama SDKs. Define the setup path, auth, lifecycle, isolation, terms, and a provider-neutral abstraction while keeping OC's memory-service boundary | M | V3_PLAN active 8 (added 2026-09-24) |
| LLM-03 | Prompt-library Stage 0 pilot, with 0018's revision (track outcomes, attempts and savings). Choose isolation first. Operator-run and zero code, so it **can start any time** | S | 0015 §6; 0016 track 4; 0018; V3_PLAN active 11 |
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
| CAL-01 | Quarterly embedding-provider sweep | Next due about 2026-11-29 (0006) |

## Operator decisions register

These wait on the operator, not on engineering:

- **Storage and data:**
  - DATA-01's target layout;
  - DATA-03 (Dropbox retention).
- **Production:**
  - when to deploy (OPS-01);
  - compose reconciliation or Git re-attach (OPS-03);
  - MCP backup tools (OPS-07).
- **Timestamps:** the naive-row policy and version classification (TS-02).
- **Releases:** the v4.0.0 tag (V4-02).
- **Measurement:** the next 0010 cycle, and stack 216 (MEAS-01).
- **Prompts and cost:**
  - Stage 0 isolation and start (LLM-03);
  - 0015 Q1-Q8 and the 0018 fork (LLM-04);
  - the gateway scope (LLM-06).
- **Process:** branch protection (HYG-07).

## Belongs to other repositories

Found in the inventory, but not OpenChronicle work:

- **Fleet-kit:** lesson harvests, and whether the canonical `gitleaks.yml`
  scans only the pushed range.
- **Other repos:** `FUNDING.yml` is missing in filesystem-mcp and
  mnemosyne-mcp.
