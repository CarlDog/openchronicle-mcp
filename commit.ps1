#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Smart commit helper that auto-handles pre-commit formatting changes.

.DESCRIPTION
    Commits staged files. If pre-commit hooks modify files (e.g., ruff formatting),
    automatically stages those changes and retries the commit.

.PARAMETER Message
    The commit message.

.PARAMETER AdditionalMessages
    Additional commit message lines (passed as -m flags to git).

.EXAMPLE
    .\commit.ps1 "Add feature X"
    .\commit.ps1 "Add feature X" -AdditionalMessages "- Detail 1", "- Detail 2"
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Message,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$AdditionalMessages = @()
)

$ErrorActionPreference = "Stop"

# Build git commit command
$commitArgs = @("commit", "-m", $Message)
foreach ($msg in $AdditionalMessages) {
    $commitArgs += @("-m", $msg)
}

Write-Host "🔄 Attempting commit..." -ForegroundColor Cyan

# First commit attempt
$result = & git @commitArgs 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "✅ Commit successful!" -ForegroundColor Green
    exit 0
}

# Check if pre-commit modified files
$output = $result | Out-String
if ($output -match "files were modified by this hook" -or $output -match "Fixed") {
    Write-Host "⚠️  Pre-commit modified files. Re-staging and retrying..." -ForegroundColor Yellow

    # Stage the modified files
    & git add -u

    # Retry commit
    Write-Host "🔄 Retrying commit..." -ForegroundColor Cyan
    & git @commitArgs

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Commit successful after pre-commit fixes!" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "❌ Commit failed even after pre-commit fixes" -ForegroundColor Red
        exit 1
    }
} else {
    # Some other error occurred
    Write-Host "❌ Commit failed:" -ForegroundColor Red
    Write-Host $output
    exit $exitCode
}
