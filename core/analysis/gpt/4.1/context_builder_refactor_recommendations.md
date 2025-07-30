# Refactoring & Deduplication Recommendations: context_builder.py

## Overview
`context_builder.py` is responsible for assembling narrative context, including scene, character, and environmental data for model input. It handles context aggregation, formatting, and injection of dynamic elements.

## Key Observations
- **Monolithic Class**: All context logic is contained in a single class, mixing context assembly, formatting, and injection.
- **Repeated Aggregation Patterns**: Context aggregation and formatting logic are repeated across methods.
- **Validation & Injection**: Context validation and dynamic injection logic are performed in multiple places.
- **Analytics**: Methods for context analytics and impact could be extracted to a helper class.

## Refactoring Opportunities
1. **Extract Context Aggregation Utilities**
   - Move context aggregation and formatting logic to a dedicated utility/helper module.
   - Use parameterized methods for context updates and checks.

2. **Centralize Validation & Injection**
   - Create utility functions for context validation and dynamic injection.
   - Reduce repeated validation logic.

3. **Split Analytics/Impact Handling**
   - Extract context-driven impact logic to a separate impact handler or callback system.

4. **Analytics Extraction**
   - Move context analytics and impact tracking to a dedicated analytics/helper module.

5. **Improve Documentation & Type Hints**
   - Add/expand docstrings and type hints for all public methods.

## Example Extraction Plan
- `context_builder.py` (core class, entry points)
- `context_utils.py` (aggregation, validation, formatting)
- `context_impact_handler.py` (impact triggers/callbacks)
- `context_analytics.py` (analytics and impact)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor context update and aggregation logic for maintainability.
3. Move analytics/impact handling to separate modules.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
