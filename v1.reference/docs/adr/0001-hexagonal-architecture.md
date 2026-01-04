# ADR-001: Hexagonal Architecture Adoption

**Status**: Accepted
**Date**: 2025-08-09
**Deciders**: OpenChronicle Team

## Context

### Problem Statement

The project started with a monolithic structure in the `core/` directory, leading to:

- Tight coupling between business logic and external concerns
- Difficulty testing components in isolation
- Unclear dependency relationships
- Hard to maintain and extend codebase

### Constraints

- Must maintain existing functionality during migration
- No breaking changes to user-facing interfaces
- Preserve excellent test coverage (96.7%)
- Limited development resources for migration

## Decision

### Chosen Approach

Adopt hexagonal (ports and adapters) architecture with the following structure:

```
src/openchronicle/
├── domain/          # Core business logic, entities, services
├── application/     # Use cases, commands, queries, orchestration
├── infrastructure/  # External service adapters (DB, LLM, cache)
├── interfaces/      # User-facing adapters (CLI, API, web)
└── shared/         # Cross-cutting concerns
```

### Alternatives Considered

- **Layered Architecture**: Rejected due to potential for layer violations
- **Microservices**: Rejected as premature for current scale
- **Keep Monolithic**: Rejected due to maintenance burden

## Consequences

### Positive

- Clear separation of concerns and dependency boundaries
- Easier testing through dependency injection
- Flexible infrastructure swapping (database, LLM providers)
- Better code organization and discoverability
- Support for test-driven development

### Negative

- Initial migration effort required
- More complex project structure
- Learning curve for new developers
- Potential over-engineering for simple features

### Neutral

- More files and directories to navigate
- Different import patterns required
- Need to establish new conventions

## Implementation

### Action Items

- [x] Create `src/openchronicle/` structure
- [x] Implement domain entities and services
- [x] Build application layer with CQRS
- [x] Create infrastructure adapters
- [x] Implement user interfaces
- [ ] Migrate legacy `core/` code (Phase 1)
- [ ] Remove dual architecture

### Validation

- All tests continue to pass during migration
- No functionality regression
- Improved development velocity post-migration
- Easier addition of new features

## References

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- Project migration plan: `.copilot/ARCHITECTURAL_MIGRATION_PHASES.md`
