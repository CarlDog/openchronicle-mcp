# OpenChronicle Utilities - MIGRATED

## ⚠️ MIGRATION NOTICE

**As of Phase 1 Architectural Modernization (2025-01-10), utilities have been migrated to their proper architectural layers:**

### Migration Mapping

| Old Location | New Location | Status |
|-------------|-------------|---------|
| `utilities/storypack_import/` | `src/openchronicle/application/services/importers/storypack/` | ✅ MIGRATED |
| `utilities/chatbot_importer/` | `src/openchronicle/application/services/importers/chatbot/` | 📋 Planned |
| `utilities/assistant_importer/` | `src/openchronicle/application/services/importers/assistant/` | 📋 Planned |

### How to Use Migrated Services

#### Storypack Import (✅ Available)
```python
# OLD (deprecated)
from utilities.storypack_import import StorypackOrchestrator

# NEW (current)
from src.openchronicle.application.services.importers.storypack import StorypackOrchestrator
```

#### CLI Usage (Updated)
```bash
# Story import command now uses the migrated services
python main.py story import ./content "My Story" --ai-enabled
```

## Remaining Legacy Files

### storypack_importer.legacy/
- **Status**: Legacy backup of old monolithic importer
- **Replacement**: Modular system in `src/openchronicle/application/services/importers/storypack/`
- **Action**: Can be removed after verification period

### chatbot_importer/ & assistant_importer/
- **Status**: Stub implementations  
- **Target**: Will be fully implemented in application services layer
- **Timeline**: Phase 2 of architectural modernization

## Benefits of Migration

### Architectural Clarity
- Import services properly positioned as application layer orchestrators
- Clean separation between CLI interface and business logic
- Better integration with hexagonal architecture patterns

### Developer Experience
- Improved IDE support and intellisense
- Cleaner import paths following Python standards
- Better testability and mocking capabilities

### Maintenance
- Services organized by domain responsibility
- Easier to extend and modify import functionality
- Consistent patterns across all import types

## For Developers

### Using Migrated Services
```python
# Import the orchestrator
from src.openchronicle.application.services.importers.storypack import StorypackOrchestrator

# Import specific components  
from src.openchronicle.application.services.importers.storypack import (
    ContentParser,
    MetadataExtractor,
    AIProcessor,
    ValidationEngine
)
```

### CLI Integration
The CLI automatically uses the migrated services. No changes needed for end users:
```bash
python main.py story import ./my-content "Adventure Story"
```

---

**Migration completed**: January 10, 2025  
**Architecture**: Hexagonal (Domain-Driven Design)  
**Integration**: Application Services Layer

## Legacy Documentation Archive

The previous comprehensive utilities documentation has been archived as `README_LEGACY.md` in this directory.
