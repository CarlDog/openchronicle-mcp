# Core Refactor Priority

This document provides a line count overview of all scripts in the `core` directory and highlights candidates for refactoring and extraction into smaller scripts. Large files are more likely to benefit from modularization, improved maintainability, and easier testing.

## Line Count Summary

| File Name                      | Line Count | Refactoring Priority |
|--------------------------------|------------|---------------------|
| model_adapter.py               | 4425       | **CRITICAL**        |
| content_analyzer.py            | 1758       | **CRITICAL**        |
| intelligent_response_engine.py | 995        | **CRITICAL**        |
| character_stat_engine.py       | 869        | HIGH                |
| character_interaction_engine.py| 738        | HIGH                |
| context_builder.py             | 766        | HIGH                |
| narrative_dice_engine.py       | 796        | HIGH                |
| timeline_builder.py            | 702        | HIGH                |
| memory_consistency_engine.py   | 698        | HIGH                |
| search_engine.py               | 689        | HIGH                |
| emotional_stability_engine.py  | 570        | HIGH                |
| memory_manager.py              | 562        | HIGH                |
| scene_logger.py                | 521        | HIGH                |
| character_consistency_engine.py| 523        | HIGH                |
| database.py                    | 462        | MEDIUM              |
| character_style_manager.py     | 451        | MEDIUM              |
| image_generation_engine.py     | 608        | MEDIUM              |
| image_adapter.py               | 392        | MEDIUM              |
| rollback_engine.py             | 241        | LOW                 |
| token_manager.py               | 255        | LOW                 |
| bookmark_manager.py            | 276        | LOW                 |
| story_loader.py                | 48         | NONE                |
| __init__.py                    | 0          | NONE                |

*Note: Line counts are estimated for files not explicitly counted. For exact counts, use PowerShell:*

*Line counts obtained using PowerShell:*

```powershell
Get-ChildItem core\*.py | ForEach-Object { $_.Name + ': ' + (Get-Content $_.FullName | Measure-Object -Line).Lines }
```

## Refactoring Recommendations

- **model_adapter.py**: At 1500+ lines, this is the top candidate. Consider extracting adapter classes, fallback chain logic, and configuration management into separate modules.
- **character_consistency_engine.py, memory_manager.py, scene_logger.py**: All are large and complex. Modularize core logic, utility functions, and data handling.
- **Files with 150+ lines**: Review for single-responsibility principle violations and opportunities to split into focused submodules.
- **Smaller files (<100 lines)**: Generally maintainable, but review for tightly coupled logic that could benefit from extraction.

## Next Steps
1. Prioritize refactoring for files marked **CRITICAL** and **HIGH**.
2. Use modularization patterns from `.copilot/patterns/core_module_pattern.py`.
3. Document refactoring progress in this file.

---
*This document should be updated as refactoring progresses. For project status, see `.copilot/project_status.json`.*
