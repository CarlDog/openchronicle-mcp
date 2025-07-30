# Refactoring Analysis for `context_builder.py`

## 1. Overview

The `context_builder.py` module is a critical component responsible for assembling the final prompt that gets sent to the language model. It aggregates data from numerous other "engine" and "manager" modules, including memory, canon, character styles, consistency, emotional stability, and more. It then formats this data into a structured context designed to guide the model's response.

The current implementation is a collection of functions, with `build_context_with_dynamic_models` being the most complex. This function has become a "God Function," orchestrating a dozen different components and containing a large amount of business logic.

## 2. Key Issues and Anti-Patterns

*   **God Function / Monolithic Design**: The `build_context_with_dynamic_models` function is a prime example of a God Function. It directly instantiates and calls upon a dozen different engine and manager classes. This creates extremely high coupling and makes the function very difficult to read, test, and maintain. Any change in a downstream engine's API requires modifying this central function.

*   **Violation of Single Responsibility Principle (SRP)**: The module violates SRP at multiple levels:
    *   The `build_context_with_dynamic_models` function is responsible for data loading, analysis, context generation, token management, and prompt assembly.
    *   The module mixes high-level orchestration with low-level formatting details (e.g., `_build_system_context`, `json_to_readable_text`).

*   **Tight Coupling and Instantiation Chaos**: The function directly instantiates its dependencies (e.g., `content_analyzer = ContentAnalyzer(model_manager)`). This makes it impossible to substitute different implementations for testing (mocking) or for different configurations without changing the code. It also tightly couples the context builder to the specific constructors of its dependencies.

*   **Lack of a Coherent Data Model**: The context is built up as a dictionary of strings (`context_parts`). This is not type-safe and relies on string keys, which can lead to typos and runtime errors. A more robust approach would be to use dedicated data models (e.g., `dataclasses`) to represent the different sections of the context.

## 3. Proposed Refactoring Plan

The refactoring strategy is to apply the **Builder** and **Dependency Injection** design patterns. We will break down the monolithic function into a series of smaller, specialized "builder" components, and a main "director" class will orchestrate them.

### Step 1: Introduce a `Context` Data Model

- **Action**: Create a `dataclass` to represent the final, structured context.
- **New File**: `core/context_models.py`
- **`Context` Class**:
    - Will have fields for each section of the context (e.g., `system: str`, `memory: str`, `canon: str`, `character_style: str`, `emotional_stability: str`, etc.).
    - This provides a clear, type-safe structure for the data being assembled.

### Step 2: Create a `ContextBuilder` Abstract Base Class

- **Action**: Define an abstract base class for all context-building components.
- **New File**: `core/context_builder_interface.py`
- **`ContextBuilder` ABC**:
    - Will define a single method: `build(self, context: Context, story_data: Dict, analysis: Dict) -> Context`.
    - Each concrete builder will implement this method to add its specific part to the `Context` object.

### Step 3: Implement Concrete Builder Classes

- **Action**: Create a separate builder class for each section of the context. Each builder will be responsible for interacting with its corresponding engine or manager.
- **New Directory**: `core/context_builders/`
- **Example Builder Classes**:
    - `SystemContextBuilder(ContextBuilder)`: Builds the system prompt.
    - `MemoryContextBuilder(ContextBuilder)`: Interacts with `MemoryManager` to build the memory section.
    - `CanonContextBuilder(ContextBuilder)`: Interacts with `StoryLoader` to build the canon section.
    - `CharacterStyleBuilder(ContextBuilder)`: Interacts with `CharacterStyleManager`.
    - `EmotionalStabilityBuilder(ContextBuilder)`: Interacts with `EmotionalStabilityEngine`.
    - `ConsistencyBuilder(ContextBuilder)`: Interacts with `CharacterConsistencyEngine`.
    - ...and so on for each engine.
- **Benefit**: Each builder has a single, focused responsibility. They are small, easy to understand, and can be tested in isolation.

### Step 4: Create a `ContextDirector` to Orchestrate the Build Process

- **Action**: Create a `ContextDirector` class that takes a list of builders and orchestrates the context creation process.
- **New File**: `core/context_director.py`
- **`ContextDirector` Class**:
    - Its constructor will accept a list of `ContextBuilder` instances (Dependency Injection).
    - It will have a `construct_context` method that:
        1.  Creates an empty `Context` object.
        2.  Iterates through its list of builders.
        3.  Calls the `build` method on each builder, passing the `Context` object to be progressively filled.
        4.  Returns the final, assembled `Context` object.
- **Benefit**: The director separates the construction process from the final representation. The order and composition of the context can be easily changed by reconfiguring the list of builders passed to the director, without changing the director's code.

### Step 5: Refactor the Main Entry Point

- **Action**: The original `build_context_with_dynamic_models` function will be replaced by a simpler setup function that initializes and runs the director.
- **File**: `core/context_builder.py` (or a new main entry point file)
- **New Logic**:
    1.  Instantiate all necessary engines and managers.
    2.  Instantiate the concrete builder classes, injecting the required engines/managers into their constructors.
    3.  Instantiate the `ContextDirector` with the list of builders.
    4.  Call the director's `construct_context` method.
    5.  Format the final `Context` object into a string for the LLM.

## 4. New Directory Structure

```
core/
|-- context_director.py         # Orchestrates the build process
|-- context_builder_interface.py# Abstract base class for builders
|-- context_models.py           # Dataclasses for context structure
|-- context_builders/
|   |-- __init__.py
|   |-- system_context_builder.py
|   |-- memory_context_builder.py
|   |-- canon_context_builder.py
|   |-- character_style_builder.py
|   |-- emotional_stability_builder.py
|   |-- consistency_builder.py
|   |-- ... (and so on for each context part)
```

This refactoring will transform the `context_builder` from a monolithic function into a highly modular, flexible, and maintainable system that adheres to the Builder and Dependency Injection patterns, significantly improving the overall software architecture.
