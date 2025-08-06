# Architecture Migration Patterns

This document provides guidance for migrating existing OpenChronicle code to use the standardized architecture frameworks implemented in Phase 2.

## Dependency Injection Migration

### From Manual Dependency Wiring → DI Container

**OLD PATTERN (Remove):**
```python
class TimelineOrchestrator:
    def __init__(self, story_id: str):
        # Manual dependency instantiation
        self.database = DatabaseOrchestrator()
        self.memory = MemoryOrchestrator() 
        self.context = ContextOrchestrator()
```

**NEW PATTERN (Use):**
```python
from core.shared.di_orchestrators import DIEnabledOrchestrator
from core.shared.service_interfaces import IDatabaseOrchestrator, IMemoryOrchestrator

class TimelineOrchestrator(DIEnabledOrchestrator):
    def _initialize_dependencies(self):
        # Dependencies resolved via DI container
        self.database = self.resolve(IDatabaseOrchestrator)
        self.memory = self.resolve(IMemoryOrchestrator)
        self.context = self.resolve(IContextOrchestrator)
```

## Error Handling Migration

### From Generic Exception Handling → Structured Error Framework

**OLD PATTERN (Remove):**
```python
def get_character_memory(self, character_id: str):
    try:
        # Operation that might fail
        return {"character_id": character_id, "memories": []}
    except Exception:
        return {}  # Silent failure, no context
```

**NEW PATTERN (Use):**
```python
from core.shared.error_handling import memory_error_handling, MemoryError, ErrorContext

@memory_error_handling(fallback_result={"character_id": None, "memories": [], "status": "error"})
async def get_character_memory(self, character_id: str):
    if not character_id:
        raise MemoryError(
            "Character ID is required for memory retrieval",
            character_id=character_id,
            context=ErrorContext(
                component="memory_orchestrator",
                operation="get_character_memory"
            )
        )
    return {"character_id": character_id, "memories": [...]}
```

## Migration Strategy

1. **Identify target orchestrator** for migration
2. **Apply DI pattern** - inherit from `DIEnabledOrchestrator` 
3. **Apply error handling** - add `@with_error_handling` decorators
4. **Remove old patterns** - delete manual dependency wiring and generic exception handling
5. **Test thoroughly** - ensure new patterns work correctly
6. **Delete deprecated code** - no backwards compatibility layers

## Key Benefits

- **DI Framework**: Better testability, reduced coupling, cleaner architecture
- **Error Handling**: Structured errors with context, automatic recovery, consistent logging
- **Clean Codebase**: No deprecated patterns, optimized for maintainability

## Implementation Files

- **DI Framework**: `core/shared/dependency_injection.py`, `core/shared/service_interfaces.py`
- **Error Handling**: `core/shared/error_handling.py`
- **Base Classes**: `core/shared/di_orchestrators.py`
- **Service Config**: `core/shared/service_configuration.py`

---

**Note**: Following OpenChronicle's philosophy, old patterns should be completely removed once migration is complete. No compatibility layers are maintained.
