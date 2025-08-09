.PHONY: help install dev-install clean lint format type test test-cov test-fast run build docs

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
	rm -rf .pytest_cache/ .coverage htmlcov/

lint:  ## Run linting
	ruff check .
	black --check .
	mypy . --ignore-missing-imports
	bandit -r . --exclude tests/

format:  ## Format code
	black .
	ruff check --fix .

type:  ## Run type checking
	mypy . --ignore-missing-imports

test:  ## Run tests
	pytest

test-cov:  ## Run tests with coverage
	pytest --cov=. --cov-report=term-missing --cov-report=html

test-fast:  ## Run tests without coverage
	pytest --tb=short

run:  ## Run the application
	python main.py

build:  ## Build package
	python -m build

docs:  ## Build documentation
	echo "Documentation build not yet implemented"

# Development workflow shortcuts
fix: format lint  ## Format and lint code
check: lint type test-fast  ## Quick quality check
full-check: lint type test-cov  ## Complete quality check
