# Refactoring Analysis for `scene_logger.py`

## 1. Overview

The `scene_logger.py` module is responsible for saving and retrieving scene data from the story's database. It handles the serialization of various data points associated with a scene, such as user input, model output, memory snapshots, and structured metadata (tags). It also provides functions to query scenes based on this metadata.

The current implementation is a collection of free-standing functions that directly interact with the database. This design mixes data access, business logic (like token calculation), and data serialization, making it difficult to maintain, test, and extend.

## 2. Key Issues and Anti-Patterns

*   **Lack of Abstraction**: The module operates as a set of procedural functions. There is no central class or abstraction layer to manage scene data, leading to scattered logic and a tight coupling with the database schema. Any change to the `scenes` table requires updating multiple functions.

*   **Mixing Concerns (SRP Violation)**: The module violates the Single Responsibility Principle by combining several distinct responsibilities:
    *   **Database Interaction**: Directly calls `execute_query` and `execute_update`.
    *   **Business Logic**: Contains logic for calculating token usage (`save_scene`), which is a business rule, not a persistence concern.
    *   **Data Serialization/Deserialization**: Manages the conversion of complex Python objects (like memory snapshots and tags) to and from JSON strings. This logic is spread across multiple functions.
    *   **Querying Logic**: Implements various specific queries (e.g., `get_scenes_by_mood`, `get_scenes_with_long_turns`) using hardcoded SQL `LIKE` clauses, which are inefficient and brittle.

*   **Dependency on External Modules**: It directly depends on the `token_manager` for token calculations, mixing the concern of scene persistence with the concern of resource management.

## 3. Proposed Refactoring Plan

The refactoring strategy is to introduce clear layers of abstraction using the Repository and Service patterns, along with dedicated data models. This will decouple the components and assign each a single, clear responsibility.

### Step 1: Define Clear Data Models

- **Action**: Create dedicated `dataclasses` to represent the structure of a scene and its associated metadata.
- **New File**: `core/scene_models.py`
- **Contents**:
    - `TokenUsage` (Dataclass): Fields for `input_tokens`, `output_tokens`, `model_used`, etc.
    - `StructuredTags` (Dataclass): Fields for `mood`, `scene_type`, `location`, `token_usage: TokenUsage`, etc.
    - `Scene` (Dataclass): The main data object with fields like `scene_id`, `timestamp`, `input`, `output`, `memory_snapshot`, and `tags: StructuredTags`.
- **Benefit**: Provides a single source of truth for the data schema, enabling type safety, better code completion, and clearer contracts between different parts of the system.

### Step 2: Create a Scene Repository

- **Action**: Create a `SceneRepository` class to handle all direct database interactions for scenes.
- **New File**: `core/scene_repository.py`
- **`SceneRepository` Class**:
    - Will contain all the SQL queries and calls to `execute_query` and `execute_update`.
    - Its methods will accept and return the new `Scene` data model, handling the serialization/deserialization of complex fields (like `StructuredTags`) internally.
    - It will provide a clean API for CRUD operations (e.g., `get(scene_id: str) -> Scene`, `save(scene: Scene)`).
    - It will also implement the various query methods (e.g., `find_by_mood(mood: str) -> List[Scene]`, `find_long_turns() -> List[Scene]`).
- **Benefit**: Decouples the rest of the application from the database implementation. The storage mechanism could be changed (e.g., to a different database or file system) with minimal impact on other components.

### Step 3: Create a Scene Service Layer

- **Action**: Create a `SceneLoggerService` to contain the core business logic related to logging scenes.
- **New File**: `core/scene_logger_service.py`
- **`SceneLoggerService` Class**:
    - Will take the `SceneRepository` and `TokenManager` as dependencies in its constructor.
    - It will contain the high-level business logic for creating and saving a scene.
    - The `log_scene` method in this service would:
        1.  Accept raw data (user input, model output, memory snapshot).
        2.  Use the `TokenManager` to calculate token usage.
        3.  Construct the `StructuredTags` and `Scene` data models.
        4.  Call the `SceneRepository` to persist the `Scene` object.
- **Benefit**: Centralizes the business rules for scene creation in one place, making it easier to manage and test. It cleanly separates the "what" (the business process) from the "how" (the database interaction).

## 4. New Directory Structure

```
core/
|-- scene_logger_service.py   # High-level business logic for logging scenes
|-- scene_repository.py       # Data access and persistence for scenes
|-- scene_models.py           # All dataclasses for scenes and metadata
|-- database.py               # (Existing) Low-level DB connection
|-- token_manager.py          # (Existing) Token management logic
```

This refactoring will transform `scene_logger.py` from a procedural script into a well-structured, multi-layered system that is robust, scalable, and easy to maintain. Each component will have a clear, single responsibility, improving the overall quality and testability of the codebase.
