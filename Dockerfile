# CLI-first image for OpenChronicle v2
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OC_DB_PATH=/app/data/openchronicle.db \
    OC_CONFIG_DIR=/app/config \
    OC_PLUGIN_DIR=/app/plugins \
    OC_OUTPUT_DIR=/app/output

WORKDIR /app

# Copy project
COPY pyproject.toml README.md ./
COPY src ./src
COPY plugins ./plugins
COPY tools/docker/entrypoint.sh /app/entrypoint.sh

# Install core
RUN pip install --no-cache-dir .

# Prepare persistent mount points
RUN mkdir -p /app/data /app/config /app/plugins /app/output \
    && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
