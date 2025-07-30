# Refactoring & Deduplication Recommendations: image_generation_engine.py

## Overview
`image_generation_engine.py` manages image generation requests, model selection, prompt formatting, and result handling for visual assets. It integrates with external image adapters and supports scene/character-based image creation.

## Key Observations
- **Single Class Structure**: All image generation logic is contained in one class, mixing request handling, prompt formatting, and result processing.
- **Repeated Patterns**: Prompt formatting and adapter selection logic are repeated in several methods.
- **Adapter Access**: Accessing image adapters and configs is performed in multiple places.
- **Result Handling**: Image result processing and error handling could be modularized for reuse.
- **Usage Tracking**: Image generation statistics and analytics are tightly coupled to the main class.
- **Logging**: Logging is performed throughout, but could be centralized for consistency.

## Refactoring Opportunities
1. **Extract Prompt Formatting Utilities**
   - Move prompt formatting and validation to a utility module/class.
   - Centralize error handling for prompt failures.

2. **Modularize Adapter Selection**
   - Create a dedicated adapter selection utility for optimal image model picking and switching.
   - Reduce duplication in adapter config access and filtering.

3. **Split Result Handling Logic**
   - Move image result processing and error handling to a separate module/class.
   - Make result cache management reusable.

4. **Centralize Usage Tracking**
   - Extract image generation usage tracking and statistics to a dedicated analytics/helper module.

5. **Logging Consistency**
   - Centralize logging calls and ensure all major actions/events are logged in a uniform way.

## Example Extraction Plan
- `image_generation_engine.py` (core class, entry points)
- `image_prompt_utils.py` (prompt formatting and validation)
- `image_adapter_selection.py` (adapter selection and switching)
- `image_result_handler.py` (result processing and error handling)
- `image_analytics.py` (usage tracking and statistics)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor adapter selection and result handling logic for maintainability.
3. Move analytics/statistics to a separate module.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
