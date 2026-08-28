# OpenChronicle — Codebase Assessment

**The project's single source of truth for current state.** Updated in
the same commit as the work that changes it (standing rule). Release
narrative lives in [CHANGELOG.md](../CHANGELOG.md); the live backlog
lives in [V3_PLAN.md](V3_PLAN.md) (see "Where things live" below); the
v2-era assessment this document once carried is frozen verbatim at
[archive/v2/CODEBASE_ASSESSMENT.md](archive/v2/CODEBASE_ASSESSMENT.md).

**Snapshot date:** 2026-08-28 · **Revision:** 93

## Current state

**v3 is live.** OpenChronicle v3 is a memory database for LLM agents —
persistent semantic + keyword memory with project namespacing, served
over HTTP REST and MCP from one ASGI process. The v2 conversation
engine, LLM providers, plugins, Discord, and assets are gone; v2 is
frozen at `archive/openchronicle.v2` (`bb217d9`).

| Fact | Value |
|---|---|
| Deployed release | `v3.0.0-rc8` code, image tag `61f711b` (2026-08-23), Portainer stack 151, endpoint 2, port `18000` |
| Deploy verification | `health.package_version` — reports the real release since rc6; also `fts5_active`, `embedding_status`, `maintenance_degraded` |
| Main vs deployed | Runtime code is in sync as of 2026-08-23: the query-aware pinned float, `JobState.last_success_at`, the `import --mode merge` warnings, and the git-onboard watermark filter are all live. Main additionally carries the 2026-08-28 documentation/repository-hygiene closeout, which does not ship in the runtime image. Code goes live only when the stack's `OC_TAG` env moves — a push alone deploys nothing |
| Surface | 18 MCP tools at `/mcp` (stateless streamable-HTTP); REST mirror at `/api/v1/*` (memory, project, system); liveness at `/health`; `oc` CLI |
| Search | Hybrid FTS5 + embedding cosine via RRF (per-call `mode`: hybrid/keyword/semantic; `phrase` exact matching; every result carries a `relevance` block); hybrid falls back to FTS5-only on provider failure, semantic fails loudly; matching pins float above the ranking, unmatched ones stay out and unfloated ones still rank; NAS runs `openai` embeddings |
| Security posture | Auth supported, intentionally disabled on the home LAN ([security_posture.md](configuration/security_posture.md)); Host-header allowlists guard both `/mcp` and the REST surface against DNS rebinding |
| Tests | 626 (pytest; per-commit via pre-commit hook and CI) |
| Lint / types | ruff (minor-pinned) + mypy clean; both enforced per commit and in CI |
| Toolchain | Python **3.14+** everywhere — `requires-python`, CI matrix (ubuntu + windows), Dockerfile, ruff/mypy targets. The floor is real: the code uses PEP 758 syntax |
| Dependency resolution | `uv.lock` is tracked for graph inspection, but CI and Docker still install from `pyproject.toml`; frozen lock consumption remains open and reproducibility must not be claimed yet |
| CI | One workflow, three jobs: test matrix → quality (incl. tag↔version guard) → build-and-push (gated on both; amd64 only) |
| Canonical OC project | `fe2ef898-0152-40a4-af97-ed97cc86ca45` on the NAS deployment |
| Coverage measurement | None (deliberate; the test count and per-commit gates are the regression signal) |

Architecture: hexagonal (`domain` → `application` → `infrastructure`,
drivers in `interfaces/`), enforced by tests — see
[architecture/ARCHITECTURE.md](architecture/ARCHITECTURE.md) and
[architecture/MAINTENANCE.md](architecture/MAINTENANCE.md).

## Where things live

- **This file** — current state only. If it isn't true today, it
  doesn't belong here.
- **[CHANGELOG.md](../CHANGELOG.md)** — what shipped in each release,
  rc1 through current.
- **[V3_PLAN.md](V3_PLAN.md)** — mostly historical (the v3 design +
  phase tracker), but two sections are declared **live**: "Post-cutover
  follow-ups" (the backlog) and "Open Questions" 20-22 (Q20/Q21 shipped
  2026-08-17; Q22 heatmaps remains exploratory). The 2026-08-15
  review's punch list is mirrored in OC memory `e22472b8`.
- **`AGENTS.md` / `CLAUDE.md` "Current Sprint"** — the in-flight batch
  only; `AGENTS.md` is canonical and a repository-hygiene test keeps the
  compatibility mirror byte-identical. History rolls into the revision
  table below and the CHANGELOG.
- **[design/](design/)** — numbered design docs, ADRs, and design
  reviews (`NNNN-topic.md`). A design or recommendation here is a
  *proposal* until its phases ship; current state still lives in this
  file.
- **[archive/v2/](archive/v2/README.md)** — frozen v2 docs, never
  maintained.

## Known-open items (summary)

- **Phase 9 decommission** — operator-gated destructive checklist
  (`v3.0.0` final tag after rc6 soaks; v2 stack + orphan volume
  deletion on the NAS). Tracked in V3_PLAN's phase tracker.
- Remaining V3_PLAN follow-ups (mcp 2.0 migration, sqlite-vec ceiling,
  offline write-behind sync, dependency audit, frozen lock consumption,
  the `pyproject.toml` semantic-search overclaim — queued to ride with the
  next change that already earns a redeploy).
  Every
  code-level finding from the 2026-08-15 review is now closed.
- **OpenClaw comparative assessment (2026-08-27)** — identified four
  local retrieval/embedding integrity defects plus one demonstrated
  filtered-recency need; the same review benchmark-gates MMR and keeps
  agent-runtime features out of scope. Findings and dispositions are
  recorded in
  [design/0002-openclaw-memory-review.md](design/0002-openclaw-memory-review.md);
  none is scheduled merely by being documented.
- **Ollama comparative assessment (2026-08-27)** — verified optional
  adapter contract defects, strengthened the proposed composite
  embedding identity with Ollama's manifest digest, and identified
  provider-independent batching, health, and backup-publication patterns.
  Model-runtime breadth remains out of scope. Findings and dispositions
  are recorded in
  [design/0003-ollama-repository-review.md](design/0003-ollama-repository-review.md);
  none is scheduled merely by being documented.
- **NemoClaw comparative assessment (2026-08-28)** — found no competing
  memory-retrieval capability and no reason to adopt its agent/runtime
  stack. The same closeout fixed the agent-instruction authority and six
  current public-fact errors. Portable-envelope validation, git-child
  credential scope, immutable build identity, and broader parity gates
  remain unscheduled; its replay and restore patterns constrain two
  already-planned features. Findings, trigger-gated ideas, and explicit
  non-fits are recorded in
  [design/0004-nemoclaw-repository-review.md](design/0004-nemoclaw-repository-review.md);
  no implementation batch is authorized by the review.

## Revision history

Revisions 1-63 belong to the v2 era — see the
[archived assessment](archive/v2/CODEBASE_ASSESSMENT.md). One line per
revision since; details in CHANGELOG.md and git history.

| Rev | Date | What changed |
|---|---|---|
| 93 | 2026-08-28 | Phase-end audit fix: `core.json`'s `maintenance.jobs` list now MERGES onto the defaults instead of replacing them. A config naming one job used to silently delete the other four — including `db_backup` — and since the entrypoint seeds `/config` from `core.json.example` with `cp -rn`, a stale seeded file would have dropped every job added in any later release, unwarned (the loop only warned on *unknown* names, never missing ones). Omission no longer disables; `"enabled": false` does, as the example already showed. Ordering follows `_DEFAULT_JOBS`, not the file. Documented in MAINTENANCE.md and config_files.md, which had never stated the semantics either way. 632 → 637 tests |
| 92 | 2026-08-28 | Phase-end audit follow-up: the README's Docker badge rendered as a shields.io "404: badge not found", not a Docker badge — the literal hyphen in `openchronicle-mcp` split the label/message/color path. Escaped as `--`, the convention the sibling License badge (`AGPL--3.0`) already used. Verified against shields.io before and after. Documentation only |
| 91 | 2026-08-28 | Phase-end audit fix 3/3: five docs corrected that were wrong about *runtime behavior* — the same class as revision 88's `db_modified_utc`, and this window's systemic theme. `mcp_client_setup.md` told operators `OC_MCP_TRANSPORT=stdio` + `oc serve` disables HTTP (`cmd_serve` never reads that variable; only `python -m openchronicle.interfaces.mcp` does, and `create_app` mounts `/mcp` unconditionally); `oc serve --help` and `cmd_serve`'s docstring advertised `0.0.0.0:18000` when the real defaults are `127.0.0.1:8000` (18000 is the NAS compose host-side mapping); `ARCHITECTURE.md` listed the deleted `BudgetExceededError` and two CLI commands that do not exist (`oc project ...`, `oc health`). All five verified against the code, not against other docs. 632 tests |
| 90 | 2026-08-28 | Phase-end audit fix 2/3: `OC_LOG_LEVEL` can no longer crash-loop the container. `oc serve` passed the raw value into `uvicorn.Config`, which indexes its own `LOG_LEVELS` dict — `OC_LOG_LEVEL=WARN` died with `KeyError: 'warn'`, and under `restart: unless-stopped` that is an indefinite outage from one typo'd Portainer value. New `uvicorn_log_level()` validates against uvicorn's real table (not a local copy), accepts the `WARN`/`FATAL` aliases `logging` defines, and otherwise warns and falls back — matching the fail-soft `configure_root_logger` already applied to the same variable. 620 → 632 tests |
| 89 | 2026-08-28 | Phase-end audit fix 1/3: the `memory_search` MCP tool no longer advertises a parameter it does not have. Its description told the model to pass `include_pinned=false`; that switch exists only on `oc memory search`, and the registered schema exposes only compact/mode/offset/phrase/pinned_limit/project_id/query/tags/top_k (confirmed against a live `list_tools()`). `docs/integrations/mcp_server_spec.md` carried the same claim inside its MCP-surface table. Both now say the switch is CLI-only. Introduced 2026-08-23 with the query-aware pinned float. Documentation only |
| 88 | 2026-08-28 | Deploy-verification guidance corrected in the agent instructions: `health.package_version` is the signal that the new image is running; `db_modified_utc` is not and never was. The store opens `PRAGMA journal_mode = WAL`, so writes land in the `-wal` sidecar and the main DB's mtime only advances on checkpoint — observed live, a memory written at 14:47Z still read `db_modified_utc` 05:26Z a minute later. Missed by revision 87's own deploy-fact sweep. `docs/integrations/mcp_client_setup.md` was checked and already correct. Documentation only |
| 87 | 2026-08-28 | Comparative-review closeout: committed the OpenClaw, Ollama, and NemoClaw assessments; made `AGENTS.md` canonical with a byte-parity guard; corrected verified CLI/MCP/security/config/deploy/README facts; added the design index and a documented post-compaction OC hook; tracked `uv.lock` without claiming frozen build consumption. 626 tests; no runtime-image change |
| 86 | 2026-08-28 | NemoClaw comparative assessment: cloned and pinned the official NVIDIA repository, separated verified OpenChronicle gaps from constraints on existing future work and trigger-gated hardening, recorded agent-runtime non-fits, and prioritized the applicable work. Documentation only |
| 85 | 2026-08-27 | Ollama comparative assessment: pinned the reviewed upstream commit, verified optional-adapter contract defects, strengthened the composite embedding-identity proposal, separated provider-independent hardening from conditional ideas, and recorded model-runtime non-fits. Documentation only |
| 84 | 2026-08-27 | OpenClaw comparative assessment: pinned the reviewed upstream commit, separated immediate OpenChronicle correctness findings from experiments and conditional ideas, recorded explicit non-fits, and linked the research into the live backlog. Documentation only |
| 83 | 2026-08-23 | NAS stack (151) redeployed: `OC_TAG` moved to image `61f711b`, bringing all four undeployed changes (revisions 79-82: query-aware pinned float, `last_success_at`, merge-hazard warnings, watermark filter) live. No code change — deploy only |
| 82 | 2026-08-23 | Git-onboard watermark no longer leaks across devices (cloud-backup design §11.3, closes §13.5): `export_memory` stops emitting the `source=WATERMARK_SOURCE` row, `import_memory` drops it on read in both `merge` and `replace` (covers envelopes written before the export fix), each drop counted as `watermark_dropped` apart from `memory_skipped`. The literal is now a shared constant in `git_onboard.py` so a rename can't silently disable either filter. 625 tests |
| 81 | 2026-08-23 | `oc memory import --mode merge` no longer loses edits silently (cloud-backup design §11.4). Semantics unchanged — it is still a union by id — but `export_memory` now stamps `exported_at`, `import_memory` returns `projects_skipped`/`memory_skipped` alongside the added counts, and merge logs one unconditional warning naming both lossy edges plus a second when the envelope predates the destination's newest `updated_at` (never `created_at` — `onboard_git` sets that from the commit author date). No `format_version` bump. 620 tests |
| 80 | 2026-08-23 | `JobState.last_success_at` — a persisted "when did this job last actually *work*" marker that a job failing every run cannot fake, unlike `last_run_at`. Prerequisite for the cloud-backup staleness alarm (design §6.1); persisted because every push to main bounces the container |
| 79 | 2026-08-23 | Pinned float made query-aware, fixing an rc8 regression: capping a blanket prepend had made pins past the cap unreachable by any query (the ranked query excluded all pinned rows, so the prepend was their only route). Float and visibility are now separate — `search_pinned` is the float query, `exclude_ids` keeps a floated pin out of the ranking, unfloated pins rank normally, and the float policy moved from the store to the application layer. 597 tests |
| 78 | 2026-08-17 | **v3.0.0-rc8 cut + deployed**: the bounded pinned prepend goes live — the rc7 search surface now costs `pinned_limit` (≤10 by default) pins instead of all 85 |
| 77 | 2026-08-17 | Bounded pinned prepend: `pinned_limit` (default 10, newest first, 0 = none) on `memory_search` across MCP/REST/CLI — an unscoped `top_k=2` search against the 85-pin NAS store had returned 87 results; capped-out pins stay excluded from ranking. 589 tests |
| 76 | 2026-08-17 | **v3.0.0-rc7 cut + deployed**: everything on main since rc6 reaches the NAS — Batch E docs/tests, post-review polish, dead-code sweep, embedding-store port + AST boundary guard, and search-surface v2 (relevance / mode / phrase). 582 tests |
| 75 | 2026-08-17 | Search-surface v2 (Q20/Q21 shipped): `search_memory` returns `ScoredMemory` — every result carries `relevance` (channel / rrf_score / semantic_similarity / keyword_rank) on MCP, REST, and CLI; per-call `mode` (keyword bypasses the provider; semantic fails loudly — 422 without a provider, 502 `PROVIDER_ERROR` on failure via a new global handler); `phrase` exact adjacent-token matching on the keyword channel. No `min_confidence` by design (RRF ≠ calibrated confidence). 582 tests |
| 74 | 2026-08-17 | Embedding persistence joins `MemoryStorePort` (EmbeddingService no longer typed against concrete SqliteStore); boundary guard rewritten as an AST scanner — TYPE_CHECKING/function-body/relative imports are now visible, with the two container-token exemptions enumerated; scanner self-tests pin the old holes |
| 73 | 2026-08-17 | Dead-code sweep: four unused error codes + BudgetExceededError deleted; canonical-code test regex hole closed (immediately caught INVALID_HOST); lying CLI flags removed (`oc init --force/--no-templates`, `plugin_dir` kwarg); tests-only helpers deleted (parse_bool/parse_str_list — their ''-is-falsy semantics conflict with empty-means-unset, recorded); `normalize_unit` extracted (the dot-product=cosine invariant); pagination rule folded. 559 tests — the drop is deleted tests of deleted code |
| 72 | 2026-08-16 | Post-review polish: shared health/embed payload builders (parity by construction); caller mistakes stop answering 500 (FK→404, created_at→422, uniform 404 shape); transactional `oc memory import`; rate-limiter idle-key sweep; honest Ollama error codes; `maintenance_degraded` declared |
| 71 | 2026-08-16 | Review Batch E: this SSOT rewrite; v2 archive restored (the Phase 7 move .gitignore swallowed); CHANGELOG created; test-debt pass (CLI smoke, MCP handler gaps, conftest consolidation) |
| 70 | 2026-08-16 | Review Batch D → **v3.0.0-rc6, deployed**: maintenance schedule persistence + burst-proof retention; fail-soft config; Docker dep-layer cache; version single-sourcing + CI tag guard |
| 69 | 2026-08-16 | Review Batch C: onboard_git robustness — ancestry watermark, unreachable-watermark auto-recovery, `branch` param + ref echo, shared CLI/MCP orchestration |
| 68 | 2026-08-16 | Review Batch B: search correctness — dimensions fact-not-claim, model-scoped semantic search, `include_pinned=False` honored |
| 67 | 2026-08-16 | Review Batch A: Python floor `>=3.14`; `context_recent` no-query fix; stateless HTTP; REST Host allowlist; empty-env normalization; CI hygiene; `init-config` zombie deleted |
| 66 | 2026-07-23 | Read-surface + delete-safety batch → **rc5**: required `confirm`, compact projection, bounded onboard_git, bulk delete, health capability signal (18 tools; 433 → 510 tests) |
| 65 | 2026-07-02 | Hardening batch: SQLite RLock serialization, async MCP tools, git-onboard body/URL fixes (→ shipped in rc5) |
| 64 | 2026-05-06..11 | **v3 cutover** (rc1-rc3 same day; turbulent — see [cutover triage](cutover-2026-05-06-triage.md)); rc4 added rate-limit bump + project CRUD |

Undocumented-at-the-time work recovered by the 2026-08-15 review: the
2026-07-29 py3.14 toolchain move and the 2026-07-30 CI-hardening batch
(publish gated on test+quality, hardened Dockerfile, least-privilege
permissions, gitleaks backstop) — both were on main before rc6.
