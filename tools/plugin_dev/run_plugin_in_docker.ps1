[CmdletBinding()]
param(
  [string]$Tag = "openchronicle-core:local",
  [Parameter(Mandatory = $true)]
  [string]$PluginDir,
  [switch]$Keep,
  [switch]$SkipBuild,
  [switch]$SkipSelftest
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$RuntimeDir = Join-Path $env:TEMP "openchronicle-plugin-harness"
$PluginName = Split-Path -Leaf $PluginDir

if (-not (Test-Path $PluginDir)) {
  Write-Error "PluginDir not found: $PluginDir"
  exit 1
}

function Cleanup {
  if (-not $Keep) {
    if (Test-Path $RuntimeDir) {
      Remove-Item -Recurse -Force $RuntimeDir
    }
  }
}

try {
  if (-not $SkipBuild) {
    Write-Host "Building image $Tag"
    docker build -t $Tag $RepoRoot
  }

  if (Test-Path $RuntimeDir) {
    Remove-Item -Recurse -Force $RuntimeDir
  }
  New-Item -ItemType Directory -Path $RuntimeDir | Out-Null

  if (-not $SkipSelftest) {
    Write-Host "Running container selftest"
    $selftestOutput = docker run --rm `
      -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
      -e OC_CONFIG_DIR=/app/runtime/config `
      -e OC_OUTPUT_DIR=/app/runtime/output `
      -v "${RuntimeDir}:/app/runtime" `
      -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
      $Tag selftest --json

    if ($LASTEXITCODE -ne 0) {
      Write-Error "Selftest failed with exit code $LASTEXITCODE"
      Write-Host $selftestOutput
      exit $LASTEXITCODE
    }

    $selftestJson = $selftestOutput | ConvertFrom-Json
    if (-not $selftestJson.ok) {
      Write-Error "Selftest returned ok=false"
      Write-Host $selftestOutput
      exit 1
    }
  }

  Write-Host "Running system.health RPC"
  $healthRequest = '{"protocol_version":"1","command":"system.health","args":{}}'
  $healthOutput = docker run --rm $Tag rpc --request $healthRequest

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Health RPC failed with exit code $LASTEXITCODE"
    Write-Host $healthOutput
    exit $LASTEXITCODE
  }

  $healthJson = $healthOutput | ConvertFrom-Json
  if (-not $healthJson.ok) {
    Write-Error "Health RPC returned ok=false"
    Write-Host $healthOutput
    exit 1
  }

  Write-Host "Verifying plugin loaded successfully"
  $listHandlersOutput = docker run --rm `
    -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
    $Tag list-handlers

  if ($LASTEXITCODE -ne 0) {
    Write-Host "list-handlers failed with exit code $LASTEXITCODE"
    Write-Host $listHandlersOutput
    exit $LASTEXITCODE
  }

  Write-Host ""
  Write-Host "=========================================="
  Write-Host "PASS: Plugin docker harness"
  Write-Host "=========================================="
  Write-Host ""
  Write-Host $listHandlersOutput
  Write-Host ""
  Write-Host "Note: Plugin execution via RPC is not yet implemented."
  Write-Host "The harness currently validates:"
  Write-Host "  1. Container health (system.health)"
  Write-Host "  2. Plugin discovery and loading"
  Write-Host "  3. Handler registration"
  Write-Host ""
  Write-Host "Next step: Implement minimal RPC hook for task execution"

} finally {
  Cleanup
}
