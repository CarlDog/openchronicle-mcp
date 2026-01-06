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
