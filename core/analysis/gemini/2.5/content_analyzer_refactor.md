# Refactoring and Deduplication Analysis for `content_analyzer.py`

**File:** `core/content_analyzer.py`
**Line Count:** 1758
**Refactoring Priority:** CRITICAL

## 1. Executive Summary

The `ContentAnalyzer` class has grown to be a large, multi-functional component responsible for a wide range of tasks, from real-time user input analysis to offline storypack importing. This has led to a violation of the Single Responsibility Principle, making the code harder to maintain, test, and extend.

The primary recommendation is to decompose the `ContentAnalyzer` into smaller, more focused classes, each responsible for a distinct area of functionality. This will improve modularity, reduce complexity, and allow for more targeted testing.

## 2. Key Refactoring Opportunities

### 2.1. Separation of Concerns: `ContentAnalyzer` vs. `StorypackImporter`

The `ContentAnalyzer` currently handles both runtime analysis of user input and one-time analysis of imported storypack content. These are distinct use cases with different requirements.

*   **Recommendation:** Create a new `StorypackImporter` class to encapsulate all the logic related to importing and analyzing storypack content. This includes methods like `extract_character_data`, `extract_location_data`, `extract_lore_data`, and `analyze_content_category`.

*   **Benefits:**
    *   Separates online and offline processing.
    *   Simplifies the `ContentAnalyzer` class, allowing it to focus solely on runtime analysis.
    *   Improves code organization and readability.

### 2.2. Model Selection Logic: `ModelSelector`

The logic for selecting the best model for a given task is complex and spread across multiple methods (`get_best_analysis_model`, `_check_model_suitability`, `_provide_model_guidance`). This logic could be centralized and made more reusable.

*   **Recommendation:** Create a `ModelSelector` class responsible for all aspects of model selection. This class would take the content type and system state as input and return the optimal model. It would also handle the logic for providing user guidance when no suitable models are found.

*   **Benefits:**
    *   Encapsulates model selection logic in one place.
    *   Simplifies the `ContentAnalyzer` class.
    *   Makes the model selection logic easier to test and extend.

### 2.3. Transformer Integration: `TransformerService`

The integration of the `transformers` library is currently handled directly within the `ContentAnalyzer`. This could be abstracted to a separate service.

*   **Recommendation:** Create a `TransformerService` class to manage the initialization and execution of all transformer-based models (NSFW, sentiment, emotion). The `ContentAnalyzer` would then call this service for transformer-based analysis.

*   **Benefits:**
    *   Isolates the `transformers` library dependency.
    *   Simplifies the `ContentAnalyzer` class.
    *   Makes it easier to add, remove, or change transformer models without modifying the `ContentAnalyzer`.

## 3. Code Deduplication Opportunities

### 3.1. Data Extraction Methods

The methods `extract_character_data`, `extract_location_data`, and `extract_lore_data` are nearly identical. They all follow the same pattern: build a prompt, call the model, and parse the JSON response.

*   **Recommendation:** Create a generic `_extract_data(content: str, prompt_template: str) -> Dict[str, Any]` method. The specific `extract_*` methods would then call this generic method with the appropriate prompt template.

*   **Benefits:**
    *   Reduces code duplication by over 100 lines.
    *   Simplifies the addition of new data extraction types.

### 3.2. JSON Parsing and Error Handling

The code for parsing JSON responses from the model, including error handling and cleanup, is repeated in multiple places.

*   **Recommendation:** Create a utility function `parse_json_response(response: str) -> Dict[str, Any]` that handles JSON parsing, including the regex-based cleanup for malformed responses.

*   **Benefits:**
    *   Centralizes error handling for JSON parsing.
    *   Reduces code duplication.

## 4. Proposed Class Structure

```python
# core/analysis/content_analyzer.py
class ContentAnalyzer:
    def __init__(self, model_selector: ModelSelector, transformer_service: TransformerService):
        # ...
    def analyze_user_input(self, user_input: str, story_context: Dict[str, Any]) -> Dict[str, Any]:
        # ...

# core/analysis/model_selector.py
class ModelSelector:
    def __init__(self, model_manager):
        # ...
    def get_best_analysis_model(self, content_type: str) -> str:
        # ...
    def provide_model_guidance(self, content_type: str):
        # ...

# core/analysis/transformer_service.py
class TransformerService:
    def __init__(self):
        # Initialize transformer models
    def analyze_content(self, text: str) -> Dict[str, Any]:
        # Run text through all transformer models
        # ...

# core/importing/storypack_importer.py
class StorypackImporter:
    def __init__(self, model_selector: ModelSelector):
        # ...
    def extract_character_data(self, content: str) -> Dict[str, Any]:
        # ...
    def extract_location_data(self, content: str) -> Dict[str, Any]:
        # ...
    def _extract_data(self, content: str, prompt_template: str) -> Dict[str, Any]:
        # ...
```

## 5. Next Steps

1.  **Create New Files:** Create the new files for `ModelSelector`, `TransformerService`, and `StorypackImporter`.
2.  **Migrate Code:** Move the relevant code from `ContentAnalyzer` to the new classes.
3.  **Refactor `ContentAnalyzer`:** Refactor `ContentAnalyzer` to use the new classes.
4.  **Update Imports:** Update all necessary imports to reflect the new file structure.
5.  **Test:** Run existing tests and create new tests for the new classes to ensure all functionality is preserved.
