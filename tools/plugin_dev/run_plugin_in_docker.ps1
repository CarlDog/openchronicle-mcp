[CmdletBinding()]
param(
  [string]$Tag = "openchronicle-core:local",
  [Parameter(Mandatory = $true)]
  [string]$PluginDir,
  [string]$Handler = "",
  [string]$InputJson = "{}",
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

  Write-Host "Bootstrapping runtime (oc init)"
  $initOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    $Tag init --json

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Init failed with exit code $LASTEXITCODE"
    Write-Host $initOutput
    exit $LASTEXITCODE
  }

  if (-not $SkipSelftest) {
    Write-Host "Running container selftest"
    $selftestOutput = docker run --rm `
      -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
      -e OC_CONFIG_DIR=/app/runtime/config `
      -e OC_PLUGIN_DIR=/app/plugins `
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
  $healthOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
    $Tag rpc --request $healthRequest

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
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
    $Tag list-handlers

  if ($LASTEXITCODE -ne 0) {
    Write-Host "list-handlers failed with exit code $LASTEXITCODE"
    Write-Host $listHandlersOutput
    exit $LASTEXITCODE
  }

  $pluginHandlers = @()
  $inPluginSection = $false
  foreach ($line in $listHandlersOutput -split "`n") {
    if ($line.Trim() -eq "Plugin handlers:") {
      $inPluginSection = $true
      continue
    }
    if ($line.Trim() -eq "Built-in handlers:") {
      $inPluginSection = $false
      continue
    }
    if ($inPluginSection) {
      $trimmed = $line.Trim()
      if ($trimmed) {
        $pluginHandlers += $trimmed
      }
    }
  }

  if (-not $pluginHandlers -or $pluginHandlers.Count -eq 0) {
    Write-Error "No plugin handlers found. Check for collisions or load errors."
    Write-Host $listHandlersOutput
    exit 1
  }

  if ([string]::IsNullOrWhiteSpace($Handler)) {
    $Handler = $pluginHandlers[0]
  }

  Write-Host "Using handler: $Handler"

  Write-Host "Creating project"
  $projectId = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
    $Tag init-project "plugin-harness"

  if ($LASTEXITCODE -ne 0 -or -not $projectId) {
    Write-Error "init-project failed"
    exit 1
  }

  $inputPayload = $null
  try {
    $inputPayload = $InputJson | ConvertFrom-Json
  } catch {
    Write-Error "InputJson is not valid JSON"
    exit 1
  }

  $submitRequest = @{
    protocol_version = "1"
    command = "task.submit"
    args = @{
      project_id = $projectId.Trim()
      task_type = "plugin.invoke"
      payload = @{
        handler = $Handler
        input = $inputPayload
      }
    }
  } | ConvertTo-Json -Compress

  Write-Host "Submitting plugin.invoke task"
  $submitOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
    $Tag rpc --request $submitRequest

  if ($LASTEXITCODE -ne 0) {
    Write-Error "task.submit failed"
    Write-Host $submitOutput
    exit $LASTEXITCODE
  }

  $submitJson = $submitOutput | ConvertFrom-Json
  if (-not $submitJson.ok) {
    Write-Error "task.submit returned ok=false"
    Write-Host $submitOutput
    exit 1
  }

  $taskId = $submitJson.result.task_id
  if (-not $taskId) {
    Write-Error "task.submit did not return task_id"
    Write-Host $submitOutput
    exit 1
  }

  $runManyRequest = '{"protocol_version":"1","command":"task.run_many","args":{"limit":5,"type":"plugin.invoke","max_seconds":0}}'
  Write-Host "Running task.run_many"
  $runManyOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
    $Tag rpc --request $runManyRequest

  if ($LASTEXITCODE -ne 0) {
    Write-Error "task.run_many failed"
    Write-Host $runManyOutput
    exit $LASTEXITCODE
  }

  Write-Host "Fetching task result"
  $resultOutput = docker run --rm `
    -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
    -e OC_CONFIG_DIR=/app/runtime/config `
    -e OC_PLUGIN_DIR=/app/plugins `
    -e OC_OUTPUT_DIR=/app/runtime/output `
    -v "${RuntimeDir}:/app/runtime" `
    -v "${PluginDir}:/app/plugins/${PluginName}:ro" `
    $Tag show-task --result $taskId

  if ($LASTEXITCODE -ne 0) {
    Write-Error "show-task failed"
    Write-Host $resultOutput
    exit $LASTEXITCODE
  }

  Write-Host ""
  Write-Host "=========================================="
  Write-Host "PASS: Plugin docker harness"
  Write-Host "=========================================="
  Write-Host ""
  Write-Host "Handler result:"
  Write-Host $resultOutput

} finally {
  Cleanup
}
