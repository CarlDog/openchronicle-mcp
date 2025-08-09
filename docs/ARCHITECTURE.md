# OpenChronicle Architecture

## Overview
OpenChronicle is an AI-powered narrative engine built using hexagonal architecture principles and modern Python best practices.

## Architecture Principles
1. **Domain-Driven Design**: Core business logic isolated from external concerns
2. **Dependency Inversion**: High-level modules don't depend on low-level modules
3. **Single Responsibility**: Each module has one reason to change
4. **Interface Segregation**: Clients depend only on interfaces they use
5. **No Backwards Compatibility**: Embrace breaking changes for better architecture

## Current Architecture (Pre-Migration)

### Core Modules
The system consists of 13 core modules:

- **Model Management**: LLM orchestration with 15+ providers
- **Memory System**: Character and narrative state management
- **Scene Generation**: Story scene creation and management
- **Character Engine**: Character consistency and development
- **Timeline Management**: Narrative timeline and continuity
- **Content Analysis**: Content processing and validation
- **Database Layer**: Persistent storage and retrieval
- **Performance Monitoring**: System metrics and optimization
- **Security Framework**: Input validation and security
- **Cache System**: Multi-tier caching with Redis support
- **Image Generation**: AI-powered image creation
- **Narrative Engine**: Story generation and flow
- **Registry System**: Model and provider configuration

### Key Design Patterns
- **Orchestrator Pattern**: Central coordination of complex workflows
- **Adapter Pattern**: Pluggable LLM provider integration
- **Factory Pattern**: Dynamic model and component creation
- **Observer Pattern**: Event-driven updates and notifications

## Target Architecture (Post-Migration)

### Hexagonal Architecture Layers

#### Domain Layer (`src/openchronicle/domain/`)
Contains core business entities, value objects, and domain services.
- **No external dependencies**
- **Pure business logic**
- **Framework agnostic**

#### Application Layer (`src/openchronicle/application/`)
Orchestrates domain objects to fulfill use cases.
- **Commands**: Write operations
- **Queries**: Read operations  
- **Orchestrators**: Complex workflows

#### Infrastructure Layer (`src/openchronicle/infrastructure/`)
Implements interfaces defined by inner layers.
- **Database**: Persistence implementations
- **LLM**: AI model adapters
- **Cache**: Caching implementations
- **Storage**: File/blob storage

#### Interface Layer (`src/openchronicle/interfaces/`)
External-facing interfaces.
- **API**: REST/GraphQL endpoints
- **CLI**: Command-line interface
- **Web**: Web interface (future)

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
- **Unit Tests**: Fast, isolated component testing
- **Integration Tests**: Cross-component interaction testing
- **Performance Tests**: Benchmarking and regression testing
- **Workflow Tests**: End-to-end user journey testing

## Contributing
See individual module documentation and ADRs for specific contribution guidelines.
