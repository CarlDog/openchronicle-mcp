# Refactoring & Deduplication Recommendations: narrative_dice_engine.py

## Overview
`narrative_dice_engine.py` manages narrative dice rolls, probability calculations, and outcome logic for story events. It provides randomization, weighted outcomes, and integrates with scene and character modules.

## Key Observations
- **Single Class Structure**: All dice logic is contained in one class, mixing roll mechanics, probability calculations, and outcome triggers.
- **Repeated Calculation Patterns**: Dice roll and probability logic are repeated across methods.
- **Outcome Handling**: Outcome logic is embedded within roll methods.
- **Validation & Formatting**: Dice validation and formatting are performed in multiple places.
- **Analytics**: Methods for dice analytics and outcome tracking could be extracted to a helper class.

## Refactoring Opportunities
1. **Extract Dice Calculation Utilities**
   - Move dice roll and probability logic to a dedicated utility/helper module.
   - Use parameterized methods for roll and outcome calculations.

2. **Centralize Validation & Formatting**
   - Create utility functions for dice validation and formatting.
   - Reduce repeated validation logic.

3. **Split Outcome Handling**
   - Extract outcome logic to a separate outcome handler or callback system.

4. **Analytics Extraction**
   - Move dice analytics and outcome tracking to a dedicated analytics/helper module.

5. **Improve Documentation & Type Hints**
   - Add/expand docstrings and type hints for all public methods.

## Example Extraction Plan
- `narrative_dice_engine.py` (core class, entry points)
- `dice_utils.py` (roll mechanics, validation, formatting)
- `dice_outcome_handler.py` (outcome triggers/callbacks)
- `dice_analytics.py` (analytics and outcome tracking)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor roll and outcome logic for maintainability.
3. Move analytics/outcome handling to separate modules.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
