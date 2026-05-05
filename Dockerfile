# OpenChronicle v3 — single-process ASGI image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OC_DB_PATH=/app/data/openchronicle.db \
    OC_CONFIG_DIR=/app/config \
    OC_OUTPUT_DIR=/app/output

# git is required by onboard_git (clones repos shallow into a tmpdir to
# walk their history). Without it, the tool fails with "git is not
# installed or not in PATH".
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY tools/docker/entrypoint.sh /app/entrypoint.sh

# Bake example config defaults into a non-mount path. The entrypoint
# bootstraps these into $OC_CONFIG_DIR on first run.
COPY config /config-defaults

# Upgrade install tooling first to dodge CVEs that ship with the
# python:3.11-slim base (pip 24.0, setuptools 68.1.2, wheel 0.42.0
# all flagged by pip-audit). v3 only needs MCP + the embedding
# providers (OpenAI / Ollama).
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir ".[openai,ollama,mcp]"

RUN mkdir -p /app/data /app/config /app/output \
    && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
