# OpenChronicle v3 — single-process ASGI image

# ---- builder stage --------------------------------------------------------
# Installs into a venv so the runtime stage can copy just the venv, not pip's
# cache, setuptools/wheel build artifacts, or apt package lists.
FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/venv \
    PATH="/venv/bin:$PATH"

WORKDIR /app

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./

# Dependency layer: install against the lockfile without project source
# so source edits don't invalidate this slow, network-bound layer.
RUN uv venv /venv \
    && uv sync --frozen --no-dev --no-install-project --extra openai --extra ollama --extra mcp --extra metrics

COPY src ./src
RUN uv sync --frozen --no-dev --extra openai --extra ollama --extra mcp --extra metrics

# ---- runtime stage ----------------------------------------------------------
FROM python:3.14-slim

# The full git SHA this image was built from, baked to a FILE the app
# reads (openchronicle/version.py). A file, not an ENV: several commits
# legitimately share one package_version, and an env var would let a
# compose edit assert a revision the image was never built from. CI
# passes the real SHA; a local `docker build` without the arg honestly
# reports "unknown".
ARG OC_BUILD_REVISION=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OC_DB_PATH=/app/data/openchronicle.db \
    OC_CONFIG_DIR=/app/config \
    OC_OUTPUT_DIR=/app/output \
    OC_METRICS_ENABLED=false \
    PATH=/venv/bin:$PATH

# git is required by onboard_git (clones repos shallow into a tmpdir to
# walk their history). Without it, the tool fails with "git is not
# installed or not in PATH".
# gosu drops root privileges cleanly in the entrypoint (setuid+setgid+exec,
# no wrapper process — unlike su/sudo it doesn't break PID-1 signal
# forwarding for graceful shutdown).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 oc \
    && useradd --uid 1000 --gid oc --no-create-home --shell /usr/sbin/nologin oc

COPY --from=builder /venv /venv

WORKDIR /app

COPY scripts ./scripts
COPY tools/docker/entrypoint.sh /app/entrypoint.sh

# Bake example config defaults into a non-mount path. The entrypoint
# bootstraps these into $OC_CONFIG_DIR on first run.
COPY config /config-defaults

# Stays root-owned/root-executable by design: the entrypoint runs as root
# (container default — no USER instruction here) so it can chown mount
# points on every start before dropping to the unprivileged `oc` user via
# gosu. This also self-heals ownership on a volume that predates this
# change (existing NAS deployment's named volumes were populated while the
# image ran fully as root).
RUN mkdir -p /app/data /app/config /app/output \
    && chmod +x /app/entrypoint.sh \
    && printf '%s\n' "$OC_BUILD_REVISION" > /app/build-revision

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3).status==200 else 1)"

ENTRYPOINT ["/app/entrypoint.sh"]
