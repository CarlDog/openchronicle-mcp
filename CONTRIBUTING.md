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

## Development Workflow

### Prerequisites
- Python 3.11+
- Git
- PowerShell (Windows) or Bash (Linux/macOS)
- Basic understanding of hexagonal architecture

### Setup
```bash
# Clone and setup
git clone https://github.com/OpenChronicle/openchronicle-core.git
cd openchronicle-core

# Install development dependencies (choose one method)
make dev-install              # Using Make
just dev-install              # Using Just (recommended)
# OR manually:
pip install -e ".[dev,api,llm]" && pre-commit install

# Verify installation
make test-fast    # OR: just test-fast

# Install development dependencies
pip install -e ".[dev]"

# Setup pre-commit hooks
pre-commit install
```

### Development Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Follow coding standards (see below)
   - Add tests for new functionality
   - Update documentation as needed

3. **Run Quality Checks**
   ```bash
   # Linting and formatting
   ruff check .
   black --check .
   mypy .

   # Tests with coverage
   pytest --cov=src --cov-fail-under=85

   # Or use make commands
   make lint
   make test
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

5. **Submit Pull Request**
   - Push to your feature branch
   - Create PR with clear description
   - Address review feedback

## Coding Standards

### Python Style
- **Formatting**: Black (88 character line length)
- **Linting**: Ruff with project configuration
- **Import Sorting**: isort via ruff
- **Type Hints**: Required for all public APIs

### Code Organization
- **Imports**: Always use absolute imports (`from openchronicle.domain import...`)
- **Architecture**: Follow hexagonal architecture patterns
- **Dependencies**: Domain → Application → Infrastructure
- **Testing**: Mirror source structure in `tests/`

### Hexagonal Architecture Guidelines

OpenChronicle follows hexagonal (ports and adapters) architecture. Understanding these principles is essential for contributing:

#### Layer Responsibilities

1. **Domain Layer** (`src/openchronicle/domain/`)
   - **Purpose**: Core business logic, entities, value objects
   - **Dependencies**: None (pure Python, framework-agnostic)
   - **Rules**: No imports from other layers, no external dependencies
   - **Example**: Character entities, story validation rules

2. **Application Layer** (`src/openchronicle/application/`)
   - **Purpose**: Use cases, commands, queries, orchestrators
   - **Dependencies**: Domain layer only
   - **Rules**: Orchestrates domain objects, defines interfaces for infrastructure
   - **Example**: "Create Story" use case, Scene orchestrator

3. **Infrastructure Layer** (`src/openchronicle/infrastructure/`)
   - **Purpose**: External adapters (database, LLM APIs, cache, file storage)
   - **Dependencies**: Can depend on Domain and Application layers
   - **Rules**: Implements application interfaces, handles external concerns
   - **Example**: OpenAI adapter, SQLite repository, Redis cache

4. **Interface Layer** (`src/openchronicle/interfaces/`)
   - **Purpose**: External-facing interfaces (CLI, API, web)
   - **Dependencies**: Application and Infrastructure layers
   - **Rules**: Handles user interaction, request/response formatting
   - **Example**: CLI commands, FastAPI routes

#### Import Conventions

```python
# ✅ CORRECT: Absolute imports following dependency direction
from openchronicle.domain.entities.character import Character
from openchronicle.application.commands.create_story import CreateStoryCommand
from openchronicle.infrastructure.llm_adapters.openai_adapter import OpenAIAdapter

# ❌ WRONG: Relative imports
from ..entities.character import Character
from .create_story import CreateStoryCommand

# ❌ WRONG: Dependency violations (Domain importing Infrastructure)
# In domain layer:
from openchronicle.infrastructure.database import Repository  # NEVER

# ❌ WRONG: Cross-cutting dependencies
# In infrastructure:
from openchronicle.interfaces.cli import CLIHandler  # AVOID
```

#### Testing by Layer

```python
# Unit tests for Domain (tests/unit/domain/)
def test_character_validation():
    """Test domain logic with no external dependencies."""
    character = Character(name="Test", age=25)
    assert character.is_valid()

# Integration tests for Application (tests/integration/application/)
def test_create_story_workflow():
    """Test use cases with mocked infrastructure."""
    with mock.patch('openchronicle.infrastructure.llm_adapters.openai_adapter'):
        result = CreateStoryCommand().execute(story_data)
        assert result.success

# Infrastructure tests with real/mocked externals (tests/integration/infrastructure/)
def test_openai_adapter():
    """Test adapter with mocked API calls."""
    adapter = OpenAIAdapter(api_key="test")
    with mock.patch('openai.ChatCompletion.create'):
        result = adapter.generate_text("prompt")
        assert result
```

### Docstrings
Use Google-style docstrings for all public modules, classes, and functions:

```python
def process_story(story_id: str, options: dict) -> StoryResult:
    """Process a story with given options.
    
    Args:
        story_id: Unique identifier for the story
        options: Processing configuration options
        
    Returns:
        StoryResult: Processed story data and metadata
        
    Raises:
        StoryNotFoundError: If story_id doesn't exist
        ValidationError: If options are invalid
    """
```

#### Error Handling Patterns

```python
# ✅ CORRECT: Use specific exception types
from openchronicle.shared.exceptions import CharacterNotFoundError, ValidationError

def get_character(character_id: str) -> Character:
    if not character_id:
        raise ValidationError("Character ID is required")
    
    character = repository.find(character_id)
    if not character:
        raise CharacterNotFoundError(f"Character {character_id} not found")
    
    return character

# ✅ CORRECT: Wrap external errors
from openchronicle.shared.exceptions import wrap_external_error

def call_external_api():
    try:
        response = external_service.call()
        return response
    except ExternalServiceException as e:
        raise wrap_external_error(e, "external API call")
```

#### Code Review Checklist

Before submitting a PR, ensure:
- [ ] **Architecture**: Code follows hexagonal architecture patterns
- [ ] **Dependencies**: No dependency violations between layers
- [ ] **Imports**: All imports are absolute (no relative imports)
- [ ] **Types**: Type hints added for all public APIs
- [ ] **Tests**: New code has appropriate test coverage
- [ ] **Documentation**: Public APIs have docstrings
- [ ] **Quality**: All quality checks pass (`make check`)
- [ ] **Performance**: No obvious performance issues introduced

## Testing Guidelines

### Test Structure
Tests mirror the source structure and are organized by architectural layer:

```
tests/
├── unit/                              # Fast, isolated tests
│   ├── domain/                        # Pure business logic tests
│   ├── application/                   # Use case tests (with mocks)
│   └── infrastructure/                # Adapter tests (with mocks)
├── integration/                       # Cross-component tests
│   ├── workflows/                     # End-to-end workflow tests
│   └── external/                      # Tests with real external services
├── performance/                       # Performance regression tests
└── fixtures/                          # Shared test data and factories
```

### Test Requirements
- **Coverage**: Maintain 85% minimum coverage across all phases
- **Naming**: Use descriptive test names that explain the scenario
- **Structure**: Follow Arrange-Act-Assert pattern
- **Mocking**: Mock external dependencies in unit tests
- **Performance**: Include performance tests for critical paths

### Test Categories (Pytest Markers)
```python
@pytest.mark.unit          # Fast, isolated tests
@pytest.mark.integration   # Cross-component tests  
@pytest.mark.performance   # Performance tests
@pytest.mark.slow          # Tests that take >1 second
@pytest.mark.requires_api_key  # Tests requiring real API access
```

### Example Tests by Layer

#### Domain Layer Tests (Pure Logic)
```python
# tests/unit/domain/test_character.py
def test_character_creation_with_valid_data():
    """Test character creation succeeds with valid data."""
    # Arrange
    character_data = {"name": "Alice", "age": 25, "role": "protagonist"}
    
    # Act
    character = Character.create(character_data)
    
    # Assert
    assert character.name == "Alice"
    assert character.is_valid()
    assert character.role == CharacterRole.PROTAGONIST
```

#### Application Layer Tests (Mocked Dependencies)
```python
# tests/unit/application/test_create_story_command.py
@mock.patch('openchronicle.infrastructure.llm_adapters.openai_adapter.OpenAIAdapter')
def test_create_story_command_success(mock_llm):
    """Test story creation command succeeds with valid input."""
    # Arrange
    mock_llm.generate_text.return_value = "Generated story content"
    command = CreateStoryCommand(llm_adapter=mock_llm)
    story_data = {"title": "Test Story", "theme": "adventure"}
    
    # Act
    result = command.execute(story_data)
    
    # Assert
    assert result.success
    assert result.story_id is not None
    mock_llm.generate_text.assert_called_once()
```

#### Integration Tests (Real Workflows)
```python
# tests/integration/test_story_workflow.py
def test_complete_story_creation_workflow():
    """Test complete story creation from command to persistence."""
    # Arrange
    story_orchestrator = StoryOrchestrator()
    story_request = StoryCreationRequest(title="Test", theme="sci-fi")
    
    # Act
    result = story_orchestrator.create_story(story_request)
    
    # Assert
    assert result.success
    assert result.story.title == "Test"
    # Verify story was persisted
    retrieved_story = story_orchestrator.get_story(result.story.id)
    assert retrieved_story is not None
    
    # Assert
    assert result.success is True
    assert result.story_id == story_id
```

## Commit Message Format

Use conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(model): add support for new LLM provider
fix(memory): resolve race condition in memory updates
docs(readme): update installation instructions
```

## Architecture Guidelines

### Current Migration
The project is migrating from dual architecture to unified hexagonal architecture:
- **Legacy**: `core/` modules (being phased out)  
- **Modern**: `src/openchronicle/` hexagonal structure

### Contribution Areas
- **Phase 0 Tasks**: Security tools, documentation, logging
- **Phase 1 Tasks**: Legacy migration assistance
- **Testing**: Enhance test coverage and quality
- **Documentation**: Keep docs current and accurate

### Dependency Rules
- Domain layer: No external dependencies
- Application layer: Depends only on domain interfaces
- Infrastructure layer: Implements domain interfaces
- Interface layer: Coordinates application services

## Getting Help

- **Development Plan**: See `docs/DEVELOPMENT_PLAN.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Current Status**: See `.copilot/project_status.json`
- **Phase Tasks**: See `.copilot/PHASE_0_DETAILED_TASKS.md`

## Code of Conduct

- Be respectful and professional
- Focus on constructive feedback
- Embrace breaking changes for better architecture
- Prioritize code quality and maintainability

## Questions?

If you have questions about contributing, please:
1. Check existing documentation
2. Review current issues and PRs
3. Ask in discussions or create an issue

Thank you for contributing to OpenChronicle!
