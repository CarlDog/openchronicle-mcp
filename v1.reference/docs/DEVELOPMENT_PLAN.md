# Development Plan (Authoritative)

This is the single development/implementation plan. For status, see `.copilot/project_status.json`.

Updated: 2025-08-11

1) Scope & Non-Goals

- In scope: docs defragmentation, README accuracy, storage/logs git hygiene, minimal CI sanity, keep hexagonal boundaries.
- Non-goals: feature work, performance tuning beyond hygiene, backward-compat layers.

2) Architecture at a Glance

- src/openchronicle/
  - domain/ (pure business logic)
  - application/ (use cases, orchestration)
  - infrastructure/ (adapters: persistence, LLM, memory, performance)
  - interfaces/ (CLI, API, web)
  - shared/ (logging, config, errors)

3) Milestones & Workstreams

- D1 Docs cleanup & defragmentation — Owner: Maintainers — DoD: README+ARCHITECTURE+PLAN aligned; stubs replace duplicates — ETA: 2025-08-13
- D2 Single-source status adoption — Owner: Maintainers — DoD: status only in .copilot/project_status.json — Done
- D3 Authoritative DEVELOPMENT_PLAN.md — Owner: Maintainers — DoD: this file in place; links consistent — ETA: 2025-08-12
- D5 Storage/logs git hygiene — Owner: Maintainers — DoD: .gitignore updated; tracked junk untracked — ETA: 2025-08-11

4) Coding Standards

- Style: Ruff + Black; Import ordering via Ruff isort.
- Typing: incrementally strict; avoid Any in public APIs.
- Docstrings: Google style for public modules/classes/functions.
- Tests: pytest; keep fast running core tests; coverage target 85% when enabled.

5) Testing Strategy

- Unit, integration, performance, stress organized under tests/.
- Minimal green path locally; full suite in CI once reinstated.

6) Release & Versioning

- Semver 0.y while evolving; breaking changes allowed (internal project rule).
- Main branch protected; feature branches for work.

7) Operational Notes

- Logging via `src/openchronicle/shared/logging_system.py`.
- Config under `config/` JSON files; env via .env.example.
- Health: run `pytest -q` fast subset; run `python scripts/phase1_health_check.py` for smoke.

8) Open Risks & Decisions

- Risks: doc drift, CI drift. Mitigate by single-source status and minimal gates.
- Decisions: No legacy paths; remove outdated docs; status centralized in project_status.json.

How to Contribute Today

- Fix a stale doc reference; align README run instructions with main.py and CLI.
- Replace duplicated status pages with two-line stubs referencing `.copilot/project_status.json`.
- Keep hexagonal boundaries (no domain->infrastructure imports).
