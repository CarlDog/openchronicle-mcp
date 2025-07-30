# Refactoring Analysis for `character_style_manager.py`

## Executive Summary

The `character_style_manager.py` module is responsible for maintaining character style consistency across different LLM models. The `CharacterStyleManager` class has grown to handle a wide range of responsibilities, including loading character styles, adapting prompts for different models, selecting models, analyzing tone, and managing consistency scores. This has resulted in a "God Object" that is difficult to maintain, test, and extend.

This refactoring plan aims to decompose the `CharacterStyleManager` class into a more modular and maintainable architecture by applying the **Service Layer**, **Repository**, and **Strategy** design patterns. This will improve separation of concerns, enhance testability, and make the system more extensible.

## Architectural Issues

1.  **God Object Anti-Pattern**: The `CharacterStyleManager` class violates the Single Responsibility Principle (SRP) by managing:
    *   **Data Loading**: Loading character style data from JSON files.
    *   **Prompt Formatting**: Adapting character style prompts for different LLM providers (OpenAI, Anthropic, Ollama).
    *   **Model Selection**: Selecting the best model for a character based on content type and preferences.
    *   **Tone Analysis**: Analyzing character output for tone consistency.
    *   **Consistency Scoring**: Calculating and managing character consistency scores.

2.  **Tight Coupling**: The business logic for style management is tightly coupled with the `ModelManager` and the file system, making it difficult to switch to a different data source or model management system.

3.  **Limited Extensibility**: Adding support for a new LLM provider or a new tone analysis model requires modifying the `CharacterStyleManager` class, which can become complex and error-prone.

## Proposed Refactoring

I propose refactoring the `character_style_manager.py` module into a layered architecture with distinct components for services, repositories, and strategies.

### 1. New Directory Structure

Create a new directory `core/character_style` to house the refactored components:

```
core/
|-- character_style/
|   |-- __init__.py
|   |-- style_service.py            # High-level style management operations
|   |-- style_repository.py         # Data access for character styles
|   |-- prompt_formatter_strategy.py # Strategy for formatting prompts
|   |-- model_selector_strategy.py  # Strategy for selecting models
|   |-- tone_analyzer_strategy.py   # Strategy for analyzing tone
|   |-- models/
|   |   |-- __init__.py
|   |   |-- character_style.py
|-- character_style_manager.py      # Facade for the style management subsystem
```

### 2. Refactoring Steps

#### Step 1: Create Data Models

Create a dedicated data model for `CharacterStyle` in `core/character_style/models/`.

-   **`core/character_style/models/character_style.py`**:
    ```python
    from dataclasses import dataclass, field
    from typing import Dict, List, Any

    @dataclass
    class CharacterStyle:
        style_block: Dict[str, Any] = field(default_factory=dict)
        preferred_models: List[str] = field(default_factory=list)
    ```

#### Step 2: Implement the Style Repository

Create a `StyleRepository` class in `core/character_style/style_repository.py` to handle all data access.

-   **`core/character_style/style_repository.py`**:
    ```python
    from typing import Dict
    from .models.character_style import CharacterStyle

    class StyleRepository:
        def __init__(self, story_path: str):
            self.story_path = story_path

        def load_character_styles(self) -> Dict[str, CharacterStyle]:
            # Logic to load character styles from JSON files
            pass
    ```

#### Step 3: Implement the Prompt Formatter Strategy

Create a `PromptFormatterStrategy` class in `core/character_style/prompt_formatter_strategy.py` to handle prompt formatting.

-   **`core/character_style/prompt_formatter_strategy.py`**:
    ```python
    from .models.character_style import CharacterStyle

    class PromptFormatterStrategy:
        def format_prompt(self, style: CharacterStyle, model_name: str, provider: str) -> str:
            # Logic for formatting prompts based on the provider
            pass
    ```

#### Step 4: Implement the Model Selector Strategy

Create a `ModelSelectorStrategy` class in `core/character_style/model_selector_strategy.py` to handle model selection.

-   **`core/character_style/model_selector_strategy.py`**:
    ```python
    from .models.character_style import CharacterStyle

    class ModelSelectorStrategy:
        def select_model(self, style: CharacterStyle, content_type: str, available_models: list) -> str:
            # Logic for selecting the best model
            pass
    ```

#### Step 5: Implement the Style Service

Create a `StyleService` class in `core/character_style/style_service.py` to orchestrate the different components.

-   **`core/character_style/style_service.py`**:
    ```python
    from .style_repository import StyleRepository
    from .prompt_formatter_strategy import PromptFormatterStrategy
    from .model_selector_strategy import ModelSelectorStrategy

    class StyleService:
        def __init__(self, story_path: str, model_manager):
            self.repository = StyleRepository(story_path)
            self.prompt_formatter = PromptFormatterStrategy()
            self.model_selector = ModelSelectorStrategy()
            self.model_manager = model_manager

        def get_character_style_prompt(self, character_name: str, model_name: str) -> str:
            # Orchestration logic for getting a character style prompt
            pass

        def select_character_model(self, character_name: str, content_type: str) -> str:
            # Orchestration logic for selecting a character model
            pass
    ```

#### Step 6: Refactor the `CharacterStyleManager` Class as a Facade

Update the original `CharacterStyleManager` class to act as a simple facade that delegates calls to the new service.

-   **`core/character_style_manager.py`**:
    ```python
    from .character_style.style_service import StyleService

    class CharacterStyleManager:
        def __init__(self, model_manager, story_path: str):
            self.service = StyleService(story_path, model_manager)

        def get_character_style_prompt(self, character_name: str, model_name: str) -> str:
            return self.service.get_character_style_prompt(character_name, model_name)

        def select_character_model(self, character_name: str, content_type: str = "dialogue") -> str:
            return self.service.select_character_model(character_name, content_type)
    ```

## Benefits of This Refactoring

-   **Improved Separation of Concerns**: The new architecture separates data loading, prompt formatting, model selection, and tone analysis, making the system easier to understand and maintain.
-   **Enhanced Testability**: Each component can be tested independently, allowing for more focused and effective unit tests.
-   **Increased Flexibility**: The system is more flexible and extensible. For example, adding support for a new LLM provider only requires updating the `PromptFormatterStrategy`, without modifying the `StyleService`.
-   **Better Scalability**: The modular design makes it easier to scale and optimize individual components as needed.

This refactoring will result in a more robust, maintainable, and scalable character style management system for OpenChronicle.
