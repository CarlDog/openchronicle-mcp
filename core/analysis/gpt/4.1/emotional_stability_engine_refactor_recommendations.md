# Refactoring & Deduplication Recommendations: emotional_stability_engine.py

## Overview
`emotional_stability_engine.py` implements an `EmotionalStabilityEngine` class for tracking emotional states, detecting loops, managing cooldowns, and maintaining dynamic character behavior. It uses dataclasses, regex patterns, and provides prompt generation, import/export, and statistics.

## Key Observations
- **Single Class Structure**: All logic is contained in one class, which is good for encapsulation but could be split for clarity and maintainability.
- **Repeated Patterns**: Emotional state tracking, cooldown management, and loop detection logic are repeated in several methods.
- **Dataclass Usage**: EmotionalState, BehaviorCooldown, and LoopDetection dataclasses could be moved to a shared module for reuse.
- **Regex & Pattern Logic**: Loop detection and disruption patterns are embedded and could be modularized.
- **Prompt Building**: Anti-loop prompt generation logic is duplicated and could be centralized.
- **Import/Export Logic**: Data import/export logic is procedural and could be grouped.
- **Statistics & Reporting**: Stats and reporting logic could be extracted to a dedicated analytics/helper class.
- **Error Handling**: Logging and error handling are performed throughout, but could be centralized for consistency.

## Refactoring Opportunities
1. **Extract Dataclasses & Pattern Utilities**
   - Move EmotionalState, BehaviorCooldown, and LoopDetection to a shared module for reuse.
   - Centralize regex and disruption pattern logic in a utility module.

2. **Modularize State & Cooldown Management**
   - Move emotional state and cooldown management to dedicated modules/classes.
   - Centralize error handling for state operations.

3. **Centralize Prompt Generation**
   - Create utility functions for anti-loop and disruption prompt building to reduce duplication.

4. **Group Import/Export Logic**
   - Move import/export logic to a dedicated module/class.

5. **Centralize Statistics & Analytics**
   - Extract statistics and reporting logic to a dedicated analytics/helper module.

## Example Extraction Plan
- `emotional_stability_engine.py` (core class, entry points)
- `emotional_state_types.py` (dataclasses and pattern utilities)
- `emotional_state_manager.py` (state and cooldown management)
- `emotional_prompt_utils.py` (prompt generation)
- `emotional_import_export.py` (import/export logic)
- `emotional_analytics.py` (statistics and reporting)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor state, cooldown, and prompt logic for maintainability.
3. Move import/export and analytics to separate modules.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
