# OpenChronicle Project Instructions

`AGENTS.md` is canonical. `CLAUDE.md` is a byte-identical compatibility
mirror for clients that load that filename; a repository-hygiene test
enforces parity.

## Project Status File

**`docs/CODEBASE_ASSESSMENT.md`** — single source of truth for this project.

## Project-Specific Notes

- **Docs + memories before every commit.** Standing rule (2026-05-05).
  Before any `git commit` on this repo, update the affected docs (at
  minimum `docs/CODEBASE_ASSESSMENT.md`; for in-flight work also
  `docs/V3_PLAN.md` and the agent-instruction "Current Sprint" section),
  keep `AGENTS.md` and `CLAUDE.md` byte-identical, and save a
  milestone/decision/scope memory to OC if the MCP server is reachable.
  The commit and the docs land together — never one without the other.
- **No backwards compatibility.** Personal project, no public users,
  no production. Break whatever needs breaking.
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
  and stack 151 sets `OC_TAG=v3.1.0`; a push to `main` refreshes only
  `:latest`, which that stack does not pull. **Code goes live when
  `OC_TAG` moves — a push alone deploys nothing.** So runtime changes
  (`src/`, `pyproject.toml`, `Dockerfile`, `docker-compose.nas.yml`)
  ship with the next tagged release, and a `portainer-mcp` redeploy is
  warranted only when you are moving `OC_TAG` to a new tag. The
  `build-and-push` job in `.github/workflows/test.yml`
  gates that image: it only
  runs `needs: [test, quality]`, so one green check is a stronger
  signal than the old two-workflow setup: a red pytest/quality run
  now can't ship `:latest` at all (fixed 2026-07-30, standards-gap
  UNI-14 — `docker-publish.yml` used to have no `needs:` at all,
  since GitHub Actions `needs:` can't cross workflow *files*; the fix
  merged the publish job into `test.yml` as a third job).
  Doc-only / hook-only pushes don't need a redeploy.

  Lookup the stack id dynamically (don't hardcode it):

  ```text
  portainer_list_stacks → filter for name == "openchronicle-mcp" → use that .Id
  portainer_redeploy_git_stack(stack_id=<id>, confirm=true, pull_image=true)
  ```

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
  DB's mtime only advances on checkpoint — observed 2026-08-28, a memory
  written at 14:47Z still read `db_modified_utc` 05:26Z a minute later.
  It is a checkpoint clock, not a liveness or freshness signal.

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

### Quarterly additions

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

**2026-08-29 — the ranking/identity/provider arc closed; v3.3.0
shipping to prod.** One day's arc, all reviewed adversarially and all
pushed:

- **v3.2.0 shipped and deployed** with the LAN-local embedding cutover:
  `ollama/nomic-embed-text` on the NAS (`content_egress: local`),
  chosen by the 0006 gold-set benchmark (nomic topped 15 candidates at
  parity with the best cloud models) and a NAS latency leg.
- **ADR 0008 (pins as ranking prior, ACCEPTED rev 4 after three review
  rounds) is COMPLETE on `v4/develop`** (tip includes the sweep):
  float retired from all modes, bounded rank lift implemented, and the
  step-4 sweep's held-out veto rejected every nonzero lift —
  **`PIN_RANK_LIFT = 0` is the recorded winning cell; the float
  removal alone was the fix** (broad-query crowding fell mean
  10.0 → 5.0). Ships as **v4.0.0 on the operator's tag call** (not
  yet made).
- **ADR 0009 (permanent embed-failure classification, ACCEPTED rev 3)
  is IMPLEMENTED and merged to `main`** (844 tests): over-length rows
  park as space/content-scoped tombstones instead of poisoning
  health; `unembeddable` health bucket; `BackfillResult.tombstoned`;
  the live OpenAI capture falsified the spec's error shape (recorded
  in the ADR's Implementation note).
- **v3.3.0 releases from `main`** carrying ADR 0009 +
  `memory_embed background=true`. Deploy note: after redeploy, run
  one backfill (`memory_embed background=true`) — it writes 9
  tombstones and the live NAS health flips
  `degraded`/`stale: 9` → `active`/`unembeddable: 9`.

**Performance measurement (design 0010, operator-adopted 2026-09-04):**
Phases 1–3 are implemented and verified in the working tree, and Phase 4 has
been evaluated and retested on a controlled host, including a two-CPU process-affinity
follow-up. The standard image and development extra
include `prometheus-client`, but runtime metrics remain off by default
(`OC_METRICS_ENABLED=false`). Phase 1's disposable REST/MCP probe, Phase 2's
bounded recorder/exporter and instrumentation, and Phase 3's profile-gated
local Prometheus configuration, saved query catalog, and runbook are complete;
a disposable Docker scrape/restart smoke check also passed. The probe now
retains every attempted direct-scrape duration and enforces a 10-ms minimum
interval. The local
scrape-responsiveness gate passed, but the original and retest A/B/C overhead
gates remain inconclusive because host/order noise is larger than the measured
effect; the enabled retest median also exceeded the 5% throughput-loss limit.
The affinity follow-up still showed 0.18–14.08% disabled and 8.69–16.18%
enabled throughput loss, with the enabled median at 11.62%. One retest case
had connection failures and was excluded. The separate NAS observation stack
has verified test scrapes; retained restart history and production release
remain unverified. After
the reboot, the serialized-setup same-run pilot passed, but the full
three-probe matrix was ineligible with 2,438/2,488/2,285 failed operations
(mostly connection failures); an isolated clean-base control was clean, so
that concurrent method saturated this host. A follow-up with equal rotating
eight-CPU partitions and per-worker keep-alive connections produced three
eligible blocks, but corrected B/C median throughput losses were 1.351%/10.867%
with reversed order effects; earlier prose incorrectly used maxima as medians.
The overhead gate remains inconclusive. The operator approved sequential runs
on CARLDOG-NAS with repeated baseline controls; dedicated hardware is not an
application requirement. After upload approval, all twelve sequential NAS
cases completed: 25,995 successful requests, zero failures/timeouts, matching
corpora and successful enabled scrapes. Median B/C throughput losses were
4.678%/8.344%, but the final repeated A slowed by 5.331% and latency controls
also breached budget; both gates remain inconclusive. Evidence is retained
under data/performance/phase4-20260904/nas-sequential/. The one-shot benchmark
stack was removed; production and the observation stack are healthy and
unchanged. Normal runtime metrics remain off. All 895 tests passed.

**Active queue after this release** (V3_PLAN carries the full
entries): (1) performance-measurement Phase 4 overhead gate (sequential NAS
measurement completed; profiling/optimization needs a separate next step),
(2) cloud-backup Phase 0 + restore drill (operator at a desktop; 0007 Stage 0),
then demand-/trigger-gated items. Design 0007 (long-term scale & resilience)
is ACCEPTED with its staged trigger-gated path. Open operator decision: the
**v4.0.0 tag** from
`v4/develop`.

**Locked decisions** (V3_PLAN open questions 1, 4, 6, 13, 14, 19):
drop `memory_items.conversation_id`; unified ASGI on port `:18000`;
cut plugin system entirely; MCP tool description quality pass done;
ship `oc memory export/import` day 1; `OC_LOG_FORMAT=human|json`
default human.

See [docs/V3_PLAN.md](docs/V3_PLAN.md) for the canonical phase tracker
and [docs/CODEBASE_ASSESSMENT.md](docs/CODEBASE_ASSESSMENT.md) for
current state.

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

Python 3.14+ project using **hexagonal architecture**: `domain/`
(pure types + ports) → `application/` (use cases, services) →
`infrastructure/` (SQLite, embedding adapters, persistence backup,
maintenance jobs). CLI / API / MCP drivers live in `interfaces/`.
See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md)
for the full layout.

**Key Concepts:**

- **Ports**: abstract interfaces in `domain/ports/` that
  infrastructure implements. v3 has three: `StoragePort`,
  `MemoryStorePort`, `EmbeddingPort`.
- **MCP Server**: `interfaces/mcp/` — 18 tools registered via
  FastMCP, mounted at `/mcp` inside the unified ASGI app.
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

For a fresh registration:

```bash
claude mcp add --scope user --transport http openchronicle http://your-nas:18000/mcp
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

**Auth posture (decided 2026-05-06, post-cutover):** `OC_API_KEY` on
stack 151 resolves to empty — auth is **intentionally disabled**.
This is a single-user home-LAN deployment, the LAN is trusted, no MCP
clients are configured to send a bearer header, and the cost/benefit
of switching doesn't pay. If the trust boundary ever changes (public
exposure, untrusted LAN segment, multi-user environment), follow the
"How to enable auth on a running deployment" steps in
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
- `scripts/migrate_v2_to_v3.py` + `scripts/verify_v3_db.py` — one-shot cutover migration
