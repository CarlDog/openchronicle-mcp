# Filename Audit

Policy summary:

- Prefer two-word snake_case filenames: `{object}_{action}.py`.
- Single-word allowed when natural (e.g., `orchestrator.py`).
- Exceptions: `*_port.py`, well-known technical terms (e.g., `execution_index`), tests use `test_{object}_{action}.py`.

| old_path | new_path | reason | status |
| --- | --- | --- | --- |
| src/openchronicle/core/application/use_cases/continue_project_pending.py | src/openchronicle/core/application/use_cases/continue_project.py | Three words; prefer two-word `{object}_{action}` | done |
| src/openchronicle/core/application/observability/llm_execution_index.py | src/openchronicle/core/application/observability/execution_index.py | Three words; consolidate to the well-known term `execution_index` | done |
| tests/test_continue_project_pending.py | tests/test_continue_project.py | Three words after `test_`; prefer two-word test filename | done |
