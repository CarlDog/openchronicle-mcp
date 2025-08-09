# OpenChronicle Architecture Audit - August 9, 2025

**Auditor**: Senior Python Architect  
**Repository**: openchronicle-core  
**Focus**: Structure, Maintainability, Modern Python Best Practices  

---

# DELIVERABLE #1 — ARCHITECTURE AUDIT

## A) Inventory (Actual)

### Directory Tree Structure
```
openchronicle-core/                           # ❌ FLAT LAYOUT (NOT src/)
├── .github/                                  # GitHub-specific configs
│   ├── copilot-instructions.md             # AI assistant instructions
│   ├── instructions/                        # Development instructions
│   └── prompts/                             # AI prompts
├── api/                                      # ⚠️ API layer (minimal usage)
├── cli/                                      # Command-line interface
│   ├── commands/                            # CLI command modules
│   ├── lib/                                 # CLI utilities
│   ├── support/                             # CLI support functions
│   └── main.py                              # ❌ DUPLICATE ENTRY POINT
├── config/                                   # Configuration files (JSON)
├── core/                                     # ❌ MAIN APP LOGIC (16 SUBDIRS)
│   ├── adapters/                            # External integrations
│   ├── analysis/                            # Content analysis
│   ├── characters/                          # Character management
│   ├── content/                             # Content processing
│   ├── database/                            # Database operations
│   ├── images/                              # Image generation
│   ├── management/                          # System management
│   ├── memory/                              # Memory/state management
│   ├── models/                              # LLM model orchestration
│   ├── narrative/                           # Story generation
│   ├── performance/                         # Performance monitoring
│   ├── registry/                            # Model registry
│   ├── scenes/                              # Scene management
│   ├── shared/                              # ⚠️ SHARED UTILITIES (GOD MODULE)
│   ├── timeline/                            # Timeline management
│   ├── database.py                          # Legacy database module
│   ├── main.py                              # ❌ DUPLICATE ENTRY POINT
│   └── story_loader.py                      # Story loading utilities
├── docs/                                     # Documentation
├── extensions/                               # Extensions/plugins
├── import/                                   # Import utilities
├── logs/                                     # ❌ LOG FILES IN REPO
├── storage/                                  # Storage layer
├── templates/                                # Templates
├── tests/                                    # Test suite
│   ├── integration/                         # Integration tests
│   ├── mocks/                               # Mock objects
│   ├── performance/                         # Performance tests
│   ├── stress/                              # Stress tests
│   ├── unit/                                # Unit tests
│   ├── workflows/                           # Workflow tests
│   ├── conftest.py                          # Test configuration
│   ├── main.py                              # ❌ DUPLICATE ENTRY POINT
│   └── pytest.ini                           # Pytest config
├── utilities/                                # Utility scripts
│   └── main.py                              # ❌ DUPLICATE ENTRY POINT
├── main.py                                   # ❌ GOD MODULE (817 LINES!)
├── pyproject.toml                           # ❌ INCOMPLETE (PYTEST ONLY)
├── requirements.txt                         # ❌ UNPINNED DEPENDENCIES
├── Dockerfile                               # Docker configuration
└── docker-compose.yaml                     # Docker Compose setup
```

### Entry Points Identified
1. **`main.py`** (817 lines) - Primary application entry with god module antipattern
2. **`cli/main.py`** - CLI framework entry point
3. **`core/main.py`** - Core API entry point  
4. **`tests/main.py`** - Test runner entry point
5. **`utilities/main.py`** - Utilities CLI entry point

### Frameworks & Technologies Detected
- **Testing**: pytest with comprehensive markers (asyncio, integration, performance, stress)
- **AI/ML**: OpenAI, Anthropic, Transformers, PyTorch integration
- **Database**: SQLAlchemy, aiosqlite for async operations
- **Web**: FastAPI (imported but minimal usage)
- **Validation**: Pydantic for data validation
- **Caching**: Redis support via aioredis

### Cross-cutting Concerns
- **Configuration**: Mixed JSON files in `config/` + Python modules in `core/shared/`
- **Logging**: Custom system in `core/shared/logging_system.py`
- **Error Handling**: Custom framework in `core/shared/error_handling.py`
- **Security**: Security decorators and validation in `core/shared/security.py`

## B) Findings (Critical Analysis)

### **CRITICAL ISSUES**

1. **God Module Antipattern**
   - `main.py` at 817 lines (should be <100 lines)
   - Massive imports, mixed responsibilities
   - Global state management anti-pattern

2. **Packaging Violations**
   - No `src/` layout protection
   - Incomplete `pyproject.toml` (missing `[project]` section)
   - Flat package structure enables circular imports
   - No proper package metadata or console scripts

3. **Import Hell**
   - Multiple `main.py` files causing namespace conflicts
   - Relative imports mixed with absolute imports
   - Path manipulation in entry points (`sys.path.append`)

4. **Architecture Explosion**
   - 16 top-level packages in `core/` (should be 3-5 logical layers)
   - `core/shared/` becomes dumping ground for utilities
   - Unclear boundaries between domains

5. **Configuration Chaos**
   - Settings scattered across JSON files and Python modules
   - No environment-based configuration strategy
   - Hardcoded paths and ad-hoc environment reads

6. **Testing Infrastructure Problems**
   - Tests don't mirror source package structure
   - Multiple test entry points creating confusion
   - Log files committed to repository (`tests/logs/`)

### **MAINTAINABILITY ISSUES**

1. **Boundary Violations**
   - `core/shared/` mixing concerns (logging, security, config, DI)
   - Circular dependency risks between `core/` subpackages
   - No clear separation of domain logic from infrastructure

2. **Naming Inconsistencies**
   - Mix of underscore and module naming conventions
   - Generic names like `shared`, `utilities`, `management`
   - Unclear file purposes from names alone

3. **State Management**
   - Global variables in `main.py` (`USE_EMOJIS`, `_imports_loaded`)
   - Lazy import patterns indicating architectural problems
   - Mutable global state scattered across modules

## C) Gap Check vs Best Practices

| Aspect | Current | Risk/Impact | Recommendation | Effort |
|--------|---------|-------------|----------------|---------|
| **Packaging** | Flat layout, incomplete pyproject.toml | HIGH - Import conflicts, no installability | Adopt src/ layout, complete project config | L |
| **Naming** | Inconsistent, generic names | MEDIUM - Poor discoverability | Domain-driven naming, clear conventions | M |
| **Imports** | Mixed relative/absolute, path hacks | HIGH - Circular import risks | Absolute imports only, clear layers | M |
| **Typing** | No mypy configuration | MEDIUM - Runtime errors, poor IDE | Gradual mypy adoption | M |
| **Logging** | Custom system, inconsistent | MEDIUM - Poor observability | Standard logging with dictConfig | S |
| **Config** | Scattered, no env support | HIGH - Deployment complexity | Centralized pydantic-settings | M |
| **Error Handling** | Custom exceptions everywhere | MEDIUM - Debugging difficulty | Standard exception hierarchy | S |
| **Testing** | No structure mirroring, scattered | HIGH - Test maintenance nightmare | Mirror src/, fixture strategy | M |
| **Docs** | Scattered markdown files | LOW - Onboarding friction | Structured docs with ADRs | S |
| **CI** | No automation detected | CRITICAL - No quality gates | GitHub Actions pipeline | M |
| **Release** | No versioning strategy | HIGH - Deployment chaos | Semantic versioning + automation | S |

---

# DELIVERABLE #2 — TARGET-STATE BLUEPRINT

## 1) Proposed Directory Structure

```
openchronicle-core/
├── src/
│   └── openchronicle/
│       ├── domain/                          # Core business logic (no deps)
│       │   ├── entities/
│       │   │   ├── story.py
│       │   │   ├── character.py
│       │   │   └── scene.py
│       │   ├── value_objects/
│       │   │   ├── memory_state.py
│       │   │   └── narrative_context.py
│       │   └── services/
│       │       ├── story_generator.py
│       │       └── character_analyzer.py
│       ├── application/                     # Use cases & orchestration
│       │   ├── commands/
│       │   │   ├── create_story.py
│       │   │   └── generate_scene.py
│       │   ├── queries/
│       │   │   ├── get_story.py
│       │   │   └── get_character_state.py
│       │   └── orchestrators/
│       │       ├── story_orchestrator.py
│       │       └── narrative_orchestrator.py
│       ├── infrastructure/                  # External systems
│       │   ├── database/
│       │   │   ├── repositories/
│       │   │   └── migrations/
│       │   ├── llm/
│       │   │   ├── openai_adapter.py
│       │   │   ├── anthropic_adapter.py
│       │   │   └── model_registry.py
│       │   ├── storage/
│       │   │   ├── file_storage.py
│       │   │   └── blob_storage.py
│       │   └── cache/
│       │       ├── redis_cache.py
│       │       └── memory_cache.py
│       ├── interfaces/                      # External interfaces
│       │   ├── api/
│       │   │   ├── routes/
│       │   │   ├── schemas/
│       │   │   └── main.py
│       │   ├── cli/
│       │   │   ├── commands/
│       │   │   └── main.py
│       │   └── web/
│       │       └── templates/
│       ├── shared/                          # Cross-cutting concerns
│       │   ├── config/
│       │   │   ├── settings.py
│       │   │   └── environment.py
│       │   ├── logging/
│       │   │   └── setup.py
│       │   ├── exceptions/
│       │   │   ├── base.py
│       │   │   └── domain_errors.py
│       │   └── types/
│       │       └── common.py
│       └── py.typed                        # Type checking marker
├── tests/                                  # Mirrors src/ structure
│   ├── unit/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── interfaces/
│   ├── integration/
│   ├── performance/
│   ├── fixtures/
│   │   ├── data/
│   │   └── factories.py
│   └── conftest.py
├── scripts/                               # Development scripts
│   ├── setup_dev.py
│   ├── migrate_db.py
│   └── generate_fixtures.py
├── docs/                                  # Documentation
│   ├── architecture/
│   │   ├── ARCHITECTURE.md
│   │   └── DESIGN_DECISIONS.md
│   ├── adr/                              # Architecture Decision Records
│   │   ├── 0001-use-hexagonal-architecture.md
│   │   └── template.md
│   └── api/
│       └── openapi.yaml
├── ci/                                    # CI/CD configurations
│   ├── requirements/
│   │   ├── base.txt
│   │   ├── dev.txt
│   │   └── test.txt
│   └── scripts/
│       └── run_tests.sh
├── .env.example                          # Environment template
├── .gitignore
├── .pre-commit-config.yaml              # Pre-commit hooks
├── pyproject.toml                        # Complete project config
├── Dockerfile                            # Optimized Docker build
├── docker-compose.yml                    # Local development
├── Makefile                              # Development commands
└── README.md
```

## 2) Naming & Boundaries

### File & Package Naming Rules
- **snake_case** for all modules and packages
- **Descriptive names**: `story_generator.py`, not `generator.py`
- **No generic utils**: Replace `shared/` with specific packages
- **Test naming**: `test_<module_name>.py` mirrors source structure

### Import Rules & Dependencies
```python
# ALLOWED dependency directions:
# interfaces → application → domain
# infrastructure → application → domain
# shared ← all layers (but shared imports nothing)

# ABSOLUTE IMPORTS ONLY
from openchronicle.domain.entities import Story
from openchronicle.application.commands import CreateStory
from openchronicle.infrastructure.llm import OpenAIAdapter

# FORBIDDEN
from .entities import Story  # relative imports
from openchronicle.domain import infrastructure  # wrong direction
```

### Entry Point Placement
```toml
[project.scripts]
openchronicle = "openchronicle.interfaces.cli.main:main"

[project.optional-dependencies]
api = ["fastapi", "uvicorn"]
```

## 3) Configuration & Secrets

```python
# src/openchronicle/shared/config/settings.py
from pydantic_settings import BaseSettings
from typing import Literal

class Settings(BaseSettings):
    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    
    # Database
    database_url: str = "sqlite:///openchronicle.db"
    
    # LLM Configuration
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    default_model: str = "gpt-4"
    
    # Cache
    redis_url: str | None = None
    cache_ttl: int = 3600
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

# Singleton instance
settings = Settings()
```

## 4) Logging & Error Handling

### Exception Hierarchy
```python
# src/openchronicle/shared/exceptions/base.py
class OpenChronicleError(Exception):
    """Base exception for all OpenChronicle errors."""
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code

class DomainError(OpenChronicleError):
    """Domain logic violations."""

class InfrastructureError(OpenChronicleError):
    """External system failures."""

class ValidationError(OpenChronicleError):
    """Input validation errors."""
```

### Logging Configuration
```python
# src/openchronicle/shared/logging/setup.py
import logging.config
from openchronicle.shared.config import settings

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed"
        }
    },
    "loggers": {
        "openchronicle": {
            "handlers": ["console"],
            "level": settings.log_level,
            "propagate": False
        }
    },
    "root": {"level": "WARNING"}
}
```

## 5) Typing & Style

### pyproject.toml Configuration
```toml
[tool.mypy]
python_version = "3.11"
packages = ["src"]
strict = true
warn_return_any = true
warn_unused_configs = true
show_error_codes = true

[tool.ruff]
target-version = "py311"
line-length = 88
src = ["src"]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "C4",  # flake8-comprehensions
    "B",   # flake8-bugbear
    "UP",  # pyupgrade
    "SIM", # flake8-simplify
]

[tool.ruff.isort]
known-first-party = ["openchronicle"]
force-single-line = true

[tool.black]
line-length = 88
target-version = ["py311"]
```

## 6) Testing Strategy

### Test Organization
- **Unit tests**: Mirror `src/` structure exactly
- **Integration tests**: Test component interactions
- **Performance tests**: Benchmark critical paths
- **Fixtures**: Centralized in `tests/fixtures/`

### Coverage & Quality Gates
```toml
[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "scripts/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
fail_under = 85
```

## 7) Docs & Decisions

### Architecture Decision Records (ADRs)
```markdown
# docs/adr/template.md
# [NUMBER]. [TITLE]

Date: YYYY-MM-DD
Status: [Proposed|Accepted|Deprecated|Superseded]

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing/have agreed to implement?

## Consequences
What becomes easier or more difficult to do because of this change?
```

## 8) CI/CD Skeleton

### GitHub Actions Pipeline
```yaml
name: CI/CD
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install ruff black mypy
      - name: Lint
        run: ruff check src tests
      - name: Format check
        run: black --check src tests
      - name: Type check
        run: mypy src

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Test
        run: pytest --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

# DELIVERABLE #3 — PHASED IMPLEMENTATION PLAN

## Phase 0 — Baseline (Quick Wins) - 1 week

### Checklist
- [ ] Create complete `pyproject.toml` with project metadata and tool configs
- [ ] Add `.pre-commit-config.yaml` with ruff, black, isort, mypy
- [ ] Add minimal GitHub Actions CI pipeline (lint + test + type)
- [ ] Create `docs/ARCHITECTURE.md` scaffold and ADR template
- [ ] Add `.env.example` with documented environment variables
- [ ] Define proper logging configuration
- [ ] Create base exception hierarchy

### Effort: **S (Small)**
### Risks: **Low** - These are additive changes with no breaking impact
### Mitigation: Test each change incrementally
### Success Criteria:
- pyproject.toml validates with `python -m build --check`
- Pre-commit hooks run successfully
- CI pipeline executes without errors
- Basic documentation structure exists

## Phase 1 — Structure & Naming (Major Refactor) - 2 weeks

### Checklist
- [ ] Create `src/openchronicle/` directory structure
- [ ] Move `core/` packages into domain/application/infrastructure layers
- [ ] Resolve duplicate `main.py` files with clear naming
- [ ] Convert all imports to absolute paths
- [ ] Implement centralized settings with pydantic-settings
- [ ] Remove ad-hoc environment reads and global state
- [ ] Add proper `__init__.py` files with clear exports
- [ ] Update entry points in pyproject.toml

### Effort: **L (Large)**
### Risks: **HIGH** - Major refactoring with potential breaking changes
### Mitigation: 
- Create branch for migration
- Move packages incrementally with test validation
- Keep old structure until new one is fully validated
### Success Criteria:
- All imports resolve correctly
- All tests pass with new structure
- Package can be installed with `pip install -e .`
- Entry points work correctly

## Phase 2 — Testing & Typing - 2 weeks

### Checklist  
- [ ] Restructure tests to mirror `src/` layout exactly
- [ ] Create centralized fixtures in `tests/fixtures/`
- [ ] Add parametrized tests for common patterns
- [ ] Enable mypy on critical modules
- [ ] Add type hints to public interfaces
- [ ] Implement coverage gate at 75%
- [ ] Add integration test suite
- [ ] Remove log files from repository

### Effort: **M (Medium)**
### Risks: **MEDIUM** - Type checking may reveal hidden bugs
### Mitigation: Enable mypy gradually, fix type errors incrementally
### Success Criteria:
- Tests mirror source structure 1:1
- Coverage reaches 75% minimum
- Mypy passes on all typed modules
- No test files in git that shouldn't be there

## Phase 3 — Hardening & CI/CD - 1 week

### Checklist
- [ ] Add comprehensive GitHub Actions matrix (multiple Python versions)
- [ ] Implement import layering rules with ruff
- [ ] Add security scanning with bandit
- [ ] Create Makefile/justfile for common development tasks
- [ ] Add Docker optimizations (multi-stage, non-root user)
- [ ] Implement proper secret management
- [ ] Add performance regression testing
- [ ] Raise coverage gate to 85%

### Effort: **M (Medium)**
### Risks: **Low** - Infrastructure improvements with minimal code impact
### Mitigation: Test CI changes on feature branches first
### Success Criteria:
- Full CI/CD pipeline with all quality gates
- Development workflow documented and scripted
- Security best practices implemented
- Performance monitoring in place

---

# DELIVERABLE #4 — READY-TO-GENERATE ARTIFACTS

## pyproject.toml
```toml
[project]
name = "openchronicle"
version = "0.1.0"
description = "AI-powered narrative engine and storytelling platform"
authors = [
    {name = "OpenChronicle Team"},
]
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
keywords = ["ai", "storytelling", "narrative", "llm"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",
    "sqlalchemy>=2.0.0",
    "aiosqlite>=0.20.0",
    "httpx>=0.25.0",
    "tiktoken>=0.5.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
api = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
]
llm = [
    "openai>=1.0.0",
    "anthropic>=0.7.0",
    "transformers>=4.35.0",
    "torch>=2.0.0",
]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.11.0",
    "mypy>=1.7.0",
    "ruff>=0.1.0",
    "black>=23.0.0",
    "pre-commit>=3.5.0",
    "bandit>=1.7.0",
]

[project.scripts]
openchronicle = "openchronicle.interfaces.cli.main:main"

[project.urls]
Homepage = "https://github.com/OpenChronicle/openchronicle-core"
Repository = "https://github.com/OpenChronicle/openchronicle-core"
Documentation = "https://openchronicle.readthedocs.io"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config --cov=src --cov-report=term-missing"
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "performance: Performance tests",
    "slow: Slow running tests",
]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["src"]
omit = ["tests/*", "scripts/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if TYPE_CHECKING:",
    "raise AssertionError",
    "raise NotImplementedError",
]
fail_under = 85

[tool.mypy]
python_version = "3.11"
packages = ["src"]
strict = true
warn_return_any = true
warn_unused_configs = true
show_error_codes = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool"]

[tool.ruff]
target-version = "py311"
line-length = 88
src = ["src"]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "C4",   # flake8-comprehensions
    "B",    # flake8-bugbear
    "UP",   # pyupgrade
    "SIM",  # flake8-simplify
    "RET",  # flake8-return
    "ARG",  # flake8-unused-arguments
    "PTH",  # flake8-use-pathlib
    "PL",   # pylint
    "RUF",  # ruff-specific rules
]
ignore = [
    "PLR0913", # Too many arguments
    "PLR0915", # Too many statements
    "RET504",  # Unnecessary variable assignment before return
]

[tool.ruff.per-file-ignores]
"tests/**/*" = ["ARG", "PLR2004"]  # Test files can have unused args and magic values

[tool.ruff.isort]
known-first-party = ["openchronicle"]
force-single-line = true

[tool.ruff.pylint]
max-args = 7

[tool.black]
line-length = 88
target-version = ["py311"]
```

## .pre-commit-config.yaml
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-merge-conflict
      - id: check-added-large-files
      - id: debug-statements

  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black

  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [pydantic>=2.0]
        args: [--strict, --ignore-missing-imports]

  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, src/]
        exclude: tests/
```

## .github/workflows/ci.yml
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Check out code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff black mypy bandit

      - name: Lint with ruff
        run: ruff check src tests

      - name: Check formatting with black
        run: black --check src tests

      - name: Type check with mypy
        run: mypy src

      - name: Security check with bandit
        run: bandit -r src/

  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - name: Check out code
        uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        run: pytest --cov=src --cov-report=xml --cov-report=term-missing

      - name: Upload coverage to Codecov
        if: matrix.python-version == '3.11'
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true

  build:
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - name: Check out code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build

      - name: Build package
        run: python -m build

      - name: Check build
        run: python -m twine check dist/*
```

## docs/ARCHITECTURE.md
```markdown
# OpenChronicle Architecture

## Overview
OpenChronicle is an AI-powered narrative engine built using hexagonal architecture principles.

## Architecture Principles
1. **Domain-Driven Design**: Core business logic isolated from external concerns
2. **Dependency Inversion**: High-level modules don't depend on low-level modules
3. **Single Responsibility**: Each module has one reason to change
4. **Interface Segregation**: Clients depend only on interfaces they use

## Layer Structure

### Domain Layer (`src/openchronicle/domain/`)
Contains core business entities, value objects, and domain services.
- **No external dependencies**
- **Pure business logic**
- **Framework agnostic**

### Application Layer (`src/openchronicle/application/`)
Orchestrates domain objects to fulfill use cases.
- **Commands**: Write operations
- **Queries**: Read operations  
- **Orchestrators**: Complex workflows

### Infrastructure Layer (`src/openchronicle/infrastructure/`)
Implements interfaces defined by inner layers.
- **Database**: Persistence implementations
- **LLM**: AI model adapters
- **Cache**: Caching implementations
- **Storage**: File/blob storage

### Interface Layer (`src/openchronicle/interfaces/`)
External-facing interfaces.
- **API**: REST/GraphQL endpoints
- **CLI**: Command-line interface
- **Web**: Web interface (future)

## Key Design Decisions
See `docs/adr/` for detailed architecture decision records.
```

## docs/adr/template.md
```markdown
# [NUMBER]. [TITLE]

Date: YYYY-MM-DD
Status: [Proposed|Accepted|Deprecated|Superseded by ADR-XXXX]

## Context
What is the issue that we're seeing that is motivating this decision or change?

## Decision
What is the change that we're proposing or have agreed to implement?

## Consequences
What becomes easier or more difficult to do and any risks introduced by this change?

## Alternatives Considered
What other options were evaluated?

## References
- Links to discussions, RFCs, or related decisions
```

## Makefile
```makefile
.PHONY: help install dev-install clean lint format type test test-cov test-watch run build docs

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -e .

dev-install:  ## Install development dependencies
	pip install -e ".[dev,api,llm]"
	pre-commit install

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

lint:  ## Run linting
	ruff check src tests
	black --check src tests
	mypy src
	bandit -r src/

format:  ## Format code
	black src tests
	ruff check --fix src tests

type:  ## Run type checking
	mypy src

test:  ## Run tests
	pytest

test-cov:  ## Run tests with coverage
	pytest --cov=src --cov-report=term-missing --cov-report=html

test-watch:  ## Run tests in watch mode
	pytest-watch

run:  ## Run the application
	python -m openchronicle.interfaces.cli

build:  ## Build package
	python -m build

docs:  ## Build documentation
	mkdocs build
```

---

## **SUMMARY & CRITICAL NEXT STEPS**

This audit reveals a codebase with **solid functionality but critical structural issues**:

1. **Immediate Priority**: Fix the 817-line god module `main.py` and duplicate entry points
2. **High Priority**: Implement proper packaging with `src/` layout and complete `pyproject.toml`
3. **Medium Priority**: Establish CI/CD pipeline and testing standards

The proposed target state provides a **clean, maintainable architecture** that follows modern Python best practices while preserving the existing functionality. The phased implementation plan ensures **low-risk migration** with clear success criteria at each stage.
