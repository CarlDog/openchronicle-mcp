FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create user/group if they don't already exist
RUN if ! getent group 100; then groupadd -g 100 appuser; fi && \
    if ! id -u 1026 >/dev/null 2>&1; then useradd -u 1026 -g 100 -m -s /bin/bash appuser; fi

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    gosu \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app source to a staging location
COPY src/ /app-template/src/
COPY config/ /app-template/config/
COPY templates/ /app-template/templates/
COPY main.py /app-template/
COPY README.md /app-template/

# Prep folders and permissions
RUN mkdir -p /app-template/storage /app-template/logs && \
    chown -R 1026:100 /app-template

# One-time initializer with flexible permissions
RUN echo '#!/bin/bash\n\
# Get user/group from environment or use defaults\n\
PUID=${PUID:-1026}\n\
PGID=${PGID:-100}\n\
\n\
if [ ! -f /app/main.py ]; then\n\
  echo "Initializing app directory with template files..."\n\
  cp -r /app-template/* /app/\n\
  mkdir -p /app/storage /app/logs\n\
fi\n\
\n\
# Handle permissions flexibly for NAS environments\n\
if [ "$(id -u)" = "0" ]; then\n\
  echo "Running as root, switching to user $PUID:$PGID..."\n\
  chown -R $PUID:$PGID /app 2>/dev/null || echo "Warning: Could not change ownership, continuing..."\n\
  exec gosu $PUID:$PGID "$@"\n\
else\n\
  echo "Running as user $(id -u):$(id -g)"\n\
  # Ensure write permissions exist\n\
  chmod -R u+w /app/storage /app/logs 2>/dev/null || true\n\
  exec "$@"\n\
fi' > /usr/local/bin/init-app.sh && chmod +x /usr/local/bin/init-app.sh

# Final folder prep - don't set ownership here, let init script handle it
RUN mkdir -p /app/storage /app/logs

# Don't set USER here - let init script handle user switching

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD gosu 1026:100 python -c "import sys; exit(0)" || python -c "import sys; exit(0)" || exit 1

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/init-app.sh"]
CMD ["python", "main.py"]
