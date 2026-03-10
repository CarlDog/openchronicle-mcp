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

Before running commands that rely on runtime directories, bootstrap them explicitly:

```bash
docker run --rm \
  -e OC_DB_PATH=/app/data/openchronicle.db \
  -e OC_CONFIG_DIR=/app/config \
  -e OC_PLUGIN_DIR=/app/plugins \
  -e OC_OUTPUT_DIR=/app/output \
  -v "$(pwd)/oc-data:/app/data" \
  -v "$(pwd)/oc-output:/app/output" \
  openchronicle-core:local init
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
- Runtime directories are created explicitly via `oc init`.
- No external dependencies are required for `oc selftest`.

## Acceptance check (Windows)

```powershell
pwsh tools/docker/acceptance.ps1
```

Use `-Keep` to retain the runtime directory for debugging.

## Multi-service local dev

For a full Docker Compose workflow with build-from-source, see
[Docker Local Development](docker_local_dev.md).

## Recommended post-build check

After building the image, run the CLI acceptance workflow for a deterministic smoke pass:

```bash
docker run --rm \
  -e OC_DB_PATH=/app/runtime/data/openchronicle.db \
  -e OC_CONFIG_DIR=/app/runtime/config \
  -e OC_PLUGIN_DIR=/app/runtime/plugins \
  -e OC_OUTPUT_DIR=/app/runtime/output \
  -v "$(pwd)/oc-runtime:/app/runtime" \
  openchronicle-core:local acceptance --json
```
