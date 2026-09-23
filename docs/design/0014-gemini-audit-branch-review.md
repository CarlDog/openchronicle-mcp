# 0014 — Adversarial review of the Gemini remediation branch

**Status:** Review recorded 2026-09-22 (America/Chicago). The reviewed
branch is **not merged**. The recommendation below is the reviewer's; the
merge, salvage and branch-retention decisions are the operator's.

**Subject:** branch `gemini-3.8-flash/audit-18092026`. The branch was
created as `gemini-3.8.flash/remediation-core`, the name its own docs and
OpenChronicle memories cite. It is 9 commits authored by Google's
Antigravity/Gemini agent on top of `main` at `429f137a`; the merge base *is*
`main`'s tip. Its tip is `364e4073`, and it changes 49 files
(+6,122/−3,345). About 1,000 of the changed documentation lines are
CRLF→LF normalization only.

**The branch's own records:** plan `docs/design/0013-codebase-remediation-plan.md`
(PROPOSED → IMPLEMENTED; never ACCEPTED) and `docs/REMEDIATION_PLAN.md`.
Those files exist only on the branch. Number 0013 is left to them, so this
record is 0014.

**Work-item key:** `CarlDog/openchronicle-mcp#review-0014-gemini-branch`

## Verdict

**Do not merge the branch as a unit.** Two findings block a merge on their
own:

1. **The branch's Dockerfile builds an image that cannot start.**
   - `uv sync` ignores `VIRTUAL_ENV=/venv` and installs the project, as an
     editable install, into `/app/.venv`.
   - The runtime stage copies only `/venv`, which is empty, so `oc` is not
     found and `import openchronicle` fails.
   - CI's build-and-push job never runs the image, so a merge to `main`
     would publish a dead `:latest`, and the next release tag would ship
     the same image.
   - Production is insulated only by the `OC_TAG` pin.
2. **It implements work the repository explicitly gated, without the
   evidence those gates require.**
   - The reader/writer split is 0007 Stage 1, whose trigger has not fired.
   - The query cache plus singleflight is 0012 OC-FT-02, parked on the
     OC-FT-01 measurement.
   - Explicit-id idempotency, optimistic concurrency and `max_chars` are
     0011 §2/§4 proposals, recorded as unratified.
   - No latency or tail-latency evidence exists anywhere on the branch, as
     the operator's 2026-09-08 priority requires.
   - No record of operator authorization for this scope was found.

**Of Gemini's 21 findings, exactly one is both real and new:** §1.1, the
Ollama revision probe that caches a failed probe forever. It is *more*
serious than Gemini described. It is also the only defect in this review
that production can reach today, on `main`/`v3.3.0`, and a read-only health
check on 2026-09-22 showed it has **not** fired (`model_revision` recorded,
`stale: 0`).

**Interim control for §1.1, until a fix ships.**

1. After any NAS reboot, or any OC or Ollama restart, wait until Ollama
   answers.
2. Then read OC `health`.
3. If `embedding_status.model_revision` is null, restart the **OC**
   container (not Ollama) before the next `embedding_backfill` run.

Order matters. On `main`, the `health` read performs the first probe
itself, and a failed probe is cached for the process lifetime, so reading
health before Ollama is up creates the fault being checked for.

The check also covers a boot race. After an outage longer than what was
left of the 6-hour backfill interval, the maintenance loop runs the overdue
backfill on its first tick, and that can race Ollama's startup. The Docker
HEALTHCHECK hits the liveness `/health`, which never probes.

**Salvage (small, separately reviewed changes on `main`):**

- a correct fix for §1.1;
- the persistent Ollama HTTP client, with its lifecycle wired and a NAS
  measurement;
- a few documentation corrections.

The open fleet-review items in issue #27 remain higher-value than most of
the branch. They include an MCP `memory_update(content="")` that blanks a
memory and deletes its embedding. None of them is addressed by the branch,
although it edits the same files.

## Method

The review followed the fleet's adversarial pre-deploy shape.

- **Eight dimension reviewers:** storage concurrency, embedding service,
  adapters, API semantics, toolchain/Docker/CI, test honesty, docs truth,
  and validity of Gemini's own findings.
- **Rules for every reviewer:** repository invariants named explicitly, a
  verbatim quote required per finding, empty results explicitly allowed,
  and mutations done only in their own git worktrees.
- **Three refuters with distinct lenses:** mechanism reproduction,
  production reachability and severity, and decision context/authorization.
- **A completeness critic** at the end.
- **The lead's direct checks:**
  - the full suite on the branch tip: 1,067 passed, 1 skipped, Python
    3.14.7;
  - the suite under a uv-managed Python 3.12.12 (authorized by the
    operator);
  - a read of production health.

Evidence scripts and outputs are kept in the session scratchpad, not the
repository.

**Counted, not derived:**

- collected tests: `main` 1,021 → branch 1,068 (+47); every per-commit
  count claimed in the branch's docs matches its commit;
- mutation testing: 86 mutants, 45 caught by the full suite, 41 missed
  (36 of them real gaps);
- Python 3.13.14: 1,067 passed, 1 skipped;
- Python 3.12.12: 2 failed, 1,065 passed, 1 skipped.

## Part 1 — Were Gemini's findings right? (checked against `main`)

| Gemini item | Verdict | Why |
|---|---|---|
| §1.1 Ollama probe caches failure forever | **CONFIRMED, UNDERSTATED** | One failed first probe leaves the revision `None` for the process lifetime. Then: 100% `space_mismatch`, zero semantic hits, hybrid silently keyword-only, and health `active` with `failure_count: 0`. The failure logs at DEBUG only. The 6-hourly backfill re-embeds the whole corpus stamped NULL, and the next healthy restart re-embeds it all again. That is two full re-embeds of about 1,060 rows on a CPU-only NAS, per incident. Only health and backfill can trigger it on `main`, because search, save and update embed first. |
| §1.2 empty `IN ()` is a syntax error | NOT A DEFECT | SQLite accepts `IN ()` (checked on 3.50.4 and 3.46.1), and no production caller passes ids |
| §1.3 SQLite variable limit | NOT A DEFECT | The limit is 32,766 on Windows and 250,000 in `python:3.14-slim`, and no production caller builds a variable-length list |
| §2.1 whole-table vector load | CONFIRMED, OVERSTATED | Real, but already recorded and trigger-gated (V3_PLAN; 0007 Stage 2). The load takes 24 ms at 868 rows on the desktop. |
| §2.2 N+1 hydration | CONFIRMED, OVERSTATED | N is 16 by default, costing 0.21 ms |
| §2.3 no persistent HTTP client | CONFIRMED, OVERSTATED | There is no TLS on the LAN. The real cost is client construction, about 13 ms per call on desktop loopback. 0003's trigger had fired. |
| §2.4 rate limiter O(clients) | DECISION RELITIGATION | `main`'s comment records this as a deliberate choice from a 2026-08-15 review |
| §3.1 RLock serialization | DECISION RELITIGATION | This is 0007 Stage 1, and its trigger has not fired |
| §3.2 background embedding | CONFIRMED, OVERSTATED | "5–30 s" has no source. 0006 measured 2.2 s cold and 396 ms warm. |
| §3.3 lock observation "56% of CPU" | NOT A DEFECT | The figure appears nowhere in the cited document, which forbids weakening exact observations. Production metrics are off. |
| §4.1 Python floor | DECISION RELITIGATION | 3.14 is a recorded decision. The host-Python rationale doesn't apply to a `python:3.14-slim` container. |
| §4.2 frozen lock consumption | CONFIRMED | An existing backlog item. The branch's implementation fails that item's acceptance criteria (see F1/F11). |
| §4.3 predecessor-repo `test.db` | OUT OF SCOPE | Other repositories |
| Phase 5 query cache + singleflight | DECISION RELITIGATION | Parked on OC-FT-01 (0012); 0003 says "benchmark only" |
| Phase 6 context budget | DECISION RELITIGATION | A 0011 §4 proposal, and its acceptance criteria are unmet |
| Batch 4 OpenAI optional `dimensions` | CONFIRMED | Real and live-confirmed, but demand-gated in V3_PLAN, which also prescribed the fingerprint/migration decision the branch skipped |
| Batch 4 background embed on update | CONFIRMED, OVERSTATED | Same reasoning as §3.2 |
| Batch 4 write idempotency | DECISION RELITIGATION | 0004 and 0011 §2 require an ADR and an operation-identity design first |
| Batch 5 optimistic concurrency | DECISION RELITIGATION | "edit-revision preconditions are a proposal" (0011) |
| Batch 5 "lock starvation" from batch inserts | NOT A DEFECT | Onboarding never used a whole-batch transaction. The false premise traces to a stale sentence in 0007 on `main`. |
| Batch 6 CLI parity / "docs parity gates" | NOT A DEFECT (false closure) | The gates are three introspection checks (0004), and none was built |

Gemini's audit also missed every open item in fleet-review issue #27,
including the data-destroying `memory_update(content="")`, in files it
edited.

## Part 2 — Are the fixes right? (surviving findings after refutation)

Severity is after refutation. "Reach" means:

- **(a)** production today;
- **(b)** after a merge plus a release;
- **(c)** latent until a configuration change or a client adopts the new
  parameters;
- **(d)** developer, CI or docs only.

| ID | Finding | Severity | Reach |
|---|---|---|---|
| F1 | The Docker image cannot start (above). The fix was verified in a test build: set `UV_PROJECT_ENVIRONMENT=/venv`, add `--no-editable` and `--locked`, pin the uv image, and add an image smoke test before push. | **critical** | (b) |
| F8 | Gated work implemented without evidence or authorization (above). The persistent-client part is *not* a violation. | **high** (process) | (b) |
| F2 | A semantic search served from the new query cache still calls `_record_success()`, so health flips from `degraded` to `active` and logs "provider recovered" while the provider is dead. Health flaps between the two. | medium | (b) |
| F3 | With OpenAI `dimensions` unset, nothing is sent, but the fingerprint still claims 1536. For a model whose native size is not 1536, existing rows stay "current", search filters on the new measured size, and older memories become silently invisible with `stale: 0`. A new test pins the equality. **Remedy note:** fingerprinting only the *requested* value would force a needless full re-embed on default `text-embedding-3-small` installs; encode the *effective* size instead. | medium | (c) |
| F6 | `max_chars` is not a maximum. The first item is always kept, including a 6.5k-char floated pin. Truncation is invisible on `memory_search` and REST search. The budget is applied after paging, so `offset += top_k` skips items permanently. `compact=true` budgets full content while returning previews. Zero or negative means unlimited on MCP but 422 on REST. | medium | (c) |
| F7 | Reads on file-backed stores no longer pass the lock observer. Measured over 45 reads: 40 `read` observations on `main`, 0 on the branch. The design-0010 evidence changes meaning, and the only guarding test uses `:memory:`. | medium | (d) |
| F10 | §1.1 on `main`, described in Part 1 | medium | **(a)** |
| F12 | Python floor lowered to 3.12 against a recorded decision, and incompletely: the badge, `AGENTS.md` and mypy still say 3.14 | medium (process) | (d) |
| F13 | Explicit `id` is unvalidated on MCP and CLI. `id=""` stores a memory, and every later `id=""` save with different content then fails permanently. `id="stats"` and `id="search"` are shadowed by REST routes; `GET /memory/stats` returns 200 with the stats body. `a/b`, and any id longer than 200 characters, is unreachable over REST. A replay with `pinned=True` "succeeds" unpinned. A retry after deletion resurrects the memory. | medium | (c) |
| F21 | Export and import interaction (completeness critic). A single memory saved over MCP or CLI with `id=""` makes every JSON export unimportable: import rejects the whole envelope ("'id' must be a non-empty string"), in both restore modes. SQLite-file backups are unaffected, and the memory can be deleted. | medium | (c) |
| F17 | Test honesty: 41 of 86 mutants escaped. Examples: a cross-thread dirty read, `query_only` dropped, a singleflight waiter blocking forever, a failed flight left registered, cache identity ignoring the revision, background flags ignored, REST and MCP not forwarding the new parameters. One assertion was removed without reason (`test_validation_error_returns_422`; restored, it passes). | medium | (d) |
| F18 | Docs call unmerged, never-CI'd work "✅ SHIPPED", "IMPLEMENTED" and "verified". The single-status-document contract is broken: six stacked checkpoints, revisions 199–202 missing from the table, and a second status document. Follow-ups 5 and 7 were closed inaccurately, and `mcp_server_spec.md` was not updated. | medium | (d) |
| F4 | Optimistic concurrency: never-edited memories serialize `updated_at: null`, and echoing that back means "no check", so stale edits overwrite. A malformed token returns 409, not 422. | low | (c) |
| F5 | The optimistic-concurrency check and the UPDATE are separate autocommit statements, so a second process can interleave | low | (c) |
| F20 | On Python 3.12/Windows (about 1 ms clock steps), two writes share one `updated_at`. The branch's own OCC tests fail there, 2 failed on the full run, and its 3.12 Windows CI leg would be red. That in turn would skip build-and-push on the merge push, hiding F1. Timestamps as revision tokens are fragile; use an integer revision counter. | low | (d) |
| F9 | The 30 s probe cooldown narrows §1.1 but doesn't close it. The root cause is "unknown" conflated with "provider has no revision". On the branch, search now probes *before* embedding, because the cache key calls `model_revision()`. | low | (b) |
| F14 | The stage timers overlap: `candidate_prep_scoring` now contains `vector_loading` | low | (d) |
| F15 | Background embed has five problems. The asyncio path is unreachable. The queue is unbounded. `close()`, called only on the CLI path, doesn't drain, so queued jobs then fail against the closed DB. The CLI flag saves no wall-clock time. Searches queue behind the drain (0.59 s → 2.0–2.5 s on a single-slot fake). On a server shutdown the non-daemon workers do drain the queue, but Docker's default 10 s stop grace period kills a longer backlog, which the next backfill then recovers. | low | (c) |
| F16 | One reader connection per thread, not the "small pool" 0007 specifies. The first read on a new thread is about 2.7× slower, and memory stays held after threads exit (+85 MiB to +243 MiB for 40 idle threads, depending on the run). | low | (b) |
| F11 | `--frozen` doesn't fail on lock drift (only `--locked` does); CI's plain `uv run` can re-lock; the uv version floats; `setup-uv@v5` is a Node 20 action five majors behind | low | (d) |

**Cleared (checked and correct):**

- **Reader/writer split correctness:** read-your-own-writes holds in 5
  scenarios, there are no dirty reads in the current code, idle readers
  don't block checkpoint/TRUNCATE or VACUUM, and there is no deadlock.
- **Scope pushdown** is exactly equivalent to the old filter: 480 combinations, 0
  mismatches.
- **Batch hydration** returns the same results in the same order.
- **Background-embed staleness races** are guarded by the content-hash
  compare-and-swap.
- **Failure accounting:** background failures still count, and failed
  singleflight results are not cached.
- **PEP 758 edits** are mechanical and correct.
- **The persistent client** is thread-safe (httpx documents that), keeps
  its proxy and TLS parity, and measures about 12 ms → 0.8 ms per call on
  loopback.
- **Test counts** are honest.
- **`AGENTS.md`/`CLAUDE.md` parity** holds.
- **The CHANGELOG** being untouched is correct per convention.
- **`uv.lock`** is currently in sync.
- **The design index** rows for 0007/0008/0009 are accurate.

## Part 3 — Disposition per change

| Change | Disposition |
|---|---|
| §1.1 probe retry | **Redo on `main`** as a small reviewed patch. Use a tri-state revision (known / no revision / unknown). While the revision is unknown: don't stamp rows, don't judge currency on the revision, don't filter search by revision, and report "unknown" in health. Add one scheduled re-probe off the request path. `main` also caches a *successful* digest for the process lifetime, so a re-pulled model tag (the case ADR 0005 §1 names) currently goes unnoticed until a restart; the re-probe catches that too. Add an end-to-end test. |
| §2.3 persistent Ollama client | **Salvage** with `close()` actually wired (lifespan and CLI exit) and a guarded `__del__`. Record a NAS p50/p95/p99 before and after. |
| §4.2 frozen lock consumption | **Redo** only if the operator schedules the backlog item. Use the verified Dockerfile remedy, `--locked`, pinned uv and setup-uv versions, `uv lock --check`, and an image smoke test before push. |
| Design index rows (0007–0009) | **Take** as a documentation commit. |
| Line endings | **Don't take the branch's normalization.** It covers docs only; the branch's source files are still CRLF, and `pyproject.toml` gained CR lines. Instead, add a `.gitattributes` rule (`* text=auto eol=lf`) and a renormalize commit on `main`, before the next main→`v4/develop` merge. |
| §2.1 scope pushdown; §3.1 reader/writer split | **Park** until the recorded triggers fire. If they do: a bounded pool, read-lock observation kept, the stage timer fixed, and NAS evidence. |
| Phase 5 cache/singleflight; Phase 6 `max_chars`; explicit-id idempotency; optimistic concurrency | **Park** behind their design gates: OC-FT-01, an ADR on operation identity, and a revision counter. The defects above (F2, F4, F5, F6, F13, F20, F21) are inputs to those designs. |
| §1.2, §1.3, §2.2, §2.4, §3.2 plus Batch 4 update-embed, Batch 5 `add_memories`, Batch 6 CLI flags | **Drop.** They were not defects, they relitigate recorded decisions, or they only follow dropped parameters. |
| §3.3 metrics "overhead fix"; §4.1 Python floor | **Revert or drop.** Both rest on false premises. |
| OpenAI optional `dimensions` | **Redo when demand appears**, with an effective-dimension fingerprint and a migration note, as V3_PLAN follow-up 5 prescribes |
| Branch docs (0013, `REMEDIATION_PLAN.md`, status claims) | **Drop.** This record replaces them. |

**Carrying anything into `v4/develop`.** Measured with `git merge-tree`,
ignoring CR differences:

| Merge into `v4/develop` | Conflicting files | Hunks | Conflict lines |
|---|---|---|---|
| `main` (today) | 3 | 8 | 87 |
| This branch | 7 | 22 | 282 |

The extra conflicts are semantic. `max_chars`, and the code around it, is
built into the pin-float code that ADR 0008 deleted on v4. The Park set is
exactly the conflicting set, so un-parking any of it must target v4's
lift-based ranking. The salvage files (the Ollama and OpenAI adapters, the
Dockerfile and `test.yml`) carry into v4 without conflict.

### What must be run before any piece ships

1. **CI on the exact commit.** A draft PR runs `test.yml`; images are never
   published from PRs. Every leg must be green, and the affected tests must
   actually have run on each leg.
2. **The full suite on Linux, in `python:3.14-slim`.** Every run so far was
   on Windows. The reader-connection tests must use a file-backed database.
3. **An image smoke test before push:** `oc version`, `import openchronicle`,
   and `/health` returning 200 with the expected `build_revision`.
4. **Mutation re-checks.** For each salvaged behavior, reverting it must turn
   its guarding test red.
5. **§1.1:** a fake-Ollama end-to-end test, then a NAS restart in both
   orders. Pass: `model_revision` non-null, `stale` and `space_mismatch`
   both 0, and no manual restart needed.
6. **The persistent client:** NAS p50/p95/p99 before and after, at 1 and 8
   clients, cold and warm, with an Ollama restart mid-run.
7. **Anything on instrumented paths** (reader split, stage timers): design
   0010's gates 3 and 4. The existing 4C/4D evidence does not carry over.
8. **Parked items, measurement or design first:**
   - the 0007 Stage 0 probe before any reader split;
   - 0012 OC-FT-01 before any cache;
   - a design (0011 §4 contract, operation-identity ADR, integer revision
     counter) before `max_chars`, idempotency or optimistic concurrency.

## Part 4 — Pre-existing issues on `main` surfaced by this review

- **The fleet-review issue #27 findings are all still open**, verified
  2026-09-22:
  1. MCP `memory_update(content="")` blanks a memory and deletes its
     embedding;
  2. a background-backfill exception is invisible;
  3. the maintenance loop's false overlap warnings flood the log;
  4. the OpenAI adapter does no response-shape validation.

  Item 1 is the highest-value next fix in the repository.
- **§1.1**, as above: `main`'s only production-reachable defect in this
  review.
- **Mixed line endings, in docs and source.**
  - `main`'s `AGENTS.md` has 535 of 696 lines CRLF, and `V3_PLAN.md`,
    `CODEBASE_ASSESSMENT.md` and others are also mixed.
  - Since `682c68f0` (2026-09-04), several source files on `main` are fully
    CRLF, including `embedding_service.py` and `sqlite_store.py`. The same
    files have no CR at all at `v3.3.0` or on `v4/develop`.
  - Unless CR is ignored, that turns main→v4 merges into whole-file
    conflicts.
  - `.gitattributes` covers only `*.sh`.
- **Log noise on every MCP request.** In stateless mode the FastMCP
  lifespan runs per request, so every MCP request logs "OpenChronicle MCP
  server starting" and "shutting down" at INFO into `OC_LOG_FILE`.
- **Stale records:**
  - 0007 says `onboard_git` holds whole-batch transactions; it doesn't.
  - `docs/integrations/mcp_client_setup.md` says Open WebUI has no native
    MCP; it has since v0.6.31, although not MCP prompts.
  - The fleet Ollama rule says there is no cache-hit signal; Ollama 0.33.3
    added `prompt_eval_cached_count`.

## Part 5 — Housekeeping outside the repository

- **OpenChronicle memories.** The branch's author wrote eight OC milestone
  memories asserting completion on the pre-rename branch name. As of
  2026-09-23 each one starts with a "NOT MERGED" status line pointing to
  this record. Their original text is kept below that line.
- **Shared git-config incidents during this review, all repaired
  2026-09-23.**
  - A reviewer's `git config core.autocrlf false` slip wrote to the shared
    repository config and was unset within seconds.
  - A later "restore", based on a misreading, re-added the setting. It was
    reverted once checkout evidence showed the original config had no local
    `autocrlf`: LF blobs had been checked out as CRLF when the worktree was
    created.
  - Committing this record from a linked worktree ran the test suite inside
    the pre-commit hook. A non-hermetic fixture then reinitialized the real
    repository and flipped `core.bare` to true. That was repaired, and the
    fixture is fixed in the preceding commit.
- **The operator's primary checkout** (`D:/GitHub/openchronicle-mcp`) was
  switched from the branch back to `main` on 2026-09-23. The switch
  mattered because Claude Code auto-loads that checkout's `CLAUDE.md`,
  which, on the branch, asserted the work was "complete, verified, and
  closed out". The eight OC memories agreed, and with both sources wrong in
  the same direction, the session-start cross-check could not catch the
  error.
- **Keep the remote branch** at least until this record lands, because it
  cites the branch's SHAs. Whether to delete it afterwards is the
  operator's call.

## Not covered

- **NAS-side timings.** All latency and memory figures are from the
  Windows desktop or simulated clocks.
- **A real GitHub Actions run of the branch.** None exists.
- **Real container start order at NAS boot.** It decides how often §1.1
  can fire. Partly narrowed: the Docker HEALTHCHECK never probes, and the
  remaining boot trigger is the overdue-backfill tick described under the
  interim control.
- **How often agents repeat exact queries** (the F2 exposure).
- **Whether any non-Claude MCP client** points at production (the F13
  exposure).
