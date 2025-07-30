# Refactoring & Deduplication Recommendations: character_style_manager.py

## Overview
`character_style_manager.py` implements a `CharacterStyleManager` class for managing character style consistency, tone auditing, and dynamic model selection. It provides style loading, prompt formatting, tone analysis, model switching, and statistics.

## Key Observations
- **Single Class Structure**: All logic is contained in one class, which is good for encapsulation but could be split for clarity and maintainability.
- **Repeated Patterns**: Style formatting, tone history management, and consistency score calculations are repeated in several methods.
- **Model Selection Logic**: Model selection and routing logic are embedded and could be modularized.
- **Prompt Building**: Prompt formatting for different models is handled in multiple methods and could be centralized.
- **Statistics & Anchoring**: Consistency stats and scene anchors logic could be extracted to a dedicated analytics/helper class.
- **Error Handling**: Logging and error handling are performed throughout, but could be centralized for consistency.

## Refactoring Opportunities
1. **Extract Style & Prompt Utilities**
   - Move style formatting and prompt building to a utility module/class.
   - Centralize error handling for style loading and formatting.

2. **Modularize Model Selection**
   - Create a dedicated model selection utility for optimal model picking and switching.
   - Reduce duplication in model config access and filtering.

3. **Split Tone & Consistency Management**
   - Move tone history and consistency score management to a separate module/class.
   - Make scene anchoring logic reusable.

4. **Centralize Statistics & Analytics**
   - Extract statistics and anchoring logic to a dedicated analytics/helper module.

5. **Logging Consistency**
   - Centralize logging calls and ensure all major actions/events are logged in a uniform way.

## Example Extraction Plan
- `character_style_manager.py` (core class, entry points)
- `character_style_utils.py` (style formatting and prompt building)
- `character_model_selection.py` (model selection and routing)
- `character_tone.py` (tone history and consistency management)
- `character_analytics.py` (statistics and anchoring)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor model selection and tone management logic for maintainability.
3. Move analytics/statistics to a separate module.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
