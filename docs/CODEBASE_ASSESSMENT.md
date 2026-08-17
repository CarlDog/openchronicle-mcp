# OpenChronicle — Codebase Assessment

**The project's single source of truth for current state.** Updated in
the same commit as the work that changes it (standing rule). Release
narrative lives in [CHANGELOG.md](../CHANGELOG.md); the live backlog
lives in [V3_PLAN.md](V3_PLAN.md) (see "Where things live" below); the
v2-era assessment this document once carried is frozen verbatim at
[archive/v2/CODEBASE_ASSESSMENT.md](archive/v2/CODEBASE_ASSESSMENT.md).

**Snapshot date:** 2026-08-17 · **Revision:** 76

## Current state

**v3 is live.** OpenChronicle v3 is a memory database for LLM agents —
persistent semantic + keyword memory with project namespacing, served
over HTTP REST and MCP from one ASGI process. The v2 conversation
engine, LLM providers, plugins, Discord, and assets are gone; v2 is
frozen at `archive/openchronicle.v2` (`bb217d9`).

| Fact | Value |
|---|---|
| Deployed release | `v3.0.0-rc7` (2026-08-17), Portainer stack 151, endpoint 2, port `18000` |
| Deploy verification | `health.package_version` — reports the real release since rc6; also `fts5_active`, `embedding_status`, `maintenance_degraded` |
| Main vs deployed | In sync at rc7. Code goes live only when the stack's `OC_TAG` env moves — a push alone deploys nothing |
| Surface | 18 MCP tools at `/mcp` (stateless streamable-HTTP); REST mirror at `/api/v1/*` (memory, project, system); liveness at `/health`; `oc` CLI |
| Search | Hybrid FTS5 + embedding cosine via RRF (per-call `mode`: hybrid/keyword/semantic; `phrase` exact matching; every result carries a `relevance` block); hybrid falls back to FTS5-only on provider failure, semantic fails loudly; NAS runs `openai` embeddings |
| Security posture | Auth supported, intentionally disabled on the home LAN ([security_posture.md](configuration/security_posture.md)); Host-header allowlists guard both `/mcp` and the REST surface against DNS rebinding |
| Tests | 582 (pytest; per-commit via pre-commit hook and CI) |
| Lint / types | ruff (minor-pinned) + mypy clean; both enforced per commit and in CI |
| Toolchain | Python **3.14+** everywhere — `requires-python`, CI matrix (ubuntu + windows), Dockerfile, ruff/mypy targets. The floor is real: the code uses PEP 758 syntax |
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
- **CLAUDE.md "Current Sprint"** — the in-flight batch only; history
  rolls into the revision table below and the CHANGELOG.
- **[archive/v2/](archive/v2/README.md)** — frozen v2 docs, never
  maintained.

## Known-open items (summary)

- **Phase 9 decommission** — operator-gated destructive checklist
  (`v3.0.0` final tag after rc6 soaks; v2 stack + orphan volume
  deletion on the NAS). Tracked in V3_PLAN's phase tracker.
- Remaining V3_PLAN follow-ups (mcp 2.0 migration, sqlite-vec ceiling,
  offline write-behind sync, dependency audit, lock file). Every
  code-level finding from the 2026-08-15 review is now closed.

## Revision history

Revisions 1-63 belong to the v2 era — see the
[archived assessment](archive/v2/CODEBASE_ASSESSMENT.md). One line per
revision since; details in CHANGELOG.md and git history.

| Rev | Date | What changed |
|---|---|---|
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
