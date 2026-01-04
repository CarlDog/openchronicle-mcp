# 0001. Adopt Comprehensive Architecture Modernization

Date: 2025-08-09
Status: Accepted

## Context

The OpenChronicle codebase had critical architectural issues blocking development:

- Pytest collection failures due to duplicate filenames (5 main.py files, 9 orchestrator.py files)
- No proper Python packaging (incomplete pyproject.toml, no src/ layout)
- Missing development tooling (no CI/CD, linting, type checking)
- 817-line god module main.py violating SRP
- 16 top-level packages in core/ indicating architectural explosion

The "No Backwards Compatibility" philosophy encourages breaking changes for better architecture.

## Decision

We will implement a comprehensive architecture modernization using:

1. **Complete pyproject.toml** with project metadata, dependencies, and tool configurations
2. **Modern tooling stack**: ruff, black, mypy, bandit, pre-commit hooks
3. **GitHub Actions CI/CD** with linting, testing, and security scanning
4. **Systematic filename conflict resolution** using domain-specific naming
5. **Development workflow automation** with Makefile and quality gates
6. **Documentation structure** with ADRs and architecture docs

This approach prioritizes long-term maintainability over incremental fixes.

## Consequences

### Benefits

- Tests are discoverable and runnable (347 tests now working)
- Modern development workflow with automated quality gates
- Proper Python packaging enabling installation and distribution
- Clear development guidelines and tooling consistency
- Foundation for future src/ layout migration

### Costs

- Initial setup time investment
- Learning curve for new tooling
- Potential disruption during migration phases

### Risks

- Complexity of comprehensive changes
- Potential tool configuration conflicts
- Need for team alignment on new workflows

## Alternatives Considered

### Emergency Approach

- Fix only blocking pytest issues
- Minimal pyproject.toml
- Defer tooling and CI setup

**Rejected**: Would accumulate technical debt and require multiple refactoring phases.

### Hybrid Approach

- Strategic foundation + emergency fixes
- Conditional src/ migration
- Adaptive implementation

**Rejected**: Added complexity without clear benefits over comprehensive approach.

## References

- `.copilot/ARCHITECTURE_AUDIT_COMPREHENSIVE_2025_08_09.md`
- OpenChronicle development philosophy: "No Backwards Compatibility"
- Modern Python packaging guidelines: PEP 518, PEP 621
