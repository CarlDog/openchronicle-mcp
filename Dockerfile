# CLI-first image for OpenChronicle MCP
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OC_DB_PATH=/app/data/openchronicle.db \
    OC_CONFIG_DIR=/app/config \
    OC_PLUGIN_DIR=/app/plugins \
    OC_OUTPUT_DIR=/app/output \
    OC_ASSETS_DIR=/app/assets

# git is required by onboard_git (clones repos shallow into a tmpdir to walk
# their history). Without it, the tool fails with "git is not installed or
# not in PATH" — which is what triggered this fix.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project
COPY pyproject.toml README.md ./
COPY src ./src
COPY plugins ./plugins
COPY tools/docker/entrypoint.sh /app/entrypoint.sh

# Install with all provider extras and Discord
RUN pip install --no-cache-dir ".[openai,ollama,anthropic,groq,gemini,discord,mcp]"

# Prepare persistent mount points
RUN mkdir -p /app/data /app/config /app/plugins /app/output /app/assets \
    && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
