# Docker local development

Build and run OpenChronicle from source via Docker.

## Prerequisites

- Docker
- An OC checkout

## Build

```bash
docker build -t openchronicle:dev .
```

## Run

The image's default `ENTRYPOINT` is `oc serve` — single uvicorn
process, HTTP REST at `/api/v1/*` and MCP at `/mcp`, both on `:8000`
inside the container.

```bash
docker run --rm \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/config:/app/config" \
  -e OC_API_KEY=dev-key \
  openchronicle:dev
```

`http://127.0.0.1:8000/health` should return `{"status": "ok"}`.

## Run a one-off command

```bash
docker run --rm openchronicle:dev oc version
docker run --rm openchronicle:dev oc memory search hello
```

The entrypoint passes positional args through to the `oc` CLI.

## Embeddings

To enable hybrid semantic search:

```bash
docker run --rm \
  -p 8000:8000 \
  -e OC_EMBEDDING_PROVIDER=openai \
  -e OC_EMBEDDING_MODEL=text-embedding-3-small \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v "$(pwd)/data:/app/data" \
  openchronicle:dev
```

Or for Ollama running on the host:

```bash
docker run --rm \
  -p 8000:8000 \
  --add-host host.docker.internal:host-gateway \
  -e OC_EMBEDDING_PROVIDER=ollama \
  -e OC_EMBEDDING_MODEL=nomic-embed-text \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -v "$(pwd)/data:/app/data" \
  openchronicle:dev
```

## NAS deployment

For Portainer / Synology Container Manager use
`docker-compose.nas.yml` from the repo root. That file documents every
operator-tunable env var inline.

## See also

- `docs/configuration/env_vars.md` — full env var list
- `docs/architecture/ARCHITECTURE.md` — what runs inside the container
