[CmdletBinding()]
param(
  [string]$Tag = "openchronicle-core:local",
  [switch]$Keep,
  [switch]$SkipHealth
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$RuntimeDir = Join-Path $env:TEMP "openchronicle-docker-acceptance"

function Cleanup {
  if (-not $Keep) {
    if (Test-Path $RuntimeDir) {
      Remove-Item -Recurse -Force $RuntimeDir
    }
  }
}

try {
  if (Test-Path $RuntimeDir) {
    Remove-Item -Recurse -Force $RuntimeDir
  }
  New-Item -ItemType Directory -Path $RuntimeDir | Out-Null

  Write-Host "Building image $Tag"
  docker build -t $Tag $RepoRoot

  Write-Host "Bootstrapping runtime (oc init)"
  $initOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/runtime/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    $Tag init --json

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Init container failed with exit code $LASTEXITCODE"
    Write-Host $initOutput
    exit $LASTEXITCODE
  }

  Write-Host "Running container selftest"
  $selftestOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/runtime/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    $Tag selftest --json

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Selftest container failed with exit code $LASTEXITCODE"
    Write-Host $selftestOutput
    exit $LASTEXITCODE
  }

  $selftestJson = $null
  try {
    $selftestJson = $selftestOutput | ConvertFrom-Json
  } catch {
    Write-Error "Selftest output is not valid JSON"
    Write-Host $selftestOutput
    exit 1
  }

  if (-not $selftestJson.ok) {
    Write-Error "Selftest returned ok=false"
    Write-Host $selftestOutput
    exit 1
  }

  if (-not $SkipHealth) {
    Write-Host "Running system.health RPC"
    # Escape double quotes for PowerShell -> Docker command line passing
    $healthRequest = '{"protocol_version":"1","command":"system.health","args":{}}' -replace '"', '\"'
    $healthOutput = docker run --rm `
      -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
      -e OC_CONFIG_DIR=/app/runtime/config `
      -e OC_PLUGIN_DIR=/app/runtime/plugins `
      -e OC_OUTPUT_DIR=/app/runtime/output `
      -v "${RuntimeDir}:/app/runtime" `
      $Tag rpc --request "$healthRequest"

    if ($LASTEXITCODE -ne 0) {
      Write-Error "Health RPC failed with exit code $LASTEXITCODE"
      Write-Host $healthOutput
      exit $LASTEXITCODE
    }

    $healthJson = $null
    try {
      $healthJson = $healthOutput | ConvertFrom-Json
    } catch {
      Write-Error "Health RPC output is not valid JSON"
      Write-Host $healthOutput
      exit 1
    }

    if (-not $healthJson.ok) {
      Write-Error "Health RPC returned ok=false"
      Write-Host $healthOutput
      exit 1
    }

    if (-not $healthJson.result.storage -or -not $healthJson.result.config) {
      Write-Error "Health RPC result missing expected fields"
      Write-Host $healthOutput
      exit 1
    }
  }

  Write-Host "Running acceptance workflow"
  $acceptanceOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/runtime/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -e OC_ACCEPTANCE_PROVIDER=stub `
    -v "${RuntimeDir}:/app/runtime" `
    $Tag acceptance --json

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Acceptance workflow failed with exit code $LASTEXITCODE"
    Write-Host $acceptanceOutput
    exit $LASTEXITCODE
  }

  Write-Host "Running list-handlers"
  $handlersOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/runtime/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    $Tag list-handlers

  if ($LASTEXITCODE -ne 0) {
    Write-Error "list-handlers failed with exit code $LASTEXITCODE"
    Write-Host $handlersOutput
    exit $LASTEXITCODE
  }

  Write-Host "PASS: Docker acceptance check"
} finally {
  Cleanup
}
