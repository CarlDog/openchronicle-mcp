$ErrorActionPreference = "Stop"

$Image = "openchronicle-core:local"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$TempDir = Join-Path $env:TEMP "openchronicle-docker-selftest"

if (Test-Path $TempDir) {
  Remove-Item -Recurse -Force $TempDir
}
New-Item -ItemType Directory -Path $TempDir | Out-Null

Write-Host "Building image $Image"
docker build -t $Image $Root

Write-Host "Running selftest"
docker run --rm `
  -e OC_DB_PATH=/app/runtime/data/openchronicle.db `
  -e OC_CONFIG_DIR=/app/runtime/config `
  -e OC_PLUGIN_DIR=/app/runtime/plugins `
  -e OC_OUTPUT_DIR=/app/runtime/output `
  -v "${TempDir}:/app/runtime" `
  $Image selftest --json

$ExitCode = $LASTEXITCODE
if ($ExitCode -ne 0) {
  Write-Error "Selftest failed with exit code $ExitCode"
  exit $ExitCode
}

Write-Host "Selftest completed successfully."
