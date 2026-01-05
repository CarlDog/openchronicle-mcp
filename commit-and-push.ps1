#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smart commit and push helper that auto-handles pre-commit formatting changes.

.DESCRIPTION
    Commits staged files and pushes to remote. If pre-commit hooks modify files,
    automatically stages those changes and retries the commit before pushing.

.PARAMETER Message
    The commit message.

.PARAMETER AdditionalMessages
    Additional commit message lines (passed as -m flags to git).

.EXAMPLE
    .\commit-and-push.ps1 "Add feature X"
    .\commit-and-push.ps1 "Add feature X" -AdditionalMessages "- Detail 1", "- Detail 2"
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Message,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$AdditionalMessages = @()
)

$ErrorActionPreference = "Stop"

# Use the commit.ps1 script
$commitScriptPath = Join-Path $PSScriptRoot "commit.ps1"

if (-not (Test-Path $commitScriptPath)) {
    Write-Host "❌ commit.ps1 not found" -ForegroundColor Red
    exit 1
}

# Execute commit
$commitArgs = @($Message) + $AdditionalMessages
& $commitScriptPath @commitArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Commit failed, aborting push" -ForegroundColor Red
    exit 1
}

# Push to remote
Write-Host "📤 Pushing to remote..." -ForegroundColor Cyan
& git push

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Pushed successfully!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "❌ Push failed" -ForegroundColor Red
    exit 1
}
