# OpenChronicle Architecture Overview

**Updated**: August 7, 2025
**Version**: 4.0 (Post-Consolidation)
**Status**: Production Architecture - Phases 1-6 Complete

---

## 🏗️ **Executive Architecture Summary**

OpenChronicle has been successfully transformed from monolithic components into a comprehensive **orchestrator-based modular architecture**. The system now features 13+ specialized orchestrators with professional test infrastructure (417 tests), SOLID principles implementation, and ultra-clean workspace organization representing the completion of a major architectural modernization.

### **Architecture Philosophy**

- **Orchestrator Pattern**: Every major system has a single entry point orchestrator
- **Clean Separation**: Clear domain boundaries with standardized interfaces
- **Test-Driven Quality**: Professional pytest infrastructure with comprehensive coverage
- **Modular Loading**: Resource-efficient loading with graceful degradation
- **Performance Optimized**: High-performance async operations throughout
- **SOLID Principles**: Interface segregation, dependency injection, modern patterns

### **Key Metrics**

- **Total Files**: 164 Python files in core module
- **Total Lines**: 35,668 lines of code
- **Test Coverage**: 417 tests with modern infrastructure
- **Architecture Pattern**: Orchestrator-based modular design
- **Performance**: <100ms response time targets for production API

---
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   story_loader  │    │ context_builder │    │  model_adapter  │
│                 │    │                 │    │                 │
│ • Load meta.yaml│───▶│ • Build prompts │───▶│ • LLM providers │
│ • Parse canon   │    │ • Inject style  │    │ • Fallback logic│
│ • Load chars    │    │ • Add memory    │    │ • Token limits  │
└─────────────────┘    └─────────────────┘    │ • Dynamic mgmt  │
         │                       │             └─────────────────┘
         ▼                       ▼                       │
┌─────────────────┐    ┌─────────────────┐              │
│ memory_manager  │    │ content_analyzer│              │
│                 │    │                 │              │
│ • World state   │◀──▶│ • Classify tone │              │
│ • Character mem │    │ • NSFW detect   │              │
│ • Flags/events  │    │ • Smart routing │              │
└─────────────────┘    └─────────────────┘              │
         │                       │                       │
         └───────────────────────┼───────────────────────┤
                                 ▼                       ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │    database     │    │  scene_logger   │
                    │                 │    │                 │
                    │ • SQLite per    │    │ • Log scenes    │
                    │   story         │    │ • Memory snaps  │
                    │ • Rollback      │    │ • Rollback pts  │
                    │   support       │    │ • Centralized   │
                    │ • FTS5 tables   │    │   logging       │
                    └─────────────────┘    └─────────────────┘
                             │                       │
                             ▼                       ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │ search_engine   │    │ rollback_engine │
                    │                 │    │                 │
                    │ • FTS5 search   │    │ • State mgmt    │
                    │ • Query parsing │    │ • Checkpoint    │
                    │ • Result rank   │    │ • Restoration   │
                    └─────────────────┘    └─────────────────┘
                             │                       │
                             ▼                       ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │bookmark_manager │    │ token_manager   │
                    │                 │    │                 │
                    │ • Bookmark CRUD │    │ • Token estim   │
                    │ • Collections   │    │ • Model select  │
                    │ • Search integ  │    │ • Optimization  │
                    └─────────────────┘    └─────────────────┘
                             │                       │
                             ▼                       ▼
                    ┌─────────────────┐    ┌─────────────────┐
                    │timeline_builder │    │char_style_mgr   │
                    │                 │    │                 │
                    │ • Timeline gen  │    │ • Char consist  │
                    │ • Event track   │    │ • Style enforce │
                    │ • Visual out    │    │ • Writing style │
                    └─────────────────┘    └─────────────────┘

```

## Data Flow Patterns

### 1. Scene Generation Flow
```

User Input → content_analyzer → memory_manager → context_builder → model_adapter → scene_logger

```

### 2. Memory Update Flow
```

Scene Output → content_analyzer → memory_manager → database

```

### 3. Rollback Flow
```

User Request → rollback_engine → database → memory_manager → scene_logger

```

### 4. Dynamic Model Management Flow
```

User Request → model_adapter.add_model_config() → validate_config → update_registry → centralized_logging

```

### 5. Model Health Monitoring Flow
```

Scheduled Check → model_adapter.health_check() → provider_status → registry_update → logging

```

## Dynamic Model Management Architecture

The ModelManager class provides runtime model configuration management:

```

┌─────────────────────────────────────────────────────────────────┐
│                        ModelManager                             │
├─────────────────────────────────────────────────────────────────┤
│ Dynamic Operations:                                             │
│ • add_model_config(name, config)    • remove_model_config(name)│
│ • enable_model(name)                • disable_model(name)      │
│ • list_model_configs()              • validate_config(config)  │
├─────────────────────────────────────────────────────────────────┤
│ Registry Management:                                            │
│ • Automatic backup creation         • Configuration validation │
│ • Fallback chain maintenance        • Content routing updates  │
│ • Health status monitoring          • Error handling/rollback  │
├─────────────────────────────────────────────────────────────────┤
│ Integration Points:                                             │
│ • Centralized logging system        • Configuration persistence│
│ • Provider health monitoring        • Runtime model switching  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌─────────────────────┐
                        │ config/             │
                        │ model_registry.json │
                        │                     │
                        │ • Active models     │
                        │ • Fallback chains   │
                        │ • Content routing   │
                        │ • Health status     │
                        └─────────────────────┘

```

### Configuration Flow

1. **Add Model**: `add_model_config()` → validate → backup registry → update registry → log
2. **Remove Model**: `remove_model_config()` → backup registry → update registry → log
3. **Enable/Disable**: `enable_model()`/`disable_model()` → update registry → log
4. **Health Check**: Periodic validation → status update → registry update → log

### Safety Mechanisms

- **Validation**: All configurations validated before adding
- **Backup**: Automatic backup before registry changes
- **Rollback**: Failed operations automatically rolled back
- **Logging**: All operations logged with centralized system

## Module Responsibilities

### Core Processing Modules
- **story_loader**: Static content loading and validation
- **context_builder**: Dynamic prompt construction
- **model_adapter**: LLM interaction and fallback handling
- **content_analyzer**: Content classification and routing
- **memory_manager**: State persistence and retrieval
- **scene_logger**: Scene persistence and rollback points
- **rollback_engine**: Time travel and state restoration
- **database**: SQLite operations and migrations

### Integration Points
- All modules use `DatabaseManager` for consistent SQLite access
- All modules use `utilities.logging_system` for centralized logging
- Configuration loaded via `story_loader` and shared across modules
- Memory state synchronized between `memory_manager` and `scene_logger`

## Design Patterns Used

### 1. Factory Pattern
- `ModelAdapter` creates provider-specific clients
- `DatabaseManager` creates story-specific connections

### 2. Strategy Pattern
- Content analysis strategies for different content types
- Model selection strategies based on content classification

### 3. Observer Pattern
- Memory updates trigger scene logging
- Content analysis results trigger model routing

### 4. Chain of Responsibility
- Model fallback chains
- Content analysis pipeline

## Error Handling Strategy

### Module-Level Errors
- Each module handles its own errors
- Graceful degradation when possible
- Detailed logging for debugging

### System-Level Errors
- Database corruption → rollback to last valid state
- Model failure → fallback to next in chain
- Memory corruption → rebuild from scene history

## Performance Considerations

### Database
- SQLite per story (isolation)
- Indexes on frequently queried fields
- Batch operations for bulk updates

### Memory
- LRU caching for frequently accessed data
- Lazy loading of large content
- Garbage collection of old scenes

### LLM Integration
- Token optimization via content analysis
- Request batching where possible
- Async operations for non-blocking calls
