# OpenChronicle Core v2 (clean slate)

This branch introduces a fresh orchestration core intended for a manager/supervisor/worker LLM system. The prior implementation now lives in `v1.reference/` as a frozen snapshot.

Key points:

- New source root: `src/openchronicle/`
- Plugins root: `plugins/`
- V1 snapshot: `v1.reference/` (read-only reference)

Use `oc --help` after installing in editable mode (`pip install -e .`) to explore the minimal CLI.

## LLM Provider Configuration

OpenChronicle supports multiple LLM providers via explicit configuration:

### Installation

Base installation (includes stub provider):

```bash
pip install -e .
```

With provider support:

```bash
pip install -e ".[openai]"   # OpenAI support
pip install -e ".[ollama]"   # Ollama local inference (requires httpx)
pip install -e ".[dev]"      # Development dependencies
```

### Provider Selection

Control which LLM provider to use via the `OC_LLM_PROVIDER` environment variable:

- **`stub` (default)**: Uses a deterministic stub adapter for testing/demos
- **`openai`**: Uses OpenAI API (requires `OPENAI_API_KEY`)
- **`ollama`**: Uses local Ollama instance (requires `OLLAMA_BASE_URL`)
- **`anthropic`**: Anthropic Claude API (mock implementation)

```bash
# Default behavior (uses stub)
oc demo-summary <project_id> "Your text here"

# Explicitly use OpenAI
export OC_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
oc demo-summary <project_id> "Your text here"

# Use local Ollama
export OC_LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434  # optional, this is the default
export OLLAMA_MODEL=llama3.1                   # optional default model
oc demo-summary <project_id> "Your text here"

# Override provider for a single command
oc demo-summary <project_id> "Your text here" --use-openai
```

### Environment Variables

#### Core Paths

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_DB_PATH` | `data/openchronicle.db` | SQLite database location |
| `OC_CONFIG_DIR` | `config` | Configuration directory |
| `OC_PLUGIN_DIR` | `plugins` | Plugin directory |
| `OC_OUTPUT_DIR` | `output` | Output/artifacts directory |

#### Provider Selection

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_LLM_PROVIDER` | `stub` | Primary LLM provider (`stub`, `openai`, `ollama`, `anthropic`) |
| `OPENAI_API_KEY` | - | Required for OpenAI provider |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_BASE_URL` | - | Custom OpenAI API endpoint |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.1` | Default Ollama model |

#### Budget and Rate Limiting

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_MAX_TOKENS_PER_TASK` | - | Budget limit per task (total tokens) |
| `OC_MAX_OUTPUT_TOKENS_PER_CALL` | - | Clamps max_output_tokens per LLM request |
| `OC_BUDGET_MAX_TOKENS` | - | Global maximum total tokens |
| `OC_BUDGET_MAX_CALLS` | - | Global maximum LLM calls |
| `OC_LLM_RPM_LIMIT` | - | Rate limit: requests per minute |
| `OC_LLM_TPM_LIMIT` | - | Rate limit: tokens per minute |
| `OC_LLM_MAX_WAIT_MS` | `5000` | Maximum rate limit wait time (ms) |
| `OC_LLM_MAX_RETRIES` | `2` | Maximum retry attempts |
| `OC_LLM_MAX_RETRY_SLEEP_MS` | `2000` | Maximum sleep between retries (ms) |

#### Routing and Pools

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_LLM_DEFAULT_MODE` | `fast` | Default routing mode (`fast`, `quality`) |
| `OC_LLM_MODEL_FAST` | `gpt-4o-mini` | Model for fast mode |
| `OC_LLM_MODEL_QUALITY` | `gpt-4o` | Model for quality mode |
| `OC_LLM_FAST_POOL` | - | Fast pool config (e.g., `ollama:llama3.1,openai:gpt-4o-mini`) |
| `OC_LLM_QUALITY_POOL` | - | Quality pool config |
| `OC_LLM_POOL_NSFW` | - | NSFW-capable pool config |
| `OC_LLM_PROVIDER_WEIGHTS` | `ollama:100,openai:20` | Provider preference weights |
| `OC_LLM_MAX_FALLBACKS` | `1` | Maximum fallback attempts |
| `OC_LLM_FALLBACK_ON_TRANSIENT` | `1` | Allow fallback on transient errors |
| `OC_LLM_FALLBACK_ON_CONSTRAINT` | `1` | Allow fallback on constraint errors |
| `OC_LLM_FALLBACK_ON_REFUSAL` | `0` | Allow fallback on refusals |
| `OC_LLM_LOW_BUDGET_THRESHOLD` | `500` | Token threshold for budget-aware routing |
| `OC_LLM_DOWNGRADE_ON_RATE_LIMIT` | `1` | Downgrade mode on rate limit |
| `OC_LLM_CONTEXT_MAX_TOKENS` | - | Maximum context window tokens |

#### Privacy Gate

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_PRIVACY_OUTBOUND_MODE` | `off` | Privacy mode (`off`, `warn`, `block`, `redact`) |
| `OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY` | `true` | Only apply to external providers |
| `OC_PRIVACY_OUTBOUND_CATEGORIES` | - | PII categories to detect (comma-separated) |
| `OC_PRIVACY_OUTBOUND_REDACT_STYLE` | `mask` | Redaction style (`mask`, `remove`) |
| `OC_PRIVACY_OUTBOUND_LOG` | `true` | Log privacy events |

#### Telemetry

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_TELEMETRY_ENABLED` | `true` | Enable telemetry collection |
| `OC_TELEMETRY_PERF_ENABLED` | `true` | Enable performance telemetry |
| `OC_TELEMETRY_USAGE_ENABLED` | `true` | Enable usage telemetry |
| `OC_TELEMETRY_CONTEXT_ENABLED` | `true` | Enable context telemetry |
| `OC_TELEMETRY_MEMORY_ENABLED` | `true` | Enable memory telemetry |
| `OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED` | `false` | Enable LLM memory self-reporting |

#### Router Assist (ML-based routing)

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_ROUTER_ENABLED` | `true` | Enable rule-based routing |
| `OC_ROUTER_LOG_REASONS` | `false` | Log routing decisions |
| `OC_ROUTER_ASSIST_ENABLED` | `false` | Enable ML-assisted routing |
| `OC_ROUTER_ASSIST_BACKEND` | `linear` | Backend type (`linear`, `onnx`) |
| `OC_ROUTER_ASSIST_MODEL_PATH` | - | Path to router model JSON |
| `OC_ROUTER_ASSIST_TIMEOUT_MS` | `50` | Router assist timeout |
| `OC_ROUTER_NSFW_ROUTE_GTE` | `0.70` | NSFW routing threshold |
| `OC_ROUTER_NSFW_UNCERTAIN_GTE` | `0.45` | NSFW uncertainty threshold |

#### Plugin System

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_PLUGIN_ALLOW_COLLISIONS` | `0` | Allow handler name collisions |

### Secret Management

**OpenChronicle follows a zero-secrets-in-repo policy:**

- **Do not commit** `.env.local`, `.env`, or other environment files to the repository
- **Do not commit** real API keys, tokens, or credentials to source files

**Where to store secrets:**

1. **Config files**: Model configs in `/config` directory (user-owned persistent volume in Docker, `config/` in dev)
   - These files are persistent and user-owned (not in the repo tree)
   - Plaintext config is acceptable since they live outside version control
   - Example: `config/models/openai-gpt4o.json` can contain your actual API key

2. **Environment variables**: Runtime configuration via shell exports or `.env.local`
   - Use `.env.local` for local development (git-ignored, never committed)
   - Set `OPENAI_API_KEY` and other secrets via env vars
   - `.env.example` is provided as a placeholder-only template

3. **Container secrets**: For Docker deployments
   - Use Docker secrets or environment variables passed at runtime
   - Never bake secrets into images

**Placeholders for examples:**

When documenting or creating examples, use obvious placeholders:

- `changeme`
- `replace_me`
- `your_key_here`
- `test-key` (for tests only)

The test suite (`tests/test_no_secrets_committed.py`) enforces this policy and will fail the build if real-looking secrets are detected.

## Usage Tracking and Token Budgets

OpenChronicle automatically tracks LLM usage metrics (input/output/total tokens, latency) for all API calls and stores them in the database.

### View Usage Statistics

```bash
# Show usage for a project
oc usage <project_id>

# Show only the N most recent calls
oc usage <project_id> --limit 10
```

The usage command displays:

- Total token counts (input/output/total)
- Breakdown by provider and model
- List of recent API calls with timestamps and latency

### Token Budgets

Set budget limits to control LLM costs and prevent runaway token usage:

#### Per-Task Budget

Prevents a single task from exceeding a total token limit:

```bash
export OC_MAX_TOKENS_PER_TASK=10000
oc demo-summary <project_id> "Your text"
```

If the task has already consumed 10,000+ tokens, subsequent LLM calls will:

- Raise a `BudgetExceededError`
- Emit an `llm.budget_exceeded` event
- Mark the task as failed

#### Per-Call Output Clamping

Limits the maximum output tokens for each individual LLM request:

```bash
export OC_MAX_OUTPUT_TOKENS_PER_CALL=500
oc demo-summary <project_id> "Your text"
```

Any LLM request with `max_output_tokens > 500` will be clamped to 500. The system emits an `llm.request_clamped` event when this occurs.

### Budget Events

Budget enforcement emits the following events for observability:

- `llm.budget_exceeded`: Task exceeded `OC_MAX_TOKENS_PER_TASK` limit
- `llm.request_clamped`: Output tokens were clamped due to `OC_MAX_OUTPUT_TOKENS_PER_CALL`

## Rate Limiting and Retries

OpenChronicle provides sophisticated rate limiting and retry mechanisms to handle API constraints and transient failures gracefully.

### Rate Limiting

Protect against API rate limits using token bucket algorithm. **Disabled by default** unless environment variables are set:

#### Requests Per Minute (RPM)

```bash
export OC_LLM_RPM_LIMIT=60  # Limit to 60 requests per minute
oc demo-summary <project_id> "Your text"
```

The rate limiter will automatically wait when the limit is approached. If the wait time exceeds `OC_LLM_MAX_WAIT_MS` (default 5000ms), the task fails with a clear error.

#### Tokens Per Minute (TPM)

```bash
export OC_LLM_TPM_LIMIT=100000  # Limit to 100k tokens per minute
oc demo-summary <project_id> "Your text"
```

The rate limiter estimates input tokens before each call and enforces TPM limits using the same token bucket mechanism.

#### Both Limits Combined

```bash
export OC_LLM_RPM_LIMIT=60
export OC_LLM_TPM_LIMIT=100000
export OC_LLM_MAX_WAIT_MS=10000  # Allow up to 10 seconds wait
oc demo-summary <project_id> "Your text"
```

When both are set, the rate limiter enforces whichever limit is more restrictive.

### Automatic Retries

Transient failures (429 rate limits, 5xx server errors, timeouts) are automatically retried with exponential backoff:

```bash
export OC_LLM_MAX_RETRIES=3  # Try up to 3 times (default: 2)
export OC_LLM_MAX_RETRY_SLEEP_MS=5000  # Max 5s between retries (default: 2000)
oc demo-summary <project_id> "Your text"
```

The retry policy:

- Retries on HTTP 429, 5xx errors, timeouts, and connection errors
- Uses exponential backoff with random jitter to avoid thundering herd
- Respects `Retry-After` headers when provided by the API
- Emits `llm.retry_scheduled` events for observability
- After exhausting retries, emits `llm.retry_exhausted` and fails the task

### Rate Limiting and Retry Events

These events provide full observability into rate limiting and retry behavior:

- `llm.rate_limited`: Wait occurred due to rate limit (includes wait time, RPM/TPM limits)
- `llm.rate_limit_timeout`: Rate limit wait exceeded `OC_LLM_MAX_WAIT_MS`
- `llm.retry_scheduled`: Retry attempt scheduled (includes attempt number, sleep duration, error details)
- `llm.retry_exhausted`: All retry attempts failed (includes total attempts, last error)

### Execution Order

LLM calls follow this order of operations:

1. **Budget Check**: Verify task hasn't exceeded `OC_MAX_TOKENS_PER_TASK`
2. **Rate Limiting**: Acquire RPM/TPM tokens (may wait or fail if timeout)
3. **Request**: Emit `llm.requested` event with estimated tokens
4. **API Call**: Execute with retry policy (automatic retries on transient failures)
5. **Success**: Emit `llm.completed` event and record usage to database
6. **Failure**: Emit `llm.failed` and `llm.retry_exhausted` events, fail task cleanly

## Docker (CLI-first)

The Docker setup separates **immutable core** (application code in `src/` baked into the image) from **persistent userland** (data, config, plugins, and outputs mounted on the host).

**Immutable core** (in image):

- Application code (`src/`)
- Python runtime and dependencies
- CLI entrypoint

**Persistent userland** (host-mounted):

- `/data`: SQLite DB (`OC_DB_PATH`, default `/data/openchronicle.db` in Docker)
- `/config`: Optional config files (`OC_CONFIG_DIR`), loaded only if you provide them
- `/plugins`: Optional plugins (`OC_PLUGIN_DIR`), loaded explicitly via the existing plugin loader
- `/output`: Reserved for future artifact exports (`OC_OUTPUT_DIR`, default `/output` in Docker); currently empty unless user tools write there

Note: `v1.reference/` is intentionally excluded: `.dockerignore` strips it from the build context and the Dockerfile only copies `src/`, `plugins/`, and project metadata.

### Quick start with docker run

```bash
docker run --rm \
  -v "$PWD/data:/data" \
  -v "$PWD/config:/config" \
  -v "$PWD/plugins:/plugins" \
  -v "$PWD/output:/output" \
  -e OC_DB_PATH=/data/openchronicle.db \
  -e OC_CONFIG_DIR=/config \
  -e OC_PLUGIN_DIR=/plugins \
  -e OC_OUTPUT_DIR=/output \
  openchronicle-core:latest --help
```

### Using docker compose

```bash
docker compose run --rm openchronicle --help
docker compose run --rm openchronicle smoke-live "Hello" --provider stub
```

Compose mounts persistent named volumes for `/data`, `/config`, and `/output`, and bind-mounts the repo's `./plugins` into `/plugins` so bundled/demo plugins are available immediately. If you prefer an empty, persisted plugins volume, swap `./plugins:/plugins` for a named volume in `docker-compose.yml`. Add environment overrides in `.env` (see `.env.example`); config files in `/config` are optional, env vars remain primary.

### Docker Persistence

- Default compose uses named volumes for `/data` and `/config` (recommended for portability). These persist across container updates.
- Windows host persistence (bind mounts on C:):
  1. Create host folders:

    ```powershell
    New-Item -ItemType Directory -Force -Path `
      C:\Docker\openchronicle\data, `
      C:\Docker\openchronicle\config, `
      C:\Docker\openchronicle\plugins, `
      C:\Docker\openchronicle\output | Out-Null
    ```

  1. Copy overlay:

    ```powershell
    Copy-Item docker-compose.local.example.yml docker-compose.local.yml
    ```

  1. Run with overlay:

    ```powershell
    docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm openchronicle list-projects
    ```

  1. Confirm DB on host: `C:\Docker\openchronicle\data\openchronicle.db`

  - `/plugins` is host-mounted; drop plugins into `C:\Docker\openchronicle\plugins`.
  - `/config` is host-mounted; edit configs live under `C:\Docker\openchronicle\config`.
  - Verify the mount is active (should show a bind, not an internal ext4 volume):

    ```bash
    docker compose -f docker-compose.yml -f docker-compose.local.yml run --rm openchronicle sh -lc "mount | grep ' /data '"
    ```
