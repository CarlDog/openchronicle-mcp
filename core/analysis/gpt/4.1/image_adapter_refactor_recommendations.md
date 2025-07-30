# Refactoring & Deduplication Recommendations: image_adapter.py

## Overview
`image_adapter.py` provides a plugin-style system for image generation, supporting multiple providers (OpenAI DALL-E, Stability AI, local models, mock). It includes request/result dataclasses, abstract and concrete adapters, a registry, and example usage.

## Key Observations
- **Multiple Responsibilities**: The file mixes dataclasses, abstract/concrete adapters, registry logic, and example/test code.
- **Repeated Patterns**: Prompt building, error handling, and adapter registration logic are repeated across adapters and registry.
- **Provider-Specific Logic**: Each adapter handles provider-specific configuration and API calls, but some logic (e.g., prompt formatting, error handling) could be shared.
- **Registry Logic**: Adapter registration and fallback logic are tightly coupled to the registry class.
- **Mock Adapter**: Mock image generation logic is embedded and could be separated for clarity.
- **Testing/Example Code**: Example usage is included in the main file, which could be moved to a dedicated test module.

## Refactoring Opportunities
1. **Extract Dataclasses & Enums**
   - Move `ImageGenerationRequest`, `ImageGenerationResult`, and enums to a separate module for reuse.

2. **Centralize Prompt & Error Handling**
   - Create utility functions for prompt formatting and error handling to reduce duplication across adapters.

3. **Modularize Provider Adapters**
   - Move each provider adapter (OpenAI, Mock, etc.) to its own module/file for clarity and maintainability.

4. **Registry Improvements**
   - Refactor registry logic to support dynamic loading and configuration of adapters.
   - Move fallback logic to a utility/helper module.

5. **Separate Testing/Example Code**
   - Move example usage and test code to a dedicated test module or script.

## Example Extraction Plan
- `image_adapter.py` (core logic, entry points)
- `image_types.py` (dataclasses and enums)
- `image_providers/` (provider-specific adapters)
- `image_registry.py` (adapter registry and fallback logic)
- `image_utils.py` (prompt formatting, error handling)
- `tests/test_image_adapter.py` (testing and example usage)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor provider adapters and registry logic for maintainability.
3. Move dataclasses/enums and test code to separate modules.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
