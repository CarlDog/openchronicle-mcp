#!/usr/bin/env pwsh
# Auto-fix and type-check script for OpenChronicle

# Use the venv Python with absolute path
$pythonCmd = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonCmd)) {
    Write-Host "❌ Virtual environment not found at $pythonCmd" -ForegroundColor Red
    Write-Host "Please run: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "📄 Running markdownlint auto-fixes..." -ForegroundColor Cyan
& npm run lint:md:fix
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Markdownlint found issues that couldn't be auto-fixed" -ForegroundColor Yellow
}

Write-Host "`n🔧 Running Ruff auto-fixes..." -ForegroundColor Cyan
& $pythonCmd -m ruff check --fix src tests plugins
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Ruff found issues that couldn't be auto-fixed" -ForegroundColor Yellow
}

Write-Host "`n📝 Formatting code with Ruff..." -ForegroundColor Cyan
& $pythonCmd -m ruff format src tests plugins

Write-Host "`n🔍 Running mypy type checking..." -ForegroundColor Cyan
& $pythonCmd -m mypy src tests plugins --config-file=openchronicle-core/mypy.ini
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Mypy found type errors that need manual fixing" -ForegroundColor Red
    exit 1
} else {
    Write-Host "✅ All checks passed!" -ForegroundColor Green
}
