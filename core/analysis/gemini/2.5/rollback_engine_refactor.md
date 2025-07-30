# Refactoring Analysis for `rollback_engine.py`

## Executive Summary

The `rollback_engine.py` module is responsible for managing story state rollbacks, allowing users to revert to previous scenes. It currently handles creating rollback points, listing them, executing the rollback logic, and performing data validation and cleanup. The module is tightly coupled to the database, with SQL queries embedded directly within its functions.

This refactoring plan aims to decouple the business logic from the data access layer by introducing a **Repository** pattern. This will improve modularity, testability, and maintainability, making the system more robust and easier to extend.

## Architectural Issues

1.  **Tight Coupling with Database**: The module directly interacts with the database using SQL queries. This violates the Single Responsibility Principle (SRP) and makes it difficult to change the database schema or switch to a different storage mechanism without modifying the business logic.

2.  **Mixed Responsibilities**: The module mixes high-level business logic (e.g., `rollback_to_scene`) with low-level data access (e.g., `execute_query`, `execute_update`). This makes the code harder to read, test, and maintain.

3.  **Limited Testability**: Unit testing the business logic in isolation is challenging because it is intertwined with database calls. Mocks are required for almost every function, making tests complex and brittle.

## Proposed Refactoring

I propose refactoring the `rollback_engine.py` module by introducing a `RollbackRepository` to handle all database interactions. This will create a clear separation between the business logic and the data access layer.

### 1. New Directory Structure

```
core/
|-- rollback/
|   |-- __init__.py
|   |-- models.py                 # Pydantic models for RollbackPoint, etc.
|   |-- rollback_repository.py    # Handles all database interactions
|   |-- rollback_service.py       # Contains the core business logic
|-- rollback_engine.py            # High-level facade for the rollback subsystem
```

### 2. Refactoring Steps

#### Step 1: Create Data Models

Define explicit Pydantic models for all rollback-related data structures in `core/rollback/models.py`.

-   **`core/rollback/models.py`**:
    ```python
    from pydantic import BaseModel
    from typing import List, Dict, Any

    class RollbackPoint(BaseModel):
        id: str
        scene_id: str
        timestamp: str
        description: str
        scene_data: Dict[str, Any]
    ```

#### Step 2: Implement the Rollback Repository

Create a `RollbackRepository` class in `core/rollback/rollback_repository.py` to encapsulate all database operations.

-   **`core/rollback/rollback_repository.py`**:
    ```python
    from typing import List
    from .models import RollbackPoint

    class RollbackRepository:
        def __init__(self, story_id: str):
            self.story_id = story_id

        def create_rollback_point(self, rollback_point: RollbackPoint) -> RollbackPoint:
            # SQL logic to insert a new rollback point
            pass

        def list_rollback_points(self) -> List[RollbackPoint]:
            # SQL logic to retrieve all rollback points
            pass

        def delete_scenes_after(self, scene_id: str) -> int:
            # SQL logic to delete scenes after a given scene
            pass

        def backup_scenes(self, scenes_to_backup: List[str]):
            # SQL logic to backup scenes before a rollback
            pass
    ```

#### Step 3: Implement the Rollback Service

Create a `RollbackService` class in `core/rollback/rollback_service.py` to contain the business logic.

-   **`core/rollback/rollback_service.py`**:
    ```python
    from .rollback_repository import RollbackRepository
    from ..memory_manager import MemoryManager

    class RollbackService:
        def __init__(self, story_id: str):
            self.repository = RollbackRepository(story_id)
            self.memory_manager = MemoryManager(story_id)

        def rollback_to_scene(self, target_scene_id: str, create_backup: bool = True) -> dict:
            # Business logic for rolling back to a scene
            # ...
            # self.repository.delete_scenes_after(target_scene_id)
            # self.memory_manager.restore_memory_from_snapshot(target_scene_id)
            pass
    ```

#### Step 4: Refactor the `RollbackEngine` as a Facade

Update the original `rollback_engine.py` to act as a simple facade that delegates calls to the new service.

-   **`core/rollback_engine.py`**:
    ```python
    from .rollback.rollback_service import RollbackService

    class RollbackEngine:
        def __init__(self, story_id: str):
            self.service = RollbackService(story_id)

        def create_rollback_point(self, scene_id: str, description: str) -> dict:
            return self.service.create_rollback_point(scene_id, description)

        def rollback_to_scene(self, target_scene_id: str, create_backup: bool = True) -> dict:
            return self.service.rollback_to_scene(target_scene_id, create_backup)
    ```

## Benefits of This Refactoring

-   **Improved Separation of Concerns**: The new architecture cleanly separates data access (Repository) from business logic (Service).
-   **Enhanced Testability**: The `RollbackService` can be tested in isolation with a mock repository, allowing for focused and effective unit tests of the business logic.
-   **Increased Flexibility**: The system is more flexible. Changing the database schema only requires updating the repository, with no impact on the service layer.
-   **Better Maintainability**: The code is organized logically, making it easier for developers to find, understand, and modify specific parts of the rollback system.
