# Refactoring & Deduplication Recommendations: token_manager.py

## Overview
`token_manager.py` implements a `TokenManager` class for managing token usage, model selection, scene continuation, and usage statistics. It integrates with the dynamic model plugin system and provides smart model switching.

## Key Observations
- **Single Class Structure**: All logic is contained in one class, which is good for encapsulation but could be split for clarity and maintainability.
- **Repeated Patterns**: Tokenizer retrieval, model selection, and token estimation logic are repeated in several methods.
- **Model Config Access**: Accessing model configs and adapter info is performed in multiple places.
- **Continuation Logic**: Scene continuation and truncation detection could be modularized for reuse.
- **Usage Tracking**: Token usage tracking and statistics are tightly coupled to the main class.
- **Logging**: Logging is performed throughout, but could be centralized for consistency.

## Refactoring Opportunities
1. **Extract Tokenizer Utilities**
   - Move tokenizer retrieval and token estimation to a utility module/class.
   - Centralize error handling for tokenizer failures.

2. **Modularize Model Selection**
   - Create a dedicated model selection utility for optimal model picking and switching.
   - Reduce duplication in model config access and filtering.

3. **Split Continuation Logic**
   - Move scene continuation and truncation detection to a separate module/class.
   - Make continuation cache management reusable.

4. **Centralize Usage Tracking**
   - Extract token usage tracking and statistics to a dedicated analytics/helper module.

5. **Logging Consistency**
   - Centralize logging calls and ensure all major actions/events are logged in a uniform way.

## Example Extraction Plan
- `token_manager.py` (core class, entry points)
- `token_utils.py` (tokenizer and estimation)
- `model_selection.py` (model selection and switching)
- `scene_continuation.py` (continuation and truncation logic)
- `token_analytics.py` (usage tracking and statistics)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor model selection and continuation logic for maintainability.
3. Move analytics/statistics to a separate module.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
