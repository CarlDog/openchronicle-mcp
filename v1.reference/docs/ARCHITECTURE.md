# OpenChronicle Architecture

Note: For project status, see `.copilot/project_status.json` (single source of truth).

## Overview

OpenChronicle is an AI-powered narrative engine built using hexagonal architecture principles and modern Python best practices.

**Architecture Status**: ✅ **Hexagonal Architecture Migration COMPLETE** (Phase 1 & 2)

## Architecture Principles

1. **Domain-Driven Design**: Core business logic isolated from external concerns
2. **Dependency Inversion**: High-level modules don't depend on low-level modules
3. **Single Responsibility**: Each module has one reason to change
4. **Interface Segregation**: Clients depend only on interfaces they use
5. **No Backwards Compatibility**: Embrace breaking changes for better architecture

## Current Architecture (Post-Migration Hexagonal Structure)

### Hexagonal Architecture Layers

```
src/openchronicle/
├── domain/           # Core business logic (entities, value objects, domain services)
├── application/      # Use cases and application services
├── infrastructure/   # External adapters (database, LLM, cache, etc.)
└── interfaces/      # External interfaces (API, CLI, web)
```

### Core Modules

The system consists of 13 core modules organized in clean architectural layers:

#### Domain Layer (`src/openchronicle/domain/`)

- **Entities**: Core business objects (Story, Character, Scene)
- **Value Objects**: Immutable domain concepts
- **Domain Services**: Pure business logic
- **Model Orchestrator**: LLM coordination (15+ providers)

#### Application Layer (`src/openchronicle/application/`)

- **Story Processing Service**: Core story workflow orchestration
- **Commands**: Write operations (CreateStory, UpdateCharacter, etc.)
- **Queries**: Read operations and data retrieval
- **Orchestrators**: Complex workflow coordination

#### Infrastructure Layer (`src/openchronicle/infrastructure/`)

- **LLM Adapters**: AI model integrations (OpenAI, Anthropic, Local, etc.)
- **Memory System**: Redis-backed multi-tier caching
- **Database**: SQLite/PostgreSQL persistence
- **Content Analysis**: NLP and content processing
- **Performance Monitoring**: Metrics and optimization
- **Security Framework**: Input validation and safety

#### Interface Layer (`src/openchronicle/interfaces/`)

- **CLI**: Command-line interface
- **API**: REST/GraphQL endpoints (future)
- **Web**: Web interface (future)

### Key Design Patterns

- **Orchestrator Pattern**: Central coordination of complex workflows
- **Adapter Pattern**: Pluggable LLM provider integration
- **Factory Pattern**: Dynamic model and component creation
- **Observer Pattern**: Event-driven updates and notifications

## Architecture Implementation Details

### Import Structure (✅ Clean - Phase 1 Complete)

All imports follow strict hexagonal architecture patterns:

```python
# Domain layer - no external dependencies
from src.openchronicle.domain.entities import Story, Character

# Application layer - depends on domain
from src.openchronicle.application.services import StoryProcessingService

# Infrastructure layer - implements interfaces
from src.openchronicle.infrastructure.memory import MemoryOrchestrator
```

**Achievement**: 0 problematic imports (reduced from 40+ legacy patterns)

### Testing Infrastructure (✅ Enhanced - Phase 2 Complete)

- **342 tests** with comprehensive coverage
- **Enhanced mock objects** with proper interfaces
- **Type-safe test fixtures**
- **Performance and stress testing** capabilities

### Current Status: Post-Migration Success

#### ✅ Completed Phases

1. **Phase 1**: Import cleanup and hexagonal structure establishment
2. **Phase 2**: Testing infrastructure and type annotation enhancement

#### 🎯 Architecture Benefits Realized

- **Clean separation of concerns** - Each layer has single responsibility
- **Improved testability** - Mock objects with proper interfaces
- **Better maintainability** - Clear dependency direction
- **Enhanced type safety** - Strategic type annotations added

## Migration Status

### Completed (Phase 0)

- ✅ Complete pyproject.toml with modern tooling configuration
- ✅ Pre-commit hooks with ruff, black, mypy, bandit
- ✅ GitHub Actions CI/CD pipeline
- ✅ Pytest collection fixes (347 tests now discoverable)
- ✅ Development workflow automation (Makefile)
- ✅ Environment configuration template

### In Progress (Phase 1)

- 🔄 Source layout migration to `src/openchronicle/`
- 🔄 Import path modernization
- 🔄 Entry point consolidation

### Planned (Phase 2-3)

- ⏳ Test structure mirroring
- ⏳ Type hint coverage
- ⏳ Performance optimization
- ⏳ Documentation completion

## Key Design Decisions

See `docs/adr/` for detailed architecture decision records.

## Development Workflow

### Quick Start

```bash
# Setup development environment
make dev-install

# Run quality checks
make check

# Run full test suite
make test-cov

# Format and lint code
make fix
```

### Testing Strategy

- **Unit Tests**: Fast, isolated component testing (342 tests)
- **Integration Tests**: Cross-component interaction testing
- **Performance Tests**: Benchmarking and regression testing
- **Workflow Tests**: End-to-end user journey testing

## Performance Characteristics (Phase 3 Analysis)

### Import Performance

- **Core Domain**: ~0.85s (ModelOrchestrator + dependencies)
- **Infrastructure**: ~0.45s (Cache systems)
- **Memory Overhead**: Optimized through lazy loading

### System Performance Benchmarks

```
Logging System: 1.45K ops/sec (690μs mean)
Database Operations: Async-optimized with connection pooling
Cache Performance: Multi-tier with Redis backing
```

### Performance Optimizations Implemented

1. **Lazy Loading**: Expensive imports only when needed
2. **Async Architecture**: Non-blocking operations throughout
3. **Multi-Tier Caching**: Local → Redis → Database fallback
4. **Connection Pooling**: Efficient database resource usage
5. **Import Structure**: Clean dependencies reduce startup time

### Performance Monitoring

- **Automated Benchmarks**: Integrated in CI/CD pipeline
- **Regression Detection**: Performance alerts on degradation
- **Memory Profiling**: Continuous memory usage monitoring
- **Stress Testing**: High-load scenario validation

## Contributing

See individual module documentation and ADRs for specific contribution guidelines.
