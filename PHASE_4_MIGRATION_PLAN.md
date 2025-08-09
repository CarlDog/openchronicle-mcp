# Phase 4: Legacy Migration Plan

## Analysis Summary

The existing `main.py` (817 lines) contains several functional areas that need to be migrated into our clean hexagonal architecture:

### 1. **Application Layer Components** (CLI Logic)
- **Command-line argument parsing** (`parse_arguments()`)
- **Interactive command processing** (main loop, user input handling)
- **Quick test functionality** (`run_quick_test()`, non-interactive mode)
- **Health check startup** (`run_startup_health_check()`)

### 2. **Interface Layer Components** (User Interactions)
- **Security wrapper functions** (`secure_user_input()`, validation)
- **Display/formatting utilities** (`emoji()`, `status_icon()`, output formatting)
- **Model management commands** (`show_model_info()`, `switch_model()`)
- **Image generation CLI** (`show_image_commands()`, image-related interfaces)
- **Memory display** (`print_memory_summary()`)
- **Rollback interface** (`show_rollback_options()`)
- **API key management interface** (`show_interactive_key_commands()`, key management functions)

### 3. **Application Service Logic** (Core Orchestration)
- **Story processing workflow** (`process_story_input()` - context building, AI generation, scene logging)
- **Content flag generation** (integration with ContentAnalyzer)
- **Event logging** (recent events, memory updates)

## Migration Strategy

### Phase 4.1: Create Enhanced CLI Application
**Target**: `src/openchronicle/applications/cli_app.py`
- Migrate the main interactive CLI logic into a proper application service
- Convert command handlers into structured command pattern
- Integrate with our existing CLI interface layer

### Phase 4.2: Extract Story Processing Service  
**Target**: `src/openchronicle/applications/services/story_processing_service.py`
- Extract the core story processing workflow (`process_story_input`)
- Create proper application service for story interactions
- Integrate with domain services through dependency injection

### Phase 4.3: Enhance Interface Utilities
**Target**: `src/openchronicle/interfaces/cli/` (enhance existing)
- Migrate display utilities and security wrappers
- Enhance existing CLI interface with additional commands
- Add interactive features to current Click-based CLI

### Phase 4.4: Create Integration Entry Points
**Target**: `src/openchronicle/main.py` (replace root main.py)
- Create new minimal entry point that uses our architecture
- Route to appropriate interfaces (CLI, API, web)
- Preserve all existing command-line compatibility

### Phase 4.5: Legacy Cleanup
- Archive the old `main.py` as `legacy_main.py`
- Update all references and documentation
- Verify complete functionality preservation

## Implementation Order

1. **Extract and test story processing service** (core business logic first)
2. **Create enhanced CLI application** (migrate application layer)
3. **Enhance CLI interface** (migrate interface layer)
4. **Create new entry point** (integration layer)
5. **Test complete functionality** (end-to-end validation)
6. **Clean up legacy code** (final cleanup)

## Success Criteria

- ✅ All existing CLI functionality preserved
- ✅ All command-line arguments work identically  
- ✅ Interactive mode functions exactly as before
- ✅ Non-interactive/test modes work unchanged
- ✅ API key management preserved
- ✅ Image generation CLI preserved
- ✅ Memory/rollback features preserved
- ✅ Integration with new architecture layers
- ✅ Improved maintainability and testability

## Risk Mitigation

- Keep original `main.py` as backup during migration
- Test each component individually before integration
- Validate command-line compatibility at each step
- Use dependency injection to maintain loose coupling
