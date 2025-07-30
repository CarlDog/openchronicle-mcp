# Refactoring Analysis for `narrative_dice_engine.py`

## 1. Overview

The `narrative_dice_engine.py` module provides an RPG-style dice resolution system for character actions. It determines success or failure based on dice rolls, character stats, and action difficulty. The engine is designed to make outcomes, especially failures, narratively significant.

The current implementation is centered around a single, large `NarrativeDiceEngine` class, which handles configuration, dice rolling, rule application, data storage, and data transformation. This monolithic design makes the engine rigid and difficult to customize or test effectively.

## 2. Key Issues and Anti-Patterns

*   **God Object**: The `NarrativeDiceEngine` class is a textbook example of a God Object, violating the Single Responsibility Principle (SRP) by managing too many distinct concerns:
    *   **Configuration Management**: It holds and manages the `ResolutionConfig`.
    *   **Data Storage**: It maintains in-memory dictionaries for `resolution_history`, `narrative_branches`, and `character_performance`.
    *   **Dice Rolling Logic**: It contains a dictionary of functions for every supported dice type (`_roll_d20`, `_roll_3d6`, etc.), hardcoding the rolling mechanism.
    *   **Rule Engine**: It contains the core logic for calculating modifiers from stats, determining outcomes from roll margins, and generating narrative text.
    *   **Analytics and Reporting**: It includes methods for calculating character performance statistics (`get_character_performance_summary`) and running simulations (`simulate_resolution`).

*   **Hardcoded Rules and Content**: The engine's behavior is defined by hardcoded data structures.
    *   The mapping of resolution types to character stats (`self.stat_mappings`) is fixed.
    *   The narrative text for successes and failures (`_generate_narrative_impact`) is pulled from hardcoded templates.
    *   This prevents story-specific customization of the dice system without modifying the core Python code.

*   **Lack of Pluggability**: While the engine supports multiple dice types, the mechanism is a hardcoded dictionary of functions. This is not a true pluggable system and requires code changes to add new dice-rolling methods.

## 3. Proposed Refactoring Plan

The refactoring strategy is to decompose the `NarrativeDiceEngine` by applying the **Strategy**, **Repository**, and **Service Layer** patterns. This will separate concerns, externalize rules, and make the system more modular and configurable.

### Step 1: Decouple Data Models

- **Action**: Move all `Enums` and `dataclasses` into a dedicated data model file.
- **New File**: `core/dice_models.py`
- **Contents**:
    - `DiceType`, `ResolutionType`, `DifficultyLevel`, `OutcomeType` (Enums)
    - `ResolutionResult`, `ResolutionConfig`, `NarrativeBranch` (Dataclasses)
- **Benefit**: Separates the data definitions (the "what") from the operational logic (the "how").

### Step 2: Isolate Dice Rolling with the Strategy Pattern

- **Action**: Create a pluggable system for dice rolling.
- **New Files**:
    - `core/dice_rollers/roller_interface.py`: Defines an abstract base class `DiceRoller` with a `roll()` method.
    - `core/dice_rollers/d20_roller.py`, `core/dice_rollers/three_d6_roller.py`, etc.: Concrete implementations of `DiceRoller` for each dice system.
- **Benefit**: The engine can be configured with any `DiceRoller` strategy, making it easy to add new dice systems without changing the engine's code.

### Step 3: Externalize Rules into a `Rulebook`

- **Action**: Create a `Rulebook` class to manage all configurable rules, loaded from an external file.
- **New File**: `core/dice_rulebook.py`
- **New Config File**: `config/dice_rules.json`
- **`Rulebook` Class**:
    - Loads stat mappings, outcome thresholds, and narrative templates from `dice_rules.json`.
    - Provides methods like `get_stat_for_resolution(resolution_type)` and `get_narrative_for_outcome(outcome)`.
- **Benefit**: Makes the dice system data-driven. Game mechanics and narrative flavor can be customized per-story by simply changing a JSON file.

### Step 4: Separate Concerns into Focused Services and Repositories

- **Action**: Break down the remaining responsibilities of the God Object into smaller classes.
- **New Files**:
    - `core/resolution_service.py`: The core service that performs the action resolution. It will take a `DiceRoller` and a `Rulebook` as dependencies. Its `resolve()` method will orchestrate the process of rolling, applying modifiers, and determining the outcome.
    - `core/performance_tracker.py`: A dedicated class to manage the `character_performance` data, encapsulating all statistical calculations.
    - `core/resolution_repository.py`: A repository to handle the persistence of `ResolutionResult` objects, abstracting away the in-memory list.
- **Benefit**: Each class has a single, clear responsibility, making them easier to test and maintain.

### Step 5: Refactor `NarrativeDiceEngine` into a High-Level Facade

- **Action**: Rewrite the `NarrativeDiceEngine` to be a clean, high-level entry point that coordinates the other components.
- **File**: `core/narrative_dice_engine.py` (modified)
- **New `NarrativeDiceEngine`**:
    - Its constructor will accept the `ResolutionService`, `PerformanceTracker`, and `ResolutionRepository` as dependencies.
    - Its public methods will delegate calls to the appropriate service or repository.
- **Benefit**: The engine becomes a simple facade, easy to use and understand, while the complex logic is encapsulated in the specialized components.

## 4. New Directory Structure

```
core/
|-- narrative_dice_engine.py    # The refactored high-level facade
|-- dice_models.py              # All dataclasses and enums for the dice system
|-- dice_rulebook.py            # Manages rules loaded from config
|-- resolution_service.py       # Core logic for resolving an action
|-- performance_tracker.py      # Manages and calculates character performance
|-- resolution_repository.py    # Handles persistence of resolution results
|-- dice_rollers/
|   |-- __init__.py
|   |-- roller_interface.py
|   |-- d20_roller.py
|   |-- three_d6_roller.py
|   |-- ... (other roller implementations)
config/
|-- dice_rules.json             # New config for dice rules, mappings, and templates
```

This refactoring will transform the `narrative_dice_engine` from a monolithic script into a flexible, modular, and professional-grade system that is highly configurable and easy to extend.
