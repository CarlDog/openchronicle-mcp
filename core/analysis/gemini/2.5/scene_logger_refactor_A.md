# Refactoring Analysis for `scene_logger.py`

## Executive Summary

The `scene_logger.py` module is responsible for saving and retrieving scenes, which are the fundamental units of a story in OpenChronicle. The current implementation consists of a collection of standalone functions that directly interact with the database, leading to a lack of clear separation of concerns and code duplication.

This refactoring plan aims to introduce a more structured architecture by applying the **Service Layer**, **Repository**, and **Data Model** design patterns. This will improve modularity, testability, and the overall maintainability of the scene logging system.

## Architectural Issues

1.  **Lack of a Central Service**: The module consists of a collection of functions, making it difficult to manage dependencies and maintain a consistent API. There is no central service to orchestrate the different scene operations.

2.  **Mixing of Concerns**: The functions in `scene_logger.py` mix data access logic (SQL queries) with business logic (e.g., generating scene IDs, calculating token usage, formatting scene data). This violates the Single Responsibility Principle (SRP) and makes the code harder to test and maintain.

3.  **Code Duplication**: The `init_database` function is called repeatedly by other functions, leading to redundant database initializations.

4.  **Limited Extensibility**: Adding new scene metadata or changing the database schema requires modifying multiple functions, which is error-prone and inefficient.

## Proposed Refactoring

I propose refactoring the `scene_logger.py` module into a layered architecture with distinct components for services, repositories, and data models.

### 1. New Directory Structure

Create a new directory `core/scene` to house the refactored components:

```
core/
|-- scene/
|   |-- __init__.py
|   |-- scene_service.py        # High-level scene operations
|   |-- scene_repository.py     # Data access and database interactions
|   |-- models/
|   |   |-- __init__.py
|   |   |-- scene.py
|-- scene_logger.py             # Facade for the scene logging subsystem
```

### 2. Refactoring Steps

#### Step 1: Create Data Models

Create a dedicated data model for a scene in `core/scene/models/scene.py`.

-   **`core/scene/models/scene.py`**:
    ```python
    from dataclasses import dataclass, field
    from typing import Dict, List, Any

    @dataclass
    class Scene:
        scene_id: str
        timestamp: str
        user_input: str
        model_output: str
        memory_snapshot: Dict[str, Any] = field(default_factory=dict)
        flags: List[Any] = field(default_factory=list)
        canon_refs: List[Any] = field(default_factory=list)
        analysis_data: Dict[str, Any] = field(default_factory=dict)
        scene_label: str = ""
        structured_tags: Dict[str, Any] = field(default_factory=dict)
    ```

#### Step 2: Implement the Scene Repository

Create a `SceneRepository` class in `core/scene/scene_repository.py` to handle all database interactions.

-   **`core/scene/scene_repository.py`**:
    ```python
    from .models.scene import Scene

    class SceneRepository:
        def __init__(self, story_id: str):
            self.story_id = story_id

        def save_scene(self, scene: Scene):
            # Database logic to save a scene
            pass

        def load_scene(self, scene_id: str) -> Scene:
            # Database logic to load a scene
            pass

        def get_scenes_by_mood(self, mood: str) -> List[Scene]:
            # Database logic to get scenes by mood
            pass

        def get_scenes_by_type(self, scene_type: str) -> List[Scene]:
            # Database logic to get scenes by type
            pass
    ```

#### Step 3: Implement the Scene Service

Create a `SceneService` class in `core/scene/scene_service.py` to orchestrate the different scene operations.

-   **`core/scene/scene_service.py`**:
    ```python
    from .scene_repository import SceneRepository
    from .models.scene import Scene

    class SceneService:
        def __init__(self, story_id: str):
            self.repository = SceneRepository(story_id)

        def save_scene(self, user_input: str, model_output: str, **kwargs) -> str:
            # Business logic for creating and saving a scene
            pass

        def load_scene(self, scene_id: str) -> Scene:
            return self.repository.load_scene(scene_id)

        def get_scenes_by_mood(self, mood: str) -> List[Scene]:
            return self.repository.get_scenes_by_mood(mood)

        def get_scenes_by_type(self, scene_type: str) -> List[Scene]:
            return self.repository.get_scenes_by_type(scene_type)
    ```

#### Step 4: Refactor the `scene_logger.py` Module as a Facade

Update the `scene_logger.py` module to act as a simple facade that delegates calls to the new `SceneService`.

-   **`core/scene_logger.py`**:
    ```python
    from .scene.scene_service import SceneService

    def save_scene(story_id, user_input, model_output, **kwargs):
        service = SceneService(story_id)
        return service.save_scene(user_input, model_output, **kwargs)

    def load_scene(story_id, scene_id):
        service = SceneService(story_id)
        return service.load_scene(scene_id)

    def get_scenes_by_mood(story_id, mood):
        service = SceneService(story_id)
        return service.get_scenes_by_mood(mood)

    # ... other functions delegating to the service
    ```

## Benefits of This Refactoring

-   **Improved Separation of Concerns**: The new architecture separates data access logic from business logic, making the system easier to understand and maintain.
-   **Enhanced Testability**: Each component can be tested independently, allowing for more focused and effective unit tests.
-   **Increased Flexibility**: The system is more flexible and extensible. For example, changing the database schema only requires updating the `SceneRepository`, without affecting the `SceneService`.
-   **Better Performance**: By centralizing data access in the `SceneRepository`, we can implement caching strategies to reduce redundant database queries.

This refactoring will result in a more robust, maintainable, and scalable scene logging system for OpenChronicle.
