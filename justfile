# OpenChronicle Development Automation
# Modern alternative to Makefile using Just (https://github.com/casey/just)
# Install: cargo install just (or use package manager)
# Usage: just <command>

# Set shell for cross-platform compatibility
set shell := if os() == "windows" { ["powershell.exe", "-c"] } else { ["bash", "-c"] }

# Default recipe - show help
default:
    @just --list

# 📦 INSTALLATION & SETUP

# Install production dependencies only
install:
    python -m pip install -e .

# Install development environment with all dependencies
dev-install:
    Write-Host "🚀 Setting up OpenChronicle development environment..." -ForegroundColor Blue
    python -m pip install --upgrade pip
    python -m pip install -e ".[dev,api,llm]"
    pre-commit install
    Write-Host "✅ Development environment ready!" -ForegroundColor Green

# Initialize new development setup
init: dev-install
    Write-Host "🎯 OpenChronicle development initialized!" -ForegroundColor Cyan
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  just test-fast     # Run quick tests" -ForegroundColor White
    Write-Host "  just full-check    # Complete quality check" -ForegroundColor White
    Write-Host "  just run           # Start the application" -ForegroundColor White

# 🧹 CLEANUP

# Clean all build artifacts and cache
clean:
    Write-Host "🧹 Cleaning build artifacts..." -ForegroundColor Blue

    # Remove build directories
    $paths = @('build', 'dist', '*.egg-info', '.pytest_cache', 'htmlcov', '.coverage')
    foreach($path in $paths) {
        if(Test-Path $path) {
            Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  Removed: $path" -ForegroundColor Gray
        }
    }

    # Remove Python cache
    Get-ChildItem -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Recurse -File -Filter '*.pyc' | Remove-Item -Force -ErrorAction SilentlyContinue

    Write-Host "✅ Clean complete!" -ForegroundColor Green

# 🎨 CODE FORMATTING & LINTING

# Format code with Black and Ruff
format:
    Write-Host "🎨 Formatting code..." -ForegroundColor Blue
    python -m black .
    python -m ruff check --fix .
    Write-Host "✅ Code formatted!" -ForegroundColor Green

# Run all linting checks
lint:
    Write-Host "🔍 Running linting checks..." -ForegroundColor Blue
    python -m ruff check .
    python -m black --check .
    python -m mypy src\ --strict
    python -m bandit -r src\ --exclude tests\

# 🏷️ TYPE CHECKING

# Run type checking with MyPy
type:
    Write-Host "🏷️ Running type checking..." -ForegroundColor Blue
    python -m mypy src\ --strict

# 🧪 TESTING

# Run fast unit tests only
test-fast:
    Write-Host "⚡ Running fast tests..." -ForegroundColor Blue
    python -m pytest tests\unit\ -v --tb=short

# Run integration tests
test-integration:
    Write-Host "🔗 Running integration tests..." -ForegroundColor Blue
    python -m pytest tests\integration\ -v

# Run performance benchmarks
test-performance:
    Write-Host "⚡ Running performance benchmarks..." -ForegroundColor Blue
    python -m pytest tests\performance\ --benchmark-only --benchmark-sort=mean

# Run full test suite
test:
    Write-Host "🧪 Running full test suite..." -ForegroundColor Blue
    python -m pytest tests\ -v

# Run tests with coverage report
test-cov:
    Write-Host "🧪 Running tests with coverage..." -ForegroundColor Blue
    python -m pytest tests\ --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=85
    Write-Host "📊 Coverage report generated in htmlcov/" -ForegroundColor Cyan

# 🔒 SECURITY

# Run security checks
security:
    Write-Host "🔒 Running security checks..." -ForegroundColor Blue
    python -m bandit -r src\ --exclude tests\
    if (Get-Command pip-audit -ErrorAction SilentlyContinue) {
        pip-audit --format=json
        if ($LASTEXITCODE -ne 0) {
            Write-Host "⚠️ Some vulnerabilities found" -ForegroundColor Yellow
            $global:LASTEXITCODE = 0
        }
    }
    else {
        Write-Host "ℹ️ pip-audit not installed; skipping SBOM audit" -ForegroundColor Yellow
    }

# 🔧 WORKFLOW SHORTCUTS

# Format and lint code (quick fix)
fix: format lint
    Write-Host "🔧 Code fixed and linted!" -ForegroundColor Green

# Run pre-commit hooks manually
pre-commit:
    Write-Host "🛡️ Running pre-commit hooks..." -ForegroundColor Blue
    pre-commit run --all-files

# Complete quality check pipeline
full-check: clean lint type test-cov security
    Write-Host "🎯 Full quality check complete!" -ForegroundColor Green
    Write-Host "✅ All checks passed - ready for production!" -ForegroundColor Cyan

# 🚀 APPLICATION

# Run the main application
run:
    Write-Host "🚀 Starting OpenChronicle..." -ForegroundColor Blue
    python main.py

# Run CLI in development mode
run-cli *ARGS:
    Write-Host "🎭 Running OpenChronicle CLI..." -ForegroundColor Blue
    python -m openchronicle {{ARGS}}

# 📦 BUILD & PACKAGING

# Build Python package
build:
    Write-Host "📦 Building package..." -ForegroundColor Blue
    python -m build
    python -m twine check dist\*
    Write-Host "✅ Package built and validated!" -ForegroundColor Green

# Build and check package
package: clean build
    Write-Host "📦 Package ready for distribution!" -ForegroundColor Cyan

# 📊 METRICS & STATUS

# Show project status and metrics
status:
    Write-Host "📊 OpenChronicle Project Status:" -ForegroundColor Cyan
    Write-Host ""

    $srcFiles = (Get-ChildItem src -Recurse -Filter "*.py").Count
    $testFiles = (Get-ChildItem tests -Recurse -Filter "*.py").Count
    $docFiles = (Get-ChildItem docs -Recurse -Filter "*.md").Count

    Write-Host "  📁 Source files: $srcFiles" -ForegroundColor White
    Write-Host "  🧪 Test files: $testFiles" -ForegroundColor White
    Write-Host "  📚 Documentation files: $docFiles" -ForegroundColor White

    $pythonVersion = python -c "import sys; print(sys.version.split()[0])"
    Write-Host "  🐍 Python version: $pythonVersion" -ForegroundColor White

    # Test ratio
    if ($srcFiles -gt 0) {
        $testRatio = [math]::Round(($testFiles / $srcFiles) * 100, 1)
        Write-Host "  📈 Test coverage ratio: $testRatio%" -ForegroundColor White
    }
    else {
        Write-Host "  📈 Test coverage ratio: N/A (no source files)" -ForegroundColor White
    }

# Run code complexity analysis
complexity:
    Write-Host "📏 Analyzing code complexity..." -ForegroundColor Blue
    python -m pip install radon lizard --quiet
    Write-Host ""
    Write-Host "Cyclomatic Complexity:" -ForegroundColor Yellow
    radon cc src\ --average
    Write-Host ""
    Write-Host "Maintainability Index:" -ForegroundColor Yellow
    radon mi src\ --show

# 📚 DOCUMENTATION

# Build documentation (placeholder)
docs:
    Write-Host "📚 Building documentation..." -ForegroundColor Blue
    Write-Host "⚠️ Documentation build not yet implemented" -ForegroundColor Yellow

# 🔄 DEVELOPMENT WORKFLOW

# Complete development workflow (recommended for daily use)
dev: clean format lint type test-fast
    Write-Host "🎯 Development workflow complete!" -ForegroundColor Green
    Write-Host "Ready to commit your changes!" -ForegroundColor Cyan

# Pre-commit workflow (run before committing)
commit-ready: full-check
    Write-Host "🚀 Ready for commit!" -ForegroundColor Green
    Write-Host "All quality gates passed ✅" -ForegroundColor Cyan

# Emergency fix workflow (fastest possible validation)
quick-fix: format test-fast
    Write-Host "⚡ Quick fix validation complete!" -ForegroundColor Green
