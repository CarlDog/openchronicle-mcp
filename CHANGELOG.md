# Changelog

Release history for OpenChronicle v3. One entry per Docker-tagged
release; the deployed release is whichever tag the Portainer stack's
`OC_TAG` env points at. Created 2026-08-16 (review Batch E),
reconstructed from the status-doc revision addenda for rc1-rc5.

## Unreleased

Not yet tagged, so not yet deployed — stack 151 stays tag-pinned to
`:v3.0.0`. The import/export item below is the first runtime change
since the tag; it ships when `OC_TAG` next moves.

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
