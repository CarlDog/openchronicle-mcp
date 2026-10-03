# OpenChronicle v3 — single-process ASGI image

# ---- uv ------------------------------------------------------------------
# Pinned uv, from its own stage so Dependabot's docker ecosystem bumps the
# tag (it does not bump a `COPY --from=<image>` line; see rclone below).
# Keep the version in step with the setup-uv pins in test.yml.
FROM ghcr.io/astral-sh/uv:0.12.21 AS uv

# ---- builder stage --------------------------------------------------------
# Installs into a venv so the runtime stage can copy just the venv, not
# uv's cache, build artifacts, or apt package lists.
FROM python:3.14-slim AS builder

# Dependencies come from uv.lock, never a fresh resolve (QUAL-06): what CI
# tested is what ships, and Dependabot alerts describe this image.
# --locked fails the build when uv.lock is out of date with pyproject.toml.
# UV_PYTHON pins the venv to this image's interpreter, the same path the
# runtime stage has. UV_COMPILE_BYTECODE keeps the startup cost pip had
# (pip compiled .pyc at install; uv does not by default).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/venv \
    UV_PYTHON=/usr/local/bin/python3 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_CACHE=1

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./

# Dependency layer, without the project, so source edits don't invalidate
# this slow, network-bound layer. v3 only needs MCP, the embedding
# providers (OpenAI / Ollama) and the metrics client.
RUN uv sync --locked --no-dev --no-install-project --no-editable \
    --extra openai --extra ollama --extra mcp --extra metrics

COPY src ./src
RUN uv sync --locked --no-dev --no-editable \
    --extra openai --extra ollama --extra mcp --extra metrics

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
# age encrypts the offsite backups (design 0001). Debian's package is fine:
# age has a stable file format and no provider policy to keep up with.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git gosu age \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 oc \
    && useradd --uid 1000 --gid oc --no-create-home --shell /usr/sbin/nologin oc

# rclone pushes the encrypted backups offsite (design 0001 section 3.4). Not
# from apt: Debian's is years behind upstream, and provider OAuth policy moves
# faster than that. rclone is MIT, (c) Nick Craig-Wood; the release binary is
# static. Dependabot does not bump COPY --from images, so the phase-end audit
# checks this tag. The RUN gate makes a missing or broken binary a build
# failure, not a runtime one.
COPY --from=rclone/rclone:1.75.1 /usr/local/bin/rclone /usr/local/bin/rclone
RUN rclone version && age --version

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
