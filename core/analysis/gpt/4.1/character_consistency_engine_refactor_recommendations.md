# Refactoring & Deduplication Recommendations: character_consistency_engine.py

## Overview
`character_consistency_engine.py` implements a `CharacterConsistencyEngine` class for motivation anchoring, trait locking, behavioral auditing, and consistency reporting. It uses dataclasses, enums, and provides prompt generation, violation analysis, and statistics.

## Key Observations
- **Single Class Structure**: All logic is contained in one class, which is good for encapsulation but could be split for clarity and maintainability.
- **Repeated Patterns**: Anchor/trait processing, violation analysis, and prompt generation are repeated in several methods.
- **Dataclass & Enum Usage**: ConsistencyViolation and MotivationAnchor dataclasses, and ConsistencyViolationType enum, could be moved to a shared module for reuse.
- **Prompt Building**: Motivation and fallback prompt generation logic is duplicated and could be centralized.
- **Violation Analysis**: Multiple methods for violation detection could be modularized for extensibility.
- **Statistics & Reporting**: Stats and reporting logic could be extracted to a dedicated analytics/helper class.
- **Error Handling**: Logging and error handling are performed throughout, but could be centralized for consistency.

## Refactoring Opportunities
1. **Extract Dataclasses & Enums**
   - Move ConsistencyViolation, MotivationAnchor, and ConsistencyViolationType to a shared module for reuse.

2. **Centralize Prompt & Anchor Utilities**
   - Create utility functions for prompt building and anchor processing to reduce duplication.

3. **Modularize Violation Analysis**
   - Move violation detection logic to a dedicated module/class for extensibility.

4. **Centralize Statistics & Reporting**
   - Extract statistics and reporting logic to a dedicated analytics/helper module.

5. **Logging Consistency**
   - Centralize logging calls and ensure all major actions/events are logged in a uniform way.

## Example Extraction Plan
- `character_consistency_engine.py` (core class, entry points)
- `character_consistency_types.py` (dataclasses and enums)
- `character_consistency_utils.py` (prompt and anchor utilities)
- `character_violation_analysis.py` (violation detection)
- `character_consistency_analytics.py` (statistics and reporting)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor violation analysis and prompt logic for maintainability.
3. Move dataclasses/enums and analytics to separate modules.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
