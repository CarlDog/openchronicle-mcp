# Refactoring Analysis for `memory_manager.py`

## 1. Overview

The `memory_manager.py` module is responsible for all aspects of character and world memory within a story. It handles loading, saving, updating, and archiving memory states. The current implementation is a collection of functions that directly interact with a SQLite database via a simple `database.py` abstraction.

While this approach is direct, it suffers from several design flaws that make it rigid, hard to test, and prone to errors. The primary issue is the lack of clear separation between data access, business logic, and data transformation.

## 2. Key Issues and Anti-Patterns

*   **Lack of Abstraction**: The module is essentially a set of free-standing functions that directly perform database operations. There is no central class or abstraction layer to manage the memory state, leading to scattered logic and repeated code (e.g., `load_current_memory` is called by almost every other function).

*   **Mixing Concerns**: The module violates the Single Responsibility Principle (SRP) by mixing several distinct concerns:
    *   **Database Interaction**: Directly calls `execute_query` and `execute_update`.
    *   **Business Logic**: Contains logic for updating character states, managing mood history, and handling rollbacks (e.g., `update_character_memory`, `refresh_memory_after_rollback`).
    *   **Data Transformation/Formatting**: Includes functions that format data specifically for LLM prompts (e.g., `format_character_snapshot_for_prompt`). This presentation logic is tightly coupled with the data access logic.

*   **Procedural, Not Object-Oriented**: The design is procedural. A more object-oriented approach would involve creating classes to represent the core concepts (like `Memory`, `CharacterMemory`) and encapsulating their behavior.

*   **Implicit Schema**: The structure of the `memory` object is implicitly defined and manipulated throughout the functions. There is no single source of truth for the data model, making it difficult to understand and maintain.

## 3. Proposed Refactoring Plan

The refactoring strategy is to introduce clear layers of abstraction using well-known design patterns like the Repository pattern, Service Layer, and dedicated Data Transfer Objects (DTOs) or data models.

### Step 1: Define Clear Data Models

- **Action**: Create dedicated `dataclasses` to represent the structure of the memory objects.
- **New File**: `core/memory_models.py`
- **Contents**:
    - `CharacterMemory` (Dataclass): Contains fields like `traits`, `relationships`, `history`, `voice_profile`, `mood_state`.
    - `WorldState` (Dataclass): Contains fields for global story state.
    - `MemoryFlag` (Dataclass): Represents a single flag.
    - `StoryMemory` (Dataclass): The top-level object containing `characters: Dict[str, CharacterMemory]`, `world_state: WorldState`, `flags: List[MemoryFlag]`, etc.
- **Benefit**: Provides a single source of truth for the data schema, enabling type safety and making the code self-documenting.

### Step 2: Create a Data Access Layer (Repository Pattern)

- **Action**: Create a `MemoryRepository` class to handle all direct database interactions.
- **New File**: `core/memory_repository.py`
- **`MemoryRepository` Class**:
    - Will contain all the SQL queries and calls to `execute_query` and `execute_update`.
    - Methods will be responsible for fetching and persisting the data models (e.g., `get_story_memory(story_id) -> StoryMemory`, `save_story_memory(story_id, memory: StoryMemory)`).
    - It will also handle archiving (`archive_memory_snapshot`).
- **Benefit**: Decouples the business logic from the database implementation. The rest of the application will be unaware of how the memory is stored (SQLite, JSON files, etc.).

### Step 3: Create a Service Layer for Business Logic

- **Action**: Create a `MemoryService` class to contain the core business logic.
- **New File**: `core/memory_service.py`
- **`MemoryService` Class**:
    - Will take the `MemoryRepository` as a dependency in its constructor.
    - Will contain the high-level business logic currently found in functions like `update_character_memory`, `update_world_state`, and `refresh_memory_after_rollback`.
    - It will operate on the data models (`StoryMemory`, `CharacterMemory`), not raw dictionaries.
    - Example method: `update_character(story_id, character_name, updates)`. This method would:
        1.  Call the repository to get the current `StoryMemory`.
        2.  Perform the update logic on the `CharacterMemory` object.
        3.  Call the repository to save the updated `StoryMemory`.
- **Benefit**: Centralizes all business rules into a single, testable layer.

### Step 4: Create a Separate Formatter for Presentation Logic

- **Action**: Create a `MemoryPromptFormatter` class to handle the formatting of memory data for LLM prompts.
- **New File**: `core/memory_prompt_formatter.py`
- **`MemoryPromptFormatter` Class**:
    - Will contain the logic from `format_character_snapshot_for_prompt` and `get_memory_context_for_prompt`.
    - It will take the data models (`CharacterMemory`, `StoryMemory`) as input and produce formatted strings.
- **Benefit**: Separates the presentation logic from the core business logic, adhering to the Single Responsibility Principle.

## 4. New Directory Structure

```
core/
|-- memory_service.py         # High-level business logic
|-- memory_repository.py      # Data access and persistence
|-- memory_models.py          # All dataclasses for memory
|-- memory_prompt_formatter.py# Logic for creating LLM prompts
|-- database.py               # (Existing) Low-level DB connection
```

This refactoring will transform `memory_manager.py` from a collection of procedural functions into a well-structured, multi-layered system that is robust, scalable, and easy to maintain. Each component will have a clear, single responsibility, making the entire system more understandable and testable.
