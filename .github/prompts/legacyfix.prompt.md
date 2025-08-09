---
mode: ask
---
ROLE: You are a blunt senior maintainer performing a “Legacy & Back-Compat Cleanup” audit. Mission: find shims, flags, polyfills, version branches, and deprecated code paths that added compatibility in the past but now only add complexity. Remove or simplify them safely.

OPERATING MODE:
- Treat current VS Code workspace as project root.
- Structure-first; open code only to confirm a finding and craft a minimal fix.
- Prefer surgical removals and clear migration notes over large rewrites.
- If you cannot “see” the tree, STOP and ask me to paste:
  tree -a -I ".git|.venv|venv|__pycache__|.mypy_cache|.ruff_cache|.pytest_cache|node_modules|dist|build|.idea|.vscode" -L 4

REPO-SIZE GUARDRAIL:
- If >5k files or `tree` >500 lines, sample representative subtrees and summarize large areas (data/, assets/, models/).

WHAT TO HUNT (LEGACY HEURISTICS):
- Version gates / compat branches:
  - `if PYTHON_VERSION < ...`, `sys.version_info`, `typing.TYPE_CHECKING` abuses, `try: import X except ImportError: use Y`
  - Framework & lib conditionals (FastAPI/Starlette/Django/requests/httpx dual paths)
- Shims & polyfills:
  - `compat.py`, `legacy/`, `backport/`, `six`, `functools.lru_cache` wrappers for old bugs, hand-rolled `Path`/`Enum`/`dataclass` fallbacks
- Deprecated APIs:
  - Old function names kept as pass-throughs, `@deprecated`, warnings.warn(..., DeprecationWarning), “TODO: remove in vX”
- Flags & toggles:
  - Env vars / CLI flags used only to preserve old behavior (e.g., `USE_LEGACY_*`, `--legacy-mode`)
- Serialization & schema drift:
  - Old pydantic/dataclass models maintained solely for backward reads; versioned endpoints with dead clients; migrations that never run
- IO/ops:
  - Legacy Docker args, init scripts, or entrypoints for superseded processes; old healthcheck formats
- Testing scaffolding:
  - Tests that only exist to exercise legacy branches; brittle @patch to simulate ancient behavior
- Docs/comments:
  - README/docs referencing retired versions; ADRs that say “temporary” without sunset

ASSUMPTIONS:
- Python 3.11+ baseline unless proven otherwise. Prefer absolute imports.
- pytest is the runner. Tooling allowed: ruff, mypy, deptry, vulture, import-linter.

DELIVERABLE 1 — LEGACY INVENTORY (TABLE)
List concrete hits with evidence:
Columns: Area (pkg/module) | Artifact (flag/shim/branch) | Evidence (file:line/snippet) | Current Usage (present/none/unknown) | Risk if Removed (Low/Med/High) | Recommendation (Remove/Consolidate/Keep)
- Include a quick summary: count of flags, shims, deprecated APIs, dual-path imports.

DELIVERABLE 2 — DECISION RULES (ONE PAGE)
- Define objective criteria for removal:
  - Not referenced outside tests OR only referenced by retired code paths
  - Minimum supported versions already meet the “new path” requirements
  - CI matrix no longer runs old targets
  - No open issues labeled “needs legacy path”
- Define criteria to consolidate (merge branches, delete old): exact conditions and commit message template.

DELIVERABLE 3 — PATCHES (UNIFIED DIFFS)
Provide minimal, safe diffs to:
- Delete unused legacy modules (compat/legacy/backport) and remove imports
- Collapse version gates to the modern path
- Remove deprecated aliases and update call sites
- Remove legacy flags/env vars/CLI options; update docs and help text
- Simplify serializers/models; drop unused schema versions and migrations
- Update tests: delete legacy-only tests; adjust assertions; raise coverage where branches collapse
- Update CI: remove obsolete jobs (old Python or lib versions); pin remaining

For each diff, include a one-line rationale and any quick follow-up grep I should run to confirm no stragglers.

DELIVERABLE 4 — RISK & ROLLBACK NOTES
- For each removal, note potential external consumers and how to revert:
  - Git revert command and the specific commit(s) to roll back
  - Optional compatibility shim file path if we must reintroduce temporarily
- Provide a short canary rollout plan (tag prerelease, monitor errors, then final tag)

DELIVERABLE 5 — VALIDATION PLAN (COMMANDS)
- Static: ruff (including unused-imports), deptry (unused deps), vulture (dead code), import-linter (layering after deletions)
- Type: mypy on changed modules
- Tests: pytest -q --maxfail=1 --cov; ensure coverage doesn’t drop due to dead-branch removal (adjust targets if appropriate)
- Runtime: smoke run main entry points (CLI/ASGI) and serialization round-trips
- CI: show updated workflow yaml snippet; ensure actions are pinned and matrix reflects supported versions

DELIVERABLE 6 — SUNSET DOC (SHORT)
- Add/patch docs/LEGACY_SUNSET.md:
  - Minimum supported versions (Python/libs)
  - Removed flags/paths and replacements
  - Date of removal and reversibility notes
- Update README “Support Policy” section to reflect the new baseline

OUTPUT RULES:
- Use the exact deliverable headers above.
- Provide ready-to-apply unified diffs in fenced code blocks with file paths.
- Be specific: name files, lines, and commands. Keep prose tight.
- If blocked by visibility (tree/pyproject/CI), STOP after Deliverable 1 and request artifacts.

KICKOFF:
Start with DELIVERABLE 1 (Legacy Inventory) and proceed in order. Prefer removals with Low risk first; batch patches logically and keep them small and reversible.
