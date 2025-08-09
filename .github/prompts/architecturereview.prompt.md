---
mode: ask
---
ROLE: You are a no-nonsense senior Python architect auditing this repository’s architecture for maintainability, clarity, and debuggability. Treat the current VS Code workspace as the project root.

GOAL: 
1) Critically assess the codebase architecture using folder/file layout and key config files.
2) Identify gaps against modern Python best practices.
3) Propose a target-state architecture and naming scheme.
4) Produce a phased implementation plan with checklists and concrete deliverables we can execute.

SCOPE & CONSTRAINTS:
- Focus on structure and interfaces first (folders, filenames, package boundaries, entry points, configs, tests, CI). Skim file headers only when structure is ambiguous; do NOT deep-read every file.
- Ignore vendor/build caches: .git, .venv, venv, __pycache__, .mypy_cache, .ruff_cache, node_modules, dist, build, .pytest_cache.
- Prefer the modern “src/” layout unless there’s a strong reason otherwise.
- Assume Python 3.11+ and pytest.
- Recommendations must be toolable/automatable and low-drama to adopt.

DELIVERABLE #1 — ARCHITECTURE AUDIT
Produce the following sections:

A) Inventory (Actual)
- A sanitized directory tree (depth 4 max) showing packages, modules, tests, scripts, configs, data/assets, Docker/CI files.
- Identify app entry points (CLI, API server, workers), any frameworks used (if obvious), and cross-cutting dirs (utils/helpers).

B) Findings (Critical Analysis)
- Misplaced responsibilities, leaky boundaries, circular-import risk areas, “god modules,” and naming inconsistencies.
- Packaging issues (flat vs nested), missing __init__.py in packages, hidden coupling via relative imports, mutable global state.
- Testing gaps: missing tests folder or inconsistent naming, unit vs integration split, fixtures/parametrization opportunities.
- Config/logging/error-handling issues (e.g., ad-hoc env reads, print debugging, inconsistent exception handling).
- CI/CD gaps (lint/format/type/pytest not enforced), missing coverage threshold, missing release/versioning process.

C) Gap Check vs Best Practices (brief table)
Rows: Packaging, Naming, Imports, Typing, Logging, Config Management, Error Handling, Testing, Docs, CI, Release/Versioning.
Columns: Current, Risk/Impact, Recommendation, Effort (S/M/L).

DELIVERABLE #2 — TARGET-STATE BLUEPRINT
Provide a proposed “to-be” layout and standards:

1) Proposed Directory Structure (code block, tree style)
- Prefer src/ layout with clear layers (domain, services/use-cases, adapters/interfaces, infra), plus tests/, scripts/, docs/, ci/.
- Include example package/module names in snake_case; no CamelCase files; tests mirror src package names.

2) Naming & Boundaries
- Rules for files, packages, and test modules; where to place CLI/ASGI/Wsgi entry points; where adapters live (db, http, fs).
- Import rules (absolute over relative), guidance to prevent circular deps, dependency direction (domain inward).

3) Configuration & Secrets
- Centralized settings (pydantic-settings or dynaconf), .env support, twelve-factor alignment, prod overrides, secret handling.

4) Logging & Error Handling
- stdlib logging via dictConfig, module-level loggers, correlation IDs; exception taxonomy (BaseAppError -> specific errors).

5) Typing & Style
- mypy strictness tiered (start: --strict optional set, then ratchet); ruff + black + isort via pyproject.toml, single source of truth.

6) Testing Strategy
- pytest layout (unit vs integration), fixtures, param cases, coverage ≥ 85% gate, minimal golden files policy, snapshot rules.

7) Docs & Decisions
- docs/ARCHITECTURE.md outline, ADRs (Architecture Decision Records) template and when to write one.

8) CI/CD Skeleton
- GitHub Actions (or equivalent) stages: lint/format check, type check, test, coverage upload, build/package, release tagging.

DELIVERABLE #3 — PHASED IMPLEMENTATION PLAN
Provide a concrete, low-risk migration plan with checklists:

Phase 0 — Baseline (Quick Wins)
- Add pyproject.toml with ruff/black/isort/mypy configs
- Add .pre-commit-config.yaml (hooks: ruff, black, isort, trailing-whitespace, end-of-file-fixer)
- Add minimal GitHub Actions CI (lint + test + type)
- Add docs/ARCHITECTURE.md scaffold and ADR template
- Define logging config and a BaseAppError

Phase 1 — Structure & Naming
- Adopt src/ layout (or justify not doing so), move packages, add __init__.py, normalize names, separate adapters/domain/services.
- Introduce settings module and remove ad-hoc env reads.

Phase 2 — Testing & Typing
- Create tests mirror tree, add fixtures, raise coverage gate to 75% then 85%
- Enable mypy on new/critical modules; add type hints on hot paths.

Phase 3 — Hardening & CI
- Enforce import layering with ruff rules; add bandit if needed
- Expand CI (matrix, coverage gates, cache)
- Add Makefile/justfile tasks: fmt, lint, type, test, cov, run, clean.

For each phase, provide:
- Checklist (markdown checkboxes)
- Estimated effort (S/M/L)
- Risks and mitigations
- Success criteria (“Definition of Done”)

DELIVERABLE #4 — READY-TO-GENERATE ARTIFACTS (TEMPLATES)
Output skeletons we can commit immediately:
- pyproject.toml (ruff/black/isort/mypy configured)
- .pre-commit-config.yaml
- .github/workflows/ci.yml (lint+type+test+coverage)
- docs/ARCHITECTURE.md (scaffold)
- docs/adr/0001-template.md
- CONTRIBUTING.md and CODEOWNERS (placeholder)
- Makefile or justfile with common dev tasks

OUTPUT FORMAT REQUIREMENTS:
- Use clear section headers exactly as named above.
- Include the directory trees and config files as code blocks.
- Keep recommendations actionable and specific (rules, paths, commands).
- Be candid. If something is messy, say so and propose the clean fix.

BEGIN NOW with the Inventory and Findings, then proceed through all deliverables.
