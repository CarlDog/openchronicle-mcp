# Refactoring Analysis for `timeline_builder.py`

## 1. Overview

The `timeline_builder.py` module is designed to create various chronological views of a story. It interacts with the database to fetch scenes and bookmarks, and then assembles them into different structures, such as a full linear timeline, a chapter-based view, or a list of labeled scenes. It also includes functionality for exporting these timelines and performing analytical tasks like tone consistency audits and auto-summarization.

The current implementation is centered around a single `TimelineBuilder` class that handles all of these responsibilities, making it a "God Object."

## 2. Key Issues and Anti-Patterns

*   **God Object / Monolithic Class**: The `TimelineBuilder` class violates the Single Responsibility Principle (SRP) by managing a wide array of unrelated tasks:
    *   **Data Fetching**: It directly queries the database for scenes and interacts with the `BookmarkManager`.
    *   **Data Aggregation and Structuring**: It contains the logic for organizing scenes and bookmarks into different timeline formats (`get_full_timeline`, `get_chapter_timeline`).
    *   **Data Formatting/Exporting**: It includes methods to format the timeline data into JSON (`export_timeline_json`) and Markdown (`export_timeline_markdown`). This is presentation logic mixed with business logic.
    *   **Complex Analytics**: It performs sophisticated analysis like tone consistency audits (`track_tone_consistency_audit`) and auto-summarization (`generate_auto_summary`), which are heavy analytical tasks, not simple timeline construction.

*   **Tight Coupling**: The class is tightly coupled to the database schema and the `BookmarkManager`. Any changes in how scenes or bookmarks are stored would require significant modifications to this class.

*   **Mixing of Concerns**: The class mixes simple data retrieval (e.g., `get_labeled_timeline`) with complex, stateful analysis (e.g., `track_tone_consistency_audit`). These are fundamentally different responsibilities and should not reside in the same class.

## 3. Proposed Refactoring Plan

The refactoring strategy is to decompose the `TimelineBuilder` class into a set of smaller, more focused components. We will apply the **Repository pattern** to handle data access, the **Service Layer pattern** for business logic, and create dedicated classes for the distinct analytical functions.

### Step 1: Decouple Data Models

- **Action**: Create dedicated `dataclasses` to represent the various timeline structures and their components.
- **New File**: `core/timeline_models.py`
- **Contents**:
    - `TimelineEntry` (Dataclass): Represents a single item in the timeline (e.g., a scene with its associated bookmarks).
    - `Chapter` (Dataclass): Represents a chapter, containing a bookmark and a list of `TimelineEntry` objects.
    - `Timeline` (Dataclass): A top-level object containing a list of `TimelineEntry` or `Chapter` objects.
- **Benefit**: Provides a clear, type-safe structure for the data, making the code more robust and self-documenting.

### Step 2: Create a `TimelineRepository`

- **Action**: Create a repository class to handle all direct database interactions related to fetching scene data for the timeline.
- **New File**: `core/timeline_repository.py`
- **`TimelineRepository` Class**:
    - Will contain all the SQL queries for fetching scenes in various orders and ranges.
    - Its methods will return lists of `Scene` objects (assuming a `Scene` model exists from refactoring `scene_logger.py`).
    - Example methods: `get_all_scenes_chronological()`, `get_scenes_by_label(label)`, `get_scenes_in_range(start_ts, end_ts)`.
- **Benefit**: Decouples the timeline logic from the specifics of the database, making the system more modular and testable.

### Step 3: Refactor `TimelineBuilder` into a Focused Service

- **Action**: Rewrite the `TimelineBuilder` to be a `TimelineService` that focuses solely on constructing different timeline views.
- **File**: `core/timeline_service.py` (renamed from `timeline_builder.py`)
- **New `TimelineService`**:
    - It will take the `TimelineRepository` and `BookmarkManager` as dependencies in its constructor.
    - It will contain the logic for assembling the data from the repository and manager into the `Timeline` and `Chapter` data models.
    - It will retain methods like `get_full_timeline` and `get_chapter_timeline`, but they will now operate on data retrieved from the repository.
- **Benefit**: The service now has a single, clear responsibility: building timeline structures.

### Step 4: Extract Analytical and Formatting Logic into Separate Classes

- **Action**: Move the complex analytical and formatting functions into their own dedicated classes.
- **New Files**:
    - `core/timeline_exporter.py`: Will contain the logic for formatting timeline data into different formats (JSON, Markdown). It will take a `Timeline` object as input.
    - `core/analytics/tone_analyzer.py`: A new class dedicated to performing the tone consistency audit. It will take the `TimelineRepository` as a dependency.
    - `core/analytics/summary_generator.py`: A new class dedicated to generating auto-summaries. It will also depend on the `TimelineRepository`.
- **Benefit**: This separation adheres to SRP. The core timeline service is no longer bloated with complex, unrelated functionality. The analytical components can be developed, tested, and even run independently.

## 4. New Directory Structure

```
core/
|-- timeline_service.py         # Core service for building timeline structures
|-- timeline_repository.py      # Handles fetching scene data from the DB
|-- timeline_models.py          # Dataclasses for timeline structures
|-- timeline_exporter.py        # Handles formatting timelines into JSON/Markdown
|-- analytics/
|   |-- __init__.py
|   |-- tone_analyzer.py        # Performs tone consistency audits
|   |-- summary_generator.py    # Generates auto-summaries
|-- bookmark_manager.py         # (Existing)
|-- database.py                 # (Existing)
```

This refactoring will transform the `timeline_builder` from a monolithic "do-everything" class into a set of clean, well-defined components. This improves modularity, testability, and maintainability, creating a more professional and scalable architecture.
