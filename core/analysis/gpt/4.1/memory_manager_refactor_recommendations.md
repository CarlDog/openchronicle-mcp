# Refactoring & Deduplication Recommendations: memory_manager.py

## Overview
`memory_manager.py` provides functions for loading, saving, updating, archiving, and formatting story memory, including character, world state, flags, events, and snapshots. It supports rollback, prompt formatting, and memory context generation.

## Key Observations
- **Procedural Structure**: All logic is implemented as standalone functions, which could be grouped for clarity and maintainability.
- **Repeated Patterns**: Database initialization, query execution, and JSON handling are repeated across functions.
- **Character Memory Management**: Character update, mood, voice, and history logic are duplicated and could be modularized.
- **Prompt Formatting**: Snapshot and context formatting logic is repeated and could be centralized.
- **Event & Flag Handling**: Event and flag management logic is scattered and could be grouped.
- **Error Handling**: Logging and error handling are performed throughout, but could be centralized for consistency.

## Refactoring Opportunities
1. **Extract Database & JSON Utilities**
   - Move database initialization and JSON handling to a helper module/class.
   - Use a `MemoryManager` class to encapsulate core logic and state.

2. **Modularize Character Memory Management**
   - Move character update, mood, voice, and history logic to dedicated modules/classes.
   - Centralize error handling for character operations.

3. **Centralize Prompt Formatting**
   - Create utility functions for snapshot and context formatting to reduce duplication.

4. **Group Event & Flag Handling**
   - Move event and flag management logic to a dedicated module/class.

5. **Logging Consistency**
   - Centralize logging calls and ensure all major actions/events are logged in a uniform way.

## Example Extraction Plan
- `memory_manager.py` (core logic, entry points)
- `memory_db_utils.py` (database and JSON handling)
- `character_memory.py` (character update, mood, voice, history)
- `memory_prompt_utils.py` (snapshot/context formatting)
- `memory_event_flag.py` (event and flag management)

## Next Steps
1. Identify repeated code and extract to utility modules.
2. Refactor character memory and prompt formatting logic for maintainability.
3. Move event/flag handling and error logging to separate modules.
4. Document new module boundaries and update tests.

---
*For project status, see `.copilot/project_status.json`. Update this document as refactoring progresses.*
