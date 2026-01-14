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

With OpenAI support:

```bash
pip install -e ".[openai]"
```

### Provider Selection

Control which LLM provider to use via the `OC_LLM_PROVIDER` environment variable:

- **`stub` (default)**: Uses a simple stub adapter for testing/demos
- **`openai`**: Uses OpenAI API (requires `OPENAI_API_KEY`)

```bash
# Default behavior (uses stub)
oc demo-summary <project_id> "Your text here"

# Explicitly use OpenAI
export OC_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
oc demo-summary <project_id> "Your text here"

# Override provider for a single command
export OC_LLM_PROVIDER=stub  # or unset
oc demo-summary <project_id> "Your text here" --use-openai
```

### Environment Variables

| Variable | Values | Default | Description |
| -------- | ------ | ------- | ----------- |
| `OC_LLM_PROVIDER` | `stub`, `openai` | `stub` | Selects LLM provider |
| `OPENAI_API_KEY` | API key string | - | Required when using OpenAI provider |
| `OPENAI_MODEL` | Model name | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_BASE_URL` | URL string | - | Optional custom API endpoint |
| `OC_MAX_TOKENS_PER_TASK` | Integer | - | Budget limit: blocks LLM calls if task exceeds this total token count |
| `OC_MAX_OUTPUT_TOKENS_PER_CALL` | Integer | - | Clamps max_output_tokens for each LLM request to this value |
| `OC_LLM_RPM_LIMIT` | Integer | - | Rate limit: maximum requests per minute (optional, disabled by default) |
| `OC_LLM_TPM_LIMIT` | Integer | - | Rate limit: maximum tokens per minute (optional, disabled by default) |
| `OC_LLM_MAX_WAIT_MS` | Integer | `5000` | Maximum wait time for rate limiting before failing |
| `OC_LLM_MAX_RETRIES` | Integer | `2` | Maximum retry attempts for transient LLM failures |
| `OC_LLM_MAX_RETRY_SLEEP_MS` | Integer | `2000` | Maximum sleep duration per retry attempt |
| `OC_DB_PATH` | path | `data/openchronicle.db` (dev) or `/data/openchronicle.db` (Docker) | SQLite database location |
| `OC_CONFIG_DIR` | path | `config` (dev) or `/config` (Docker) | Optional configuration directory |
| `OC_PLUGIN_DIR` | path | `plugins` (dev) or `/plugins` (Docker) | Plugin directory (explicit loading only) |

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
