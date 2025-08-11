.PHONY: help install dev-install clean lint format type test test-cov test-fast run build docs fix full-check

help:  ## Show this help
	@powershell -Command "Get-Content $(MAKEFILE_LIST) | Select-String '^[a-zA-Z_-]+:.*?## .*$$' | ForEach-Object { $$match = [regex]::Match($$_, '^([a-zA-Z_-]+):.*?## (.*)$$'); Write-Host ('{0,-20} {1}' -f $$match.Groups[1].Value, $$match.Groups[2].Value) }"

install:  ## Install production dependencies
	python -m pip install -e .

dev-install:  ## Install development dependencies and setup hooks
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev,api,llm]"
	pre-commit install
	@echo "✅ Development environment ready!"

clean:  ## Clean build artifacts and cache
	@echo "🧹 Cleaning build artifacts..."
	@powershell -Command "$$paths = @('build', 'dist', '*.egg-info', '.pytest_cache', 'htmlcov', '.coverage'); foreach($$p in $$paths) { if(Test-Path $$p) { Remove-Item $$p -Recurse -Force } }"
	@powershell -Command "Get-ChildItem -Recurse -Directory -Name '__pycache__' | ForEach-Object { Remove-Item $$_ -Recurse -Force }"
	@powershell -Command "Get-ChildItem -Recurse -File -Name '*.pyc' | Remove-Item -Force"
	@echo "✅ Clean complete!"

lint:  ## Run all linting checks
	@echo "🔍 Running linting checks..."
	python -m ruff check .
	python -m black --check .
	python -m mypy src/ --strict
	python -m bandit -r src/ --exclude tests/

format:  ## Format code with black and ruff
	@echo "🎨 Formatting code..."
	python -m black .
	python -m ruff check --fix .
	@echo "✅ Code formatted!"

type:  ## Run type checking
	@echo "🏷️ Running type checking..."
	python -m mypy src/ --strict

test:  ## Run full test suite
	@echo "🧪 Running full test suite..."
	python -m pytest tests/ -v

test-cov:  ## Run tests with coverage report
	@echo "🧪 Running tests with coverage..."
	python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=85

test-fast:  ## Run fast tests only (unit tests)
	@echo "⚡ Running fast tests..."
	python -m pytest tests/unit/ -v

test-integration:  ## Run integration tests
	@echo "🔗 Running integration tests..."
	python -m pytest tests/integration/ -v

test-performance:  ## Run performance benchmarks
	@echo "⚡ Running performance benchmarks..."
	python -m pytest tests/performance/ --benchmark-only

run:  ## Run the application
	@echo "🚀 Starting OpenChronicle..."
	python main.py

build:  ## Build package
	@echo "📦 Building package..."
	python -m build
	python -m twine check dist/*

docs:  ## Build documentation (placeholder)
	@echo "📚 Building documentation..."
	@echo "Documentation build not yet implemented"

# Development workflow shortcuts
fix: format lint  ## Format and lint code
	@echo "🔧 Code fixed and linted!"

security:  ## Run security checks
	@echo "🔒 Running security checks..."
	python -m bandit -r src/ --exclude tests/
	python -m pip-audit

pre-commit:  ## Run pre-commit hooks manually
	@echo "🛡️ Running pre-commit hooks..."
	pre-commit run --all-files

full-check: clean lint type test-cov security  ## Complete quality check
	@echo "🎯 Full quality check complete!"

init:  ## Initialize project for development
	@echo "🚀 Initializing OpenChronicle development environment..."
	$(MAKE) dev-install
	@echo "✅ Project initialized! Run 'make help' to see available commands."

status:  ## Show project status
	@echo "📊 OpenChronicle Project Status:"
	@echo "  📁 Source files: $$(powershell -Command '(Get-ChildItem src -Recurse -Filter "*.py").Count')"
	@echo "  🧪 Test files: $$(powershell -Command '(Get-ChildItem tests -Recurse -Filter "*.py").Count')"
	@echo "  📚 Documentation: $$(powershell -Command '(Get-ChildItem docs -Recurse -Filter "*.md").Count')"
	@python -c "import sys; print(f'  🐍 Python version: {sys.version.split()[0]}')"
