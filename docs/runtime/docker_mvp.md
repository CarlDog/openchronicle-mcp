# Docker MVP runtime

## Build

```bash
docker build -t openchronicle-core:local .
```

## Run daemon (stdio JSON-RPC)

```bash
docker run --rm -it \
  -e OC_DB_PATH=/app/data/openchronicle.db \
  -e OC_CONFIG_DIR=/app/config \
  -e OC_PLUGIN_DIR=/app/plugins \
  -e OC_OUTPUT_DIR=/app/output \
  -v "$(pwd)/oc-data:/app/data" \
  -v "$(pwd)/oc-output:/app/output" \
  openchronicle-core:local
```

## Run selftest

```bash
docker run --rm \
  -e OC_DB_PATH=/app/data/openchronicle.db \
  -e OC_CONFIG_DIR=/app/config \
  -e OC_PLUGIN_DIR=/app/plugins \
  -e OC_OUTPUT_DIR=/app/output \
  -v "$(pwd)/oc-data:/app/data" \
  -v "$(pwd)/oc-output:/app/output" \
  openchronicle-core:local selftest --json
```

## Notes

- Default internal directories (when env vars are not set):
  - /app/data
  - /app/config
  - /app/plugins
  - /app/output
- The entrypoint creates missing directories.
- No external dependencies are required for `oc selftest`.

## Acceptance check (Windows)

```powershell
pwsh tools/docker/acceptance.ps1
```

Use `-Keep` to retain the runtime directory for debugging.
