# Refactoring Analysis for `character_interaction_engine.py`

## 1. Overview

The `character_interaction_engine.py` module is responsible for managing the complex web of relationships, dialogues, and actions between multiple characters within a scene. It tracks relationship states (like trust and suspicion), orchestrates the flow of interactions, and maintains the emotional state of each character.

While functionally rich, the current architecture concentrates almost all logic and data management into the single `CharacterInteractionEngine` class. This creates a "God Object" that is difficult to maintain, test, and extend.

## 2. Key Issues and Anti-Patterns

*   **God Object**: The `CharacterInteractionEngine` class violates the Single Responsibility Principle (SRP) by handling numerous distinct responsibilities:
    *   **Data Repository**: It directly manages in-memory dictionaries for `RelationshipState`, `SceneState`, and `Interaction` objects.
    *   **Scene Orchestrator**: It controls the turn-based flow of interactions within a scene (e.g., `get_next_speaker`).
    *   **Relationship Logic**: It contains the hardcoded rules for how interactions affect character relationships (e.g., `_process_interaction_effects`).
    *   **State Management**: It tracks the individual state of each character within a scene (`CharacterState`).
    *   **Context Generation**: It builds complex data structures to be used as context for LLM prompts (`generate_interaction_context`).

*   **Tight Coupling**: The business logic is tightly coupled with the data storage implementation (in-memory dictionaries). Swapping this for a database or another storage mechanism would require significant refactoring of the entire class.

*   **Hardcoded Rules**: The logic for determining the emotional impact of an interaction is based on a simple, hardcoded keyword search (`_process_interaction_effects`). This approach is brittle and cannot be easily customized or expanded without modifying the core engine code.

*   **Implicit Data Keys**: Using concatenated strings like `"char_a:char_b"` as dictionary keys for relationships is not type-safe and can lead to subtle bugs.

## 3. Proposed Refactoring Plan

The refactoring strategy is to decompose the `CharacterInteractionEngine` into a set of cohesive, loosely coupled components, each with a single, well-defined responsibility. This will be achieved by applying the Repository and Strategy patterns.

### Step 1: Decouple Data Models

- **Action**: Move all `dataclasses` and `Enums` into a dedicated data model file.
- **New File**: `core/interaction_models.py`
- **Contents**:
    - `RelationshipType` (Enum)
    - `InteractionType` (Enum)
    - `RelationshipState` (Dataclass)
    - `CharacterState` (Dataclass)
    - `Interaction` (Dataclass)
    - `SceneState` (Dataclass)
- **Benefit**: Clearly separates the data structures from the logic that operates on them.

### Step 2: Introduce Repositories for Data Persistence

- **Action**: Create dedicated repository classes to handle the storage and retrieval of each type of data object.
- **New Files**:
    - `core/repositories/scene_repository.py`
    - `core/repositories/relationship_repository.py`
    - `core/repositories/interaction_repository.py`
- **Responsibilities**:
    - Each repository will manage its corresponding dictionary (e.g., `SceneRepository` manages `self.scene_states`).
    - They will provide a clean API for CRUD (Create, Read, Update, Delete) operations (e.g., `get_scene(scene_id)`, `save_scene(scene)`).
    - This abstracts away the storage implementation, making the system more modular.

### Step 3: Isolate Business Logic into Manager/Controller Classes

- **Action**: Extract the distinct business logic responsibilities into their own classes.
- **New Files**:
    - `core/scene_controller.py`
    - `core/relationship_manager.py`
- **Responsibilities**:
    - **`SceneController`**: Manages the state and flow of a single scene. It will handle turn-taking (`get_next_speaker`), updating scene-level properties like tension, and orchestrating the sequence of events.
    - **`RelationshipManager`**: Contains the logic for how relationships evolve. It will encapsulate the rules from `_process_interaction_effects` and provide methods to calculate relationship changes based on interactions. This logic could eventually be loaded from a configuration file.

### Step 4: Refine the `CharacterInteractionEngine` into a High-Level Facade

- **Action**: Rewrite the `CharacterInteractionEngine` to coordinate the new components, delegating tasks to the appropriate manager or repository.
- **File**: `core/character_interaction_engine.py` (modified)
- **New `CharacterInteractionEngine`**:
    - It will receive the repositories and managers as dependencies via its constructor (Dependency Injection).
    - Its public methods will become clean, high-level entry points. For example, `add_interaction` would coordinate the process:
        1.  Call `InteractionRepository` to save the new interaction.
        2.  Call `RelationshipManager` to compute the resulting relationship changes.
        3.  Call `RelationshipRepository` to save the updated relationships.
        4.  Call `SceneController` to update the scene's state (e.g., tension, next speaker).
        5.  Call `SceneRepository` to save the updated scene.
    - It will no longer contain any direct data manipulation or hardcoded business rules.

## 4. New Directory Structure

```
core/
|-- character_interaction_engine.py  # The refactored facade class
|-- interaction_models.py            # All dataclasses and enums
|-- scene_controller.py              # Manages the flow of a single scene
|-- relationship_manager.py          # Manages relationship dynamics and rules
|-- repositories/
|   |-- __init__.py
|   |-- scene_repository.py
|   |-- relationship_repository.py
|   |-- interaction_repository.py
config/
|-- relationship_rules.json          # (Optional) New config for relationship rules
```

This refactoring will transform the `character_interaction_engine` from a monolithic script into a robust, modular, and maintainable system that adheres to modern software design principles.
