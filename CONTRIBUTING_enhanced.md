# Contributing to OpenChronicle

Thank you for your interest in contributing to OpenChronicle! This document outlines the process and guidelines for contributing to our AI-powered narrative engine.

## 🏛️ Architecture Principles

OpenChronicle follows **hexagonal architecture** with strict layer boundaries:

- **Domain Layer**: Pure business logic, no external dependencies
- **Application Layer**: Use cases and workflows  
- **Infrastructure Layer**: External integrations (databases, APIs, LLMs)
- **Interface Layer**: User interfaces (CLI, API, web)

**⚠️ CRITICAL: NO BACKWARDS COMPATIBILITY POLICY**
We embrace breaking changes for better architecture. When designing improvements, implement them completely and remove old approaches entirely.

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ 
- Git
- PowerShell (Windows) or Bash (Linux/macOS)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/OpenChronicle/openchronicle-core.git
cd openchronicle-core

# Install development dependencies
make dev-install
# OR: pip install -e ".[dev,api,llm]" && pre-commit install

# Verify installation
make test-fast
```

## 📝 Development Workflow

### 1. Code Changes

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make your changes following the architecture
# - Keep domain layer pure (no external dependencies)
# - Use dependency injection for infrastructure
# - Write tests for all new functionality

# Format and lint
make fix

# Run full checks
make full-check
```

### 2. Testing Requirements

All contributions must include tests:

- **Unit tests**: Fast, isolated tests for business logic
- **Integration tests**: Cross-component interaction tests
- **Performance tests**: For performance-critical features

```bash
# Run different test suites
make test-fast          # Unit tests only
make test-integration   # Integration tests
make test-performance   # Performance benchmarks
make test-cov          # Full suite with coverage
```

**Coverage Requirements:**
- Overall: ≥85%
- Domain layer: ≥95% (critical business logic)
- New features: 100% coverage required

### 3. Quality Standards

All code must pass:

```bash
make lint      # Ruff linting
make format    # Black code formatting  
make type      # MyPy type checking
make security  # Bandit security scanning
```

Pre-commit hooks automatically enforce these standards.

## 🎯 Architecture Guidelines

### Import Rules
```python
# ✅ CORRECT: Absolute imports
from openchronicle.domain.entities import Story
from openchronicle.application.services import StoryService

# ❌ WRONG: Relative imports
from ..entities import Story
from ...services import StoryService
```

### Dependency Direction
```python
# ✅ CORRECT: Dependencies point inward
class StoryService:  # Application layer
    def __init__(self, story_repo: StoryRepository):  # Domain interface
        self._story_repo = story_repo

# ❌ WRONG: Domain depending on infrastructure
class Story:  # Domain entity
    def save(self):
        database.save(self)  # Infrastructure dependency!
```

### Error Handling
```python
# ✅ CORRECT: Custom exception hierarchy
from openchronicle.shared.errors import ValidationError, NotFoundError

def create_story(title: str) -> Story:
    if not title.strip():
        raise ValidationError("Story title cannot be empty")
```

### Configuration
```python
# ✅ CORRECT: Dependency injection
class StoryService:
    def __init__(self, config: Settings, llm_adapter: LLMAdapter):
        self._config = config
        self._llm = llm_adapter

# ❌ WRONG: Direct configuration access
class StoryService:
    def create_story(self):
        api_key = os.getenv("OPENAI_API_KEY")  # Tight coupling!
```

## 📚 Documentation Requirements

### Code Documentation
- All public APIs must have docstrings
- Complex algorithms need inline comments
- Type hints are required for all function signatures

### Architecture Decisions
For significant changes, create an ADR (Architecture Decision Record):

```bash
cp docs/adr/0001-template.md docs/adr/NNNN-your-decision.md
# Fill in the template with your decision rationale
```

### API Documentation
Update relevant documentation in `docs/` for user-facing changes.

## 🔄 Pull Request Process

### Before Submitting
1. **Rebase** your branch on latest main
2. **Run full test suite**: `make full-check`
3. **Update documentation** for any API changes
4. **Add ADR** for architectural changes

### PR Description Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (requires version bump)
- [ ] Architecture improvement
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass  
- [ ] Performance tests pass (if applicable)
- [ ] Manual testing completed

## Architecture Compliance
- [ ] Follows hexagonal architecture principles
- [ ] Domain layer remains pure
- [ ] Proper dependency injection used
- [ ] No backwards compatibility concerns

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] ADR created (if applicable)
```

### Review Process
1. **Automated checks** must pass (CI/CD pipeline)
2. **Architecture review** by maintainers
3. **Code review** by at least one other contributor
4. **Manual testing** for complex features

## 🐛 Bug Reports

Use GitHub Issues with this information:
- **Environment**: Python version, OS, dependencies
- **Steps to reproduce**: Minimal example
- **Expected vs actual behavior**
- **Logs/screenshots** if applicable

## 💡 Feature Requests

Before proposing new features:
1. **Check existing issues** for similar requests
2. **Consider architecture impact**: How does it fit the hexagonal model?
3. **Provide use cases**: Real-world scenarios
4. **Suggest implementation approach**: High-level design

## 📞 Getting Help

- **Documentation**: Check `docs/` directory
- **Architecture questions**: Create GitHub Discussion
- **Bug reports**: GitHub Issues
- **Security issues**: Email security@openchronicle.org

## 🏷️ Release Process

Releases follow semantic versioning:
- **Major**: Breaking changes, architecture overhauls
- **Minor**: New features, backwards-compatible
- **Patch**: Bug fixes, documentation updates

## 🎖️ Recognition

Contributors are recognized in:
- `CREDITS.md` file
- Release notes for significant contributions
- GitHub contributors page

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

**Thank you for contributing to OpenChronicle!** 🎭

For questions about this guide, please open a GitHub Discussion.
