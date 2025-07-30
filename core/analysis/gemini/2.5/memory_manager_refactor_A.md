# Refactoring Analysis for `memory_manager.py`

## Executive Summary

The `memory_manager.py` module is responsible for managing the memory state of a story, including character memories, world state, flags, and recent events. The current implementation mixes data access logic with business logic, making it difficult to maintain and test. The module relies on a series of standalone functions that directly interact with the database, leading to code duplication and a lack of clear separation of concerns.

This refactoring plan aims to introduce a more structured architecture by applying the **Service Layer**, **Repository**, and **Data Model** design patterns. This will improve modularity, testability, and the overall maintainability of the memory management system.

## Architectural Issues

1.  **Lack of a Central Service**: The module consists of a collection of functions, making it difficult to manage dependencies and maintain a consistent API. There is no central service to orchestrate the different memory operations.

2.  **Mixing of Concerns**: The functions in `memory_manager.py` mix data access logic (SQL queries) with business logic (e.g., updating character memory, formatting prompts). This violates the Single Responsibility Principle (SRP) and makes the code harder to test and maintain.

3.  **Code Duplication**: The `load_current_memory` function is called repeatedly by other functions, leading to redundant database queries and potential performance issues.

4.  **Limited Extensibility**: Adding new memory types or changing the database schema requires modifying multiple functions, which is error-prone and inefficient.

## Proposed Refactoring

I propose refactoring the `memory_manager.py` module into a layered architecture with distinct components for services, repositories, and data models.

### 1. New Directory Structure

Create a new directory `core/memory` to house the refactored components:

```
core/
|-- memory/
|   |-- __init__.py
|   |-- memory_service.py       # High-level memory operations
|   |-- memory_repository.py    # Data access and database interactions
|   |-- models/
|   |   |-- __init__.py
|   |   |-- memory_state.py
|   |   |-- character_memory.py
|-- memory_manager.py           # Facade for the memory subsystem
```

### 2. Refactoring Steps

#### Step 1: Create Data Models

Create dedicated data models for the memory state and character memory in `core/memory/models/`.

-   **`core/memory/models/memory_state.py`**:
    ```python
    from dataclasses import dataclass, field
    from typing import Dict, List, Any

    @dataclass
    class MemoryState:
        characters: Dict[str, Any] = field(default_factory=dict)
        world_state: Dict[str, Any] = field(default_factory=dict)
        flags: List[Dict[str, Any]] = field(default_factory=list)
        recent_events: List[Dict[str, Any]] = field(default_factory=list)
        metadata: Dict[str, Any] = field(default_factory=dict)
    ```

-   **`core/memory/models/character_memory.py`**:
    ```python
    from dataclasses import dataclass, field
    from typing import Dict, List, Any

    @dataclass
    class CharacterMemory:
        traits: Dict[str, Any] = field(default_factory=dict)
        relationships: Dict[str, Any] = field(default_factory=dict)
        history: List[Any] = field(default_factory=list)
        current_state: Dict[str, Any] = field(default_factory=dict)
        voice_profile: Dict[str, Any] = field(default_factory=dict)
        mood_state: Dict[str, Any] = field(default_factory=dict)
    ```

#### Step 2: Implement the Memory Repository

Create a `MemoryRepository` class in `core/memory/memory_repository.py` to handle all database interactions.

-   **`core/memory/memory_repository.py`**:
    ```python
    from .models.memory_state import MemoryState

    class MemoryRepository:
        def __init__(self, story_id: str):
            self.story_id = story_id

        def get_current_memory(self) -> MemoryState:
            # Database logic to load the current memory state
            pass

        def save_current_memory(self, memory_state: MemoryState):
            # Database logic to save the current memory state
            pass

        def archive_memory_snapshot(self, scene_id: str, memory_state: MemoryState):
            # Database logic to archive a memory snapshot
            pass
    ```

#### Step 3: Implement the Memory Service

Create a `MemoryService` class in `core/memory/memory_service.py` to orchestrate the different memory operations.

-   **`core/memory/memory_service.py`**:
    ```python
    from .memory_repository import MemoryRepository
    from .models.memory_state import MemoryState
    from .models.character_memory import CharacterMemory

    class MemoryService:
        def __init__(self, story_id: str):
            self.repository = MemoryRepository(story_id)

        def get_memory_state(self) -> MemoryState:
            return self.repository.get_current_memory()

        def update_character_memory(self, character_name: str, updates: dict) -> MemoryState:
            # Business logic for updating character memory
            pass

        def get_character_memory_snapshot(self, character_name: str, format_for_prompt: bool = True) -> dict:
            # Business logic for getting a character memory snapshot
            pass

        def refresh_memory_after_rollback(self, target_scene_id: str) -> MemoryState:
            # Business logic for refreshing memory after a rollback
            pass
    ```

#### Step 4: Refactor the `memory_manager.py` Module as a Facade

Update the `memory_manager.py` module to act as a simple facade that delegates calls to the new `MemoryService`.

-   **`core/memory_manager.py`**:
    ```python
    from .memory.memory_service import MemoryService

    def load_current_memory(story_id):
        service = MemoryService(story_id)
        return service.get_memory_state()

    def save_current_memory(story_id, memory_data):
        service = MemoryService(story_id)
        service.save_current_memory(memory_data)

    def update_character_memory(story_id, character_name, updates):
        service = MemoryService(story_id)
        return service.update_character_memory(character_name, updates)

    # ... other functions delegating to the service
    ```

## Benefits of This Refactoring

-   **Improved Separation of Concerns**: The new architecture separates data access logic from business logic, making the system easier to understand and maintain.
-   **Enhanced Testability**: Each component can be tested independently, allowing for more focused and effective unit tests.
-   **Increased Flexibility**: The system is more flexible and extensible. For example, changing the database schema only requires updating the `MemoryRepository`, without affecting the `MemoryService`.
-   **Better Performance**: By centralizing data access in the `MemoryRepository`, we can implement caching strategies to reduce redundant database queries.

This refactoring will result in a more robust, maintainable, and scalable memory management system for OpenChronicle.
