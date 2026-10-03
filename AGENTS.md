# OpenChronicle Project Instructions

`AGENTS.md` is canonical. `CLAUDE.md` is a byte-identical compatibility
mirror for clients that load that filename; a repository-hygiene test
enforces parity.

## Project Status File

**`docs/CODEBASE_ASSESSMENT.md`** — single source of truth for this project.

**Fleet standards:** python-service v3.0 — audited 2026-09-29 (one open gap: PY-04, whose check predates the uv ecosystem; see issue #17)

## Project-Specific Notes

- **Development priorities (operator, 2026-09-08).** Accuracy comes first;
  speed and responsiveness are second only to accuracy. Evaluate new
  features and architectural changes against both before expanding scope.
  For runtime-affecting work, use proportionate evidence of request latency,
  tail latency and responsiveness under relevant load; throughput alone is
  not enough. Preserve existing acceptance/noise budgets. This priority
  does not itself authorize a benchmark, release, deployment or enablement.
- **Rules for autonomous agents** (Claude, Gemini/Antigravity, Codex).
  Added 2026-09-23 after [design 0014](docs/design/0014-gemini-audit-branch-review.md).
  - Research and review designs (0003, 0011, 0012 and similar) are
    not authorization to implement. Implement a gated or parked item
    only after the operator ratifies it and its named measurement or
    trigger is met.
  - Work lands through a pull request so CI runs. A pushed branch
    alone gets no test run. Since 2026-09-28 GitHub enforces this: `main`
    is protected for everyone, admins included, requires the CI checks
    listed under ROADMAP HYG-07, and requires the branch to be up to date.
    `gh pr merge --auto` now waits for those checks.
  - Nothing is "shipped" or "verified" before it is in a tagged
    release, and CI has passed on the exact commit.
  - Never write OpenChronicle milestone memories for unmerged work.
- **Voice and posture** (operator standing rule, 2026-05-02; restored from
  the v2 backup on 2026-09-30). Applies to the README and all user-facing
  docs:
  - Don't undersell. State what the work is, confidently; no "just a
    personal project" qualifiers or apologetic hedges.
  - Don't sell competitors' products. No "consider also" pointers; the
    README is not a market survey.
  - State the scope honestly: memory, git onboarding and projects, by design.
    Honest about boundaries is not apologetic about quality.
  - The high bar stays: lean scope does not mean lean rigor.
  - No benchmark chasing for marketing; running one is curiosity.
  - Competitive context is internal only and never goes in user-facing copy.
- **Docs + memories before every commit.** Standing rule (2026-05-05).
  Before any `git commit` on this repo, update the affected docs (at
  minimum `docs/CODEBASE_ASSESSMENT.md`; for in-flight work also
  `docs/V3_PLAN.md` and the agent-instruction "Current Sprint" section),
  keep `AGENTS.md` and `CLAUDE.md` byte-identical, and save a
  milestone/decision/scope memory to OC if the MCP server is reachable.
  The commit and the docs land together — never one without the other.
- **Compatibility.** Personal project with no public users, so there
  are no compatibility shims for old behavior. Production runs the v3.x
  line (see Branch state), so every change follows the semver rules in
  `docs/api/STABILITY.md`: a breaking change is MAJOR and goes to
  `v4/develop`.
- **Branch state.** `main` is the v3.x PRODUCTION line (it was
  force-pushed from `v3/develop` at the 2026-05-06 cutover). Since
  2026-08-29, **`v4/develop` is the v4.0.0 development line**
  (operator-directed, created for ADR 0008's breaking work): v3.x
  maintenance and additive features go straight to `main`; anything
  MAJOR-breaking goes to `v4/develop`; merge `main` → `v4/develop`
  regularly so v4 tracks prod fixes. CI runs test+quality on both
  branches but publishes images ONLY from `main` and tags — a
  `v4/develop` push can never move `:latest` or reach the NAS stack.
  v2 is frozen at `archive/openchronicle.v2` (`bb217d9`), and v1
  lives at `archive/openchronicle.v1`.
- **Post-CI redeploy convention.** The stack is TAG-PINNED, so a green
  build is not by itself a reason to redeploy. `docker-compose.nas.yml`
  **requires** `OC_TAG` (`${OC_TAG:?...}` since 2026-08-28 — a deploy
  with it unset fails loudly instead of silently tracking `:latest`),
  and stack 151 pins it (`v3.8.0` since 2026-10-03); a push to `main`
  refreshes only `:latest`, which that stack does not pull. **Code goes
  live when `OC_TAG` moves — a push alone deploys nothing.** So runtime
  changes (`src/`, `pyproject.toml`, `Dockerfile`) ship with the next
  tagged release, and a `portainer-mcp` redeploy is warranted only when
  you are moving `OC_TAG` to a new tag. `docker-compose.nas.yml` changes
  do not ship even then: see the stack note below. The
  `build-and-push` job in `.github/workflows/test.yml`
  gates that image: it runs only after `needs: [test, quality]`
  pass, so a red pytest or quality run cannot ship `:latest`. It also
  builds the image locally and runs
  `tools/ci/smoke-image.sh` before pushing: `oc version` must report
  the commit's SHA, the runtime extras must import, and a started
  container must answer `/health` and report the same SHA. An image
  that cannot start never reaches `:latest`.
  Doc-only / hook-only pushes don't need a redeploy.

  **Stack 151 is file-based and detached from Git** (operator decision).
  Portainer holds its own copy of the compose, so a git redeploy does not
  apply. Look up the stack id dynamically (don't hardcode it), then move
  the tag with one call, which redeploys a file-based stack:

  ```text
  portainer_list_stacks → filter for name == "openchronicle-mcp" → use that .Id
  portainer_set_stack_env(stack_id=<id>, set=[{name: "OC_TAG", value: "<tag>"}],
                          confirm=true, pull_image=true)
  ```

  The stored compose matches the repository file. OPS-03 (2026-09-28)
  reconciled it: the shared bridge, design 0020's volume layout (the data
  volume external and pinned by name, `/config` a named volume) and
  `container_name: openchronicle-mcp`. Since 2026-10-03 (assessment rev
  303) it matches `main` at `4f7a71f`: PR #97's inline metrics collector,
  whose settings all come from the stack env. The repository
  file reaches production only through a reviewed
  `portainer_update_stack_file`, never pasted unreviewed and never by a git
  redeploy. When a release needs both new compose lines and new env values,
  update the file first and the env second: `update_stack_file` only
  round-trips the existing env, and a new image booted under the old
  compose can miss settings its first maintenance run needs.
  `OC_LOG_FILE=/output/logs/openchronicle.log` is set in the stack env
  (0020 step A).

  Verify with `mcp__openchronicle__health`: `package_version` is the
  signal **when the released version actually changed** — it reports the
  real release since rc6, so a value that has not moved to the expected
  new version means the new image is not running. It CANNOT verify a
  same-version redeploy: two images built from the same version both
  report it, so an unchanged reading is the expected result either way.
  For that case read `health.build_revision` — since 2026-08-28 the CI
  build bakes the full git SHA into the image (`/app/build-revision`)
  and health/`oc version` report it, so a same-version redeploy is
  verified by comparing it to the expected commit. (Images built before
  that report `"unknown"`; fall back to the container's
  `org.opencontainers.image.revision` label for those.) Do **not** use
  `db_modified_utc`
  for this. The store opens `PRAGMA journal_mode = WAL`
  (`sqlite_store.py`), so writes land in the `-wal` sidecar and the main
  DB's mtime only advances on checkpoint. It is a checkpoint clock, not a
  liveness or freshness signal.

## Phase-end audit checklist

Project-specific additions to the standard phase-end audit. The generic
checklist lives in the fleet rules; this section records what *this* repo
does differently.

### Permanently closed — do NOT re-raise

- **Author email in commit history.** 540 of 779 public commits carry a
  personal-domain email. **Decided 2026-08-28: accepted, never to be
  remediated.** A history rewrite cannot retract it (unreferenced commits
  stay retrievable by SHA without a manual GitHub Support GC request; the
  address has been public since 2025-07-15 and is mirrored beyond our
  reach) while certainly destroying ~1,700 commit SHAs, the
  `archive/*` frozen-branch guarantee, and every SHA reference in our own
  docs and OC memories. Full reasoning:
  [security_posture.md](docs/configuration/security_posture.md).
  The pre-commit identity hook prevents recurrence and is verified
  working. **If an audit surfaces this, the correct action is to close it
  citing this entry — not to re-analyse it, not to ask the operator
  again.**

- **The internal NAS hostname appearing in tracked files.** The 2026-07-25
  repo-wide scrub convention (`your-nas` placeholder, f483ec3d) is
  **retired for this repo — decided 2026-08-29** after the hostname was
  reintroduced (revs 141-142), a remediation shipped (bb558436), and the
  operator chose full rollback (31c3f331) as overcaution: it is a
  non-routable LAN NetBIOS label, permanently retrievable from 79
  never-rewritten pre-scrub history occurrences, and enforcement
  machinery cost more than the HEAD-discoverability it bought. The
  hostname MAY appear in tracked files here; do not scrub it, do not
  flag it, do not re-raise the convention — close any finding citing
  this entry (OC memory `46bb58cc` has the full sequence). The generic
  PII guards (user-home paths, personal-email domains, author identity)
  are unchanged and still binding.

- **Splitting `sqlite_store.py`, `git_onboard.py`, or
  `tests/test_http_api.py` on size.** Assessed 2026-08-28 and rejected:
  all three are one concern expressed at length, and the "300-400 line
  soft cap" they were measured against is not repo policy — it appears
  once, as an aside in `docs/design/0001-cloud-backup.md`. Cohesion
  judgements for the two source files are recorded in
  [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md); the revisit
  trigger for `sqlite_store.py` is search-section growth, not total lines.
- **Substituting `container.storage.vacuum()` into `cmd_db_vacuum` to
  remove its `noqa: SLF001`.** Measured regression: `vacuum()`
  checkpoints FULL *then* VACUUMs, while the CLI needs VACUUM *then*
  `wal_checkpoint(TRUNCATE)`. Through the port the command would report
  "Saved: 0" and leave the WAL untruncated. The reach-through is
  deliberate and documented at the method.
- **Adding a shared `store` fixture to `tests/conftest.py`.** pytest
  resolves fixtures nearest-first, so the six existing local definitions
  would shadow it — it becomes a seventh shape rather than replacing six.
  The local fixtures also diverge load-bearingly (different seeded
  projects, different close behaviour). Tolerated, per the duplication
  bar.

### Every phase end: roadmap reconciliation

Added 2026-09-28, after a manual inventory found open work scattered across
docs, OC memories, issues and branches, some of it in no plan at all.

1. Sweep every source of open work for this project: `docs/V3_PLAN.md`,
   `docs/CODEBASE_ASSESSMENT.md` known-open items, `docs/design/`, OC
   memories for project `fe2ef898-…` (ideas, `mcp-feedback`, deferred
   notes), open GitHub issues and PRs, long-lived branches (`v4/develop`,
   draft PR branches), and work-marker comments in the code.
2. Every open item must appear in [docs/ROADMAP.md](docs/ROADMAP.md) under a
   stable ID, or be dropped with a recorded reason.
3. Mark items done that finished since the last audit; correct any status
   line or cross-reference that no longer matches reality.
4. Re-check the phase order against the operator's current priorities and
   record any change the operator makes.

### Quarterly additions

- **Bump rclone** (design 0001 §3.4): Dependabot does not track the
  Dockerfile's `COPY --from=rclone/rclone:<tag>`, and a stale rclone falls
  behind provider OAuth changes. Check the latest release and bump it.
- **Embedding-provider sweep** (operator-directed 2026-08-29): diff the
  Ollama library embedding catalog, Ollama Cloud, Atlas Cloud, and the
  Anthropic embeddings page (no first-party API as of 2026-08-29)
  against the baselines in
  [design/0006 §Recurring cadence](docs/design/0006-embedding-provider-review.md);
  pull + benchmark any new credible candidate; reopen the provider
  decision only on 0006's named triggers. Absorbs the former standalone
  Ollama Cloud re-check — one clock, not two.

### Cadence relaxations

- The **author-identity audit** (`git log --all --pretty='%ae' | sort -u`)
  is retired as a finding-producing check per the above. Run it if you
  like; the only actionable outcome is a *new* non-noreply identity
  appearing after 2026-08-28, which would mean the hook is not installed
  on some machine.

## Current Sprint

**2026-10-03 — v3.8.0 deployed (migration 005, schema 5);
phase-end audit in progress.**

- **Live:** v3.8.0 (`3e9fa8d7`, schema 5) on stack 151 since 2026-10-03, with
  the MCP backup tools on (OPS-07) and runtime metrics on (rev 303); stored
  compose matches `main` at `4f7a71f`. Nightly catalogued backups land in `/exports/backups/auto`
  ([0017](docs/design/0017-exposed-backup-and-restore.md)), and the nightly
  encrypted offsite push ([0001](docs/design/0001-cloud-backup.md) Phase 1)
  sends them to `ocdrop:openchronicle/nas`. Auth is on.
- **Closed 2026-09-28/29:** DATA-01 ([0020](docs/design/0020-persistent-storage-review.md),
  steps A and B), DATA-02, OPS-01 to OPS-06, HYG-04, HYG-07; v3.4.0, v3.5.0
  and v3.6.0 released and deployed. The record is in the assessment's
  revision history (revs 240-258).
- **Closed 2026-10-03:** OPS-08, after three green nights, the
  deliberate-breakage check and the latency sample during a nightly push
  (assessment rev 286).
- **Deployed 2026-10-03:** v3.7.0, verified with health, the latency sample
  (p95 6.0 ms) and the backup tools (assessment rev 295); then v3.8.0, the
  timestamp release (TS-04), verified with health, 0 non-UTC values and the
  latency sample (p95 5.8 ms) (assessment rev 300). Its rollback target is the
  16:40Z pre-migration snapshot.
- **Merged, unreleased:** QUAL-11 (MCP tools refuse undeclared arguments,
  PR #94, merged to `main` 2026-10-03) is classified MINOR (operator,
  2026-10-03) and ships in the release after v3.8.0.
- **Next:** [docs/ROADMAP.md](docs/ROADMAP.md) owns the order of all open
  work. Now: the DATA-06/07 NAS session, then v4.0.0 on the
  operator's tag call (V4-01).
- **Standing:**
  - The Gemini audit branch was rejected as a unit and survives only as the
    tag `archive/gemini-audit-18092026`
    ([0014](docs/design/0014-gemini-audit-branch-review.md)). Never merge it
    or take from it wholesale; its docs and OC milestone memories describe
    unshipped work.
  - Runtime metrics ([0010](docs/design/0010-performance-measurement.md))
    are on in production since 2026-10-03 (assessment rev 303; collector
    profile `metrics-auth`). MEAS-01 is done: its direct-cost run passed
    every gate (rev 305), and the recorder owns the metrics-failure guard
    (QUAL-20). GATE-19's 4F observation remains. Since 2026-10-03 its release gate covers only
    releases that change metrics code; other releases need no exception.
  - Research and idea records (0011, 0012, 0015, 0018, 0019, 0021) are not
    authorization to implement.

**Locked decisions** (V3_PLAN open questions 1, 4, 6, 13, 14, 19):
drop `memory_items.conversation_id`; unified ASGI on port `:18000`;
cut plugin system entirely; MCP tool description quality pass done;
ship `oc memory export/import` day 1; `OC_LOG_FORMAT=human|json`
default human.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the order of open work,
[docs/V3_PLAN.md](docs/V3_PLAN.md) for the detailed entries and history
it cites, and [docs/CODEBASE_ASSESSMENT.md](docs/CODEBASE_ASSESSMENT.md)
for current state.

## Build and Development

```bash
# Install in development mode
pip install -e ".[dev,mcp,openai,ollama]"

# Setup pre-commit hooks
pip install pre-commit && pre-commit install
```

The optional extras are deliberately small:

- `[openai]` and `[ollama]` — embedding providers only (v3 has no LLM)
- `[mcp]` — FastMCP runtime
- `[dev]` — pytest, mypy, ruff, plus the embedding deps for tests

After changing any hook `rev:` in `.pre-commit-config.yaml`, run
`pre-commit install-hooks` from a normal shell before committing.
Installing a hook environment inside a commit lets npm inherit git's
hook variables, and on 2026-09-23 that overwrote a worktree's index.

## Testing

```bash
# Run all tests
pytest

# Run a specific test file or single test
pytest tests/test_memory_export_import.py
pytest tests/test_maintenance_loop.py::test_overlap_skip_records_skip_and_does_not_block -v
```

There are no `@pytest.mark.integration` tests in v3 — the
`tests/integration/` directory and the `integration` marker were cut
along with the conversation engine.

## Linting and Formatting

```bash
# Format and lint with ruff
ruff format src tests scripts
ruff check --fix src tests scripts

# Type checking
mypy src tests --config-file=pyproject.toml

# Markdown linting
npm run lint:md:fix

# Run all checks (what pre-commit does)
pre-commit run --all-files
```

## Architecture

Python 3.14+ project using **hexagonal architecture**. Under
`src/openchronicle/core/`: `domain/` (pure types + ports) →
`application/` (use cases, services) → `infrastructure/` (SQLite,
embedding adapters, persistence backup, maintenance jobs). CLI / API /
MCP drivers live in `src/openchronicle/interfaces/`. The relative paths
below resolve against those two roots.
See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
for the full layout.

**Key Concepts:**

- **Ports**: abstract interfaces in `domain/ports/` that
  infrastructure implements: `StoragePort`, `MemoryStorePort`,
  `EmbeddingPort`, and the `MetricsRecorder` protocol
  (`metrics_port.py`).
- **MCP Server**: `interfaces/mcp/` — 18 tools registered via
  FastMCP by default, plus 5 backup tools when `OC_BACKUP_MCP_ENABLED`
  is on (23, as in production), mounted at `/mcp` inside the unified
  ASGI app.
- **HTTP API**: `interfaces/api/` — FastAPI app factory
  (`create_app`), routes for memory + project + system, FastMCP
  mounted alongside.
- **Embedding Service**: `application/services/embedding_service.py`
  — hybrid FTS5 + cosine similarity via Reciprocal Rank Fusion.
  `EmbeddingPort` adapters: `stub` / `openai` / `ollama`. Falls back
  to FTS5-only when the provider raises (degradation policy).
- **Maintenance loop**:
  `application/services/maintenance_loop.py` — single asyncio task
  dispatches due jobs as background tasks; per-job + global locks
  give skip-on-overlap with sequential-within-process. Job handlers
  in `infrastructure/maintenance/jobs.py`. See
  [docs/architecture/MAINTENANCE.md](docs/architecture/MAINTENANCE.md).
- **Schema migration framework**:
  `infrastructure/persistence/migrator.py` reads
  `migrations/NNN_*.sql` files and applies them within savepoints.
  Idempotent re-run is a no-op. v3 baseline is `001_initial.sql`.

## Conventions

**Naming:**

- Error codes: SCREAMING_SNAKE_CASE (`INVALID_ARGUMENT`, `MEMORY_NOT_FOUND`,
  `CONFIG_ERROR`, `PROVIDER_ERROR`)
- MCP tool names: snake_case (`memory_save`, `context_recent`,
  `onboard_git`)

**Patterns:**

- Strict typing enforced by mypy
- Domain models use `@dataclass`
- Not-found conditions raise `NotFoundError` (from
  `domain/exceptions.py`), caught globally → HTTP 404
- Validation failures raise `ValidationError` (aliased
  `DomainValidationError` to avoid Pydantic collision), caught
  globally → HTTP 422
- Provider failures (embedding adapters, future external systems)
  raise `ProviderError` with `error_code`/`hint`/`details`
- Config / startup-environment failures raise `ConfigError`
- Global exception handlers in `interfaces/api/app.py` eliminate
  per-route try/except
- Pydantic `Field()` constraints on request bodies; `Query()`
  constraints on query parameters
- Use `utc_now()` from `domain/time_utils.py` for current UTC time
  (not inline `datetime.now(UTC)`)
- Use `parse_csv_tags()` from `application/config/env_helpers.py`
  for comma-separated tag parsing

**Secrets:**

- Zero secrets in repo (enforced by `test_no_secrets_committed.py`)
- Use `.env.local` (git-ignored) or `OC_CONFIG_DIR` for secrets
- Test placeholders: `changeme`, `replace_me`, `your_key_here`,
  `test-key`

**GitHub Actions hygiene:**

- "Node.js 20 actions are deprecated" warnings (and any future
  Node-version deprecation) come from an action's *bundled
  runtime*, not the workflow's `runs-on`. Fix by bumping the
  action's major version to one that ships the newer Node runtime.
  Example: `actions/setup-python@v5` → `@v6` was the bump that
  silenced Node 20 warnings.
- Verify the latest major before bumping —
  `https://github.com/<owner>/<action>/releases/latest` (e.g.
  `actions/checkout/releases/latest`,
  `docker/build-push-action/releases/latest`).
- Dependabot's `github-actions` ecosystem in
  `.github/dependabot.yml` opens weekly grouped PRs for action
  bumps automatically. If a deprecation warning fires before the
  weekly run, do a manual bump and let Dependabot pick up from
  there.
- Runtime deprecation is a *warning*, not a build failure. Don't
  treat it as a cutover blocker.
- **Docker image builds amd64 only.** The `build-and-push` job in
  `test.yml` pins `platforms: linux/amd64`. The NAS deploy target is x86-64 and no
  fleet host is ARM, so a QEMU-emulated arm64 build is wasted CI time
  for an image nobody pulls. Re-add `linux/arm64` only if an ARM
  deployment target appears. See claude-fleet-kit
  `fleet/lessons/docker-multiarch-only-what-you-deploy` (dropped
  fleet-wide 2026-07-24).

## Environment Variables

Most-used variables for quick reference:

| Variable | Purpose | Default |
| ---------- | --------- | --------- |
| `OC_DATA_DIR` | Root data directory (derives all data paths when set) | *(unset)* |
| `OC_DB_PATH` | SQLite database location | `data/openchronicle.db` |
| `OC_CONFIG_DIR` | Directory containing `core.json` | `config` |
| `OC_API_HOST` / `OC_API_PORT` | Bind address + port for the unified ASGI | `127.0.0.1` / `8000` |
| `OC_API_KEY` | Bearer token (auth disabled when empty) | — |
| `OC_EMBEDDING_PROVIDER` | `none`, `stub`, `openai`, `ollama` | `none` |
| `OC_EMBEDDING_MODEL` | Embedding model name (provider-specific default) | *(provider default)* |
| `OPENAI_API_KEY` | Used by the OpenAI embedding adapter | — |
| `OLLAMA_HOST` | Used by the Ollama embedding adapter | adapter default |
| `OC_LOG_FORMAT` | `human` or `json` | `human` |
| `OC_LOG_FILE` | Rotating file mirror of the logs (survives container recreates when on a volume) | *(unset; NAS compose sets it)* |
| `OC_MAINTENANCE_DISABLED` | `1`/`true`/`yes`/`on` to short-circuit the loop | unset |

Full reference: [docs/configuration/env_vars.md](docs/configuration/env_vars.md)

## OpenChronicle Memory Integration

OC is available as an MCP server. It provides persistent memory that
survives context compression and session boundaries. **Use it.**

Context compression loses the "why" — decisions made, approaches
rejected, working state, user preferences expressed mid-session. The
status doc (`CODEBASE_ASSESSMENT.md`) tracks project-level state but
not conversational context. OC memory fills that gap.

### Setup

OC runs on the NAS as a Portainer stack (see `docker-compose.nas.yml`).
The MCP server is registered at user scope in `~/.claude.json` as
`openchronicle` pointing at the NAS endpoint over HTTP streamable-http
transport. No project-level setup required.

**v3 endpoint:** MCP and HTTP REST are unified on port `:18000` since the
2026-05-06 cutover. MCP at `/mcp`, REST at `/api/v1/*`, liveness at
`/health`. Each machine's `~/.claude.json` should point at
`http://your-nas:18000/mcp`. (Pre-cutover v2 was `:18001/mcp` for MCP
and `:18000/api/v1` for REST as separate services — that shape is gone.)

For a fresh registration (auth is on, see Auth posture below, so the
client must send the key):

```bash
claude mcp add --scope user --transport http \
    --header "Authorization: Bearer $OC_API_KEY" \
    openchronicle http://your-nas:18000/mcp
```

For local dev (without the NAS), run `oc serve` in a checkout — the
unified ASGI app binds `127.0.0.1:8000` by default, so:

```bash
claude mcp add --scope user --transport http openchronicle http://127.0.0.1:8000/mcp
```

(That uses the local OC store, which is a different memory pool than
the NAS one.)

### Project Identity

Use `project_id: "fe2ef898-0152-40a4-af97-ed97cc86ca45"` in all
`memory_save` calls on the NAS-hosted OC. This is a FK to the projects
table — freeform strings will fail. (Project name on the NAS is
`openchronicle-mcp`, created 2026-05-06 during the v3 cutover.)

**Historical project_ids (no longer valid against the live DB):**

- `87de0f7d-d6ab-4b83-8613-b2b5ff60a57b` — v2 NAS project (lost 2026-05-06
  when the v3 cutover migration produced a corrupt DB and live v3
  restarted against an empty volume; 36 memories were not carried
  forward, 24 remain in the NAS rollback snapshot, and all 36 remain in
  the laptop pre-cutover backup; see the cutover triage document)
- `0db2b2ff-f995-4f59-b059-0fae5c78909d` — LOCAL OC (Windows machine),
  separate memory pool, never valid against NAS

If the NAS DB is recreated again in the future, create a new project
with `project_create` and update this UUID.

**Auth posture: enabled (operator, 2026-09-25).** Stack 151 sets
`OC_API_KEY`, so `/mcp` and REST require
`Authorization: Bearer <key>` (or `X-API-Key`); only `/health`,
`/api/v1/health` and the OpenAPI pages are exempt. Confirmed read-only on
2026-09-28: `/mcp` answers 401 without a key. Every MCP client must send the
key, so a client configured without it cannot reach OpenChronicle. The key
lives only in Portainer and in client configurations, never in the
repository. This supersedes the 2026-05-06 decision to leave auth off. See
[docs/configuration/security_posture.md](docs/configuration/security_posture.md#authentication).

### Session Protocol Addition

After the standard session protocol (status doc, CLAUDE.md sprint),
add:

- Call `memory_search` with keywords relevant to the current task or
  the user's first message. Review results for prior decisions,
  rejected approaches, and working context from previous sessions.

This step is **especially critical after context compression**, where
the compression summary is a lossy snapshot. OC memory is the
lossless record.

### When to Save

Call `memory_save` when any of these happen during a session:

- **Decision made.** Architecture, design, or approach chosen.
  Include what was decided, alternatives considered, and the
  reasoning.
- **Approach rejected.** Something was tried and didn't work. Save
  what it was, why it failed, and what replaced it.
- **Milestone completed.** A feature or significant unit of work is
  done. Summarize what was built and any non-obvious gotchas.
- **User preference expressed.** The user states a workflow
  preference, convention, or standing instruction that isn't already
  in CLAUDE.md.
- **Scope change.** The user redirects mid-task. Save what changed
  and why, so future sessions don't re-tread the old path.
- **Pre-compression.** If a session is getting long (many tool calls,
  complex multi-step work), proactively save working context — what
  we're doing, where we are in it, what's left. There is no hook for
  compression; the only mitigation is saving early.

**Tagging convention:**

| Tag | When |
| ----- | ------ |
| `decision` | Architectural or design decisions |
| `rejected` | Approaches tried and abandoned |
| `milestone` | Completed work summaries |
| `context` | Working state snapshots (proactive saves) |
| `convention` | Patterns, preferences, recurring gotchas |
| `scope` | Scope changes and reprioritizations |

Pin memories that represent standing rules or conventions.

**Don't save:**

- Routine file edits or commands (too granular, no retrieval value)
- Anything already captured in `docs/CODEBASE_ASSESSMENT.md`
- Speculative plans that haven't been confirmed by the user

### When to Load

Call `memory_search` at these points:

- **Session start / post-compression.** Search for the current task
  topic. This is non-negotiable after compression.
- **Before starting a new area of work.** Check if prior context exists.
- **When something feels familiar.** If a problem seems like it was
  discussed before, search before re-deriving from scratch.

### Tools to Use / Avoid

| Tool | Use | Notes |
| ------ | ----- | ------- |
| `memory_save` | **Yes** | Primary persistence mechanism |
| `memory_search` | **Yes** | Primary retrieval mechanism |
| `memory_list` | Occasionally | Browse recent memories when search terms are unclear |
| `memory_pin` | Yes | Pin standing conventions and rules |
| `memory_update` | Yes | Update content/tags of existing memories |
| `context_recent` | Occasionally | Catch up on prior memory activity for a project |
| `health` | Rarely | Diagnostics only |

The v2 conversation tools (`conversation_*`, `turn_record`,
`context_assemble`, `search_turns`) are gone in v3 — Claude Code IS
the LLM, so OC's role is memory/retrieval only.

### Known Gaps

- **No compression hook.** We can't detect when compression is about
  to happen. Mitigation: save-as-you-go discipline.
- **Search is keyword-based by default.** Set `OC_EMBEDDING_PROVIDER`
  to enable hybrid semantic+keyword search. Without it, quality
  depends on good content and tags. Write memories as if future-you
  is searching for them with obvious keywords.

## Key Files

- `pyproject.toml` — Project config, dependencies, tool settings
- `CHANGELOG.md` — release history (rc1 → current)
- `docs/architecture/ARCHITECTURE.md` — v3 layout + schema + ASGI design
- `docs/architecture/MAINTENANCE.md` — maintenance loop + degradation policy
- `docs/cli/commands.md` — `oc` subcommand reference
- `docs/configuration/env_vars.md` — environment variables
- `docs/configuration/config_files.md` — `core.json` schema
- `docs/configuration/security_posture.md` — threat model + secrets handling
- `docs/integrations/mcp_server_spec.md` — MCP tool surface (18 tools)
- `docs/integrations/mcp_client_setup.md` — registering Claude Code, Goose, Open WebUI
- `docs/api/STABILITY.md` — semver + deprecation policy
- `docs/V3_PLAN.md` — full v3 plan, kill list, open questions, phase tracker
- `docs/archive/v2/` — frozen v2 docs (orchestrator, conversation engine, plugin system, etc.)
- `tests/test_architectural_posture.py` — core agnostic of MCP SDK
- `tests/test_hexagonal_boundaries.py` — domain/application/infrastructure layering
- `src/openchronicle/interfaces/api/app.py` — unified ASGI factory (FastAPI + FastMCP at /mcp)
- `src/openchronicle/interfaces/cli/main.py` — `oc` command entry point
- `src/openchronicle/core/infrastructure/wiring/container.py` — DI composition root
- `src/openchronicle/core/infrastructure/persistence/migrator.py` — schema migration runner
