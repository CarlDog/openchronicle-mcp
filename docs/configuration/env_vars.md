# Environment Variables Reference

Canonical reference for all OpenChronicle environment variables.

All `OC_*` variables follow three-layer precedence: **env var > `core.json` >
code default**. Boolean values accept `1`/`true`/`yes`/`on` (case-insensitive).

---

## Core Paths

All data-directory paths support four-layer precedence:

1. **Constructor param** (programmatic override) — wins unconditionally.
2. **Per-path env var** (e.g., `OC_DB_PATH`) — checked next.
3. **`OC_DATA_DIR`** + suffix — if `OC_DATA_DIR` is set, all paths derive from it.
4. **Hardcoded default** — last resort.

`OC_DATA_DIR` is opt-in. When unset, behavior is identical to previous versions.
When set, all data-directory paths are derived from it unless individually overridden.

| Variable                        | Default                      | Description                                                                              |
| ------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------- |
| `OC_DATA_DIR`                   | _(unset)_                    | Root data directory. When set, derives all paths below (unless individually overridden). |
| `OC_DB_PATH`                    | `data/openchronicle.db`      | SQLite database location                                                                 |
| `OC_CONFIG_DIR`                 | `config`                     | Configuration directory (model configs, `core.json`)                                     |
| `OC_PLUGIN_DIR`                 | `plugins`                    | Plugin directory                                                                         |
| `OC_OUTPUT_DIR`                 | `output`                     | Output/artifacts directory                                                               |
| `OC_ASSETS_DIR`                 | `data/assets`                | Asset storage directory (SHA-256 dedup, file-based)                                      |
| `OC_DISCORD_SESSION_STORE_PATH` | `data/discord_sessions.json` | Discord session mapping file                                                             |
| `OC_DISCORD_PID_PATH`           | `data/discord_bot.pid`       | Discord bot PID file                                                                     |

## Provider Selection and Authentication

| Variable          | Default | Description                                                                      |
| ----------------- | ------- | -------------------------------------------------------------------------------- |
| `OC_LLM_PROVIDER` | `stub`  | Primary LLM provider (`stub`, `openai`, `ollama`, `anthropic`, `groq`, `gemini`) |

### OpenAI

| Variable          | Default       | Description                                       |
| ----------------- | ------------- | ------------------------------------------------- |
| `OPENAI_API_KEY`  | -             | Required for OpenAI provider                      |
| `OPENAI_MODEL`    | `gpt-4o-mini` | OpenAI model to use                               |
| `OPENAI_BASE_URL` | -             | Custom OpenAI API endpoint (proxies, Azure, etc.) |

### Anthropic

| Variable             | Default                    | Description                     |
| -------------------- | -------------------------- | ------------------------------- |
| `ANTHROPIC_API_KEY`  | -                          | Required for Anthropic provider |
| `ANTHROPIC_MODEL`    | `claude-sonnet-4-20250514` | Anthropic model to use          |
| `ANTHROPIC_BASE_URL` | -                          | Custom Anthropic API endpoint   |

### Groq

| Variable       | Default                   | Description                |
| -------------- | ------------------------- | -------------------------- |
| `GROQ_API_KEY` | -                         | Required for Groq provider |
| `GROQ_MODEL`   | `llama-3.3-70b-versatile` | Groq model to use          |

### Gemini (Google)

| Variable         | Default            | Description                                                  |
| ---------------- | ------------------ | ------------------------------------------------------------ |
| `GEMINI_API_KEY` | -                  | Required for Gemini provider (also accepts `GOOGLE_API_KEY`) |
| `GOOGLE_API_KEY` | -                  | Alternative to `GEMINI_API_KEY`                              |
| `GEMINI_MODEL`   | `gemini-2.0-flash` | Gemini model to use                                          |

### Ollama

| Variable          | Default                  | Description                                                                          |
| ----------------- | ------------------------ | ------------------------------------------------------------------------------------ |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint                                                                  |
| `OLLAMA_HOST`     | -                        | Alias for `OLLAMA_BASE_URL` (read by `provider_facade.py` and `diagnose_runtime.py`) |
| `OLLAMA_MODEL`    | `llama3.1`               | Default Ollama model                                                                 |

## Budget and Rate Limiting

| Variable                        | Default | Description                                                              |
| ------------------------------- | ------- | ------------------------------------------------------------------------ |
| `OC_MAX_TOKENS_PER_TASK`        | -       | Budget limit per task (total tokens)                                     |
| `OC_MAX_OUTPUT_TOKENS_PER_CALL` | -       | Clamps max_output_tokens per LLM request                                 |
| `OC_BUDGET_MAX_TOKENS`          | -       | Global maximum total tokens                                              |
| `OC_BUDGET_MAX_CALLS`           | -       | Global maximum LLM calls                                                 |
| `OC_LLM_RPM_LIMIT`              | -       | Rate limit: requests per minute                                          |
| `OC_LLM_TPM_LIMIT`              | -       | Rate limit: tokens per minute                                            |
| `OC_LLM_MAX_WAIT_MS`            | `5000`  | Maximum rate limit wait time (ms)                                        |
| `OC_LLM_MAX_RETRIES`            | `2`     | Maximum retry attempts                                                   |
| `OC_LLM_MAX_RETRY_SLEEP_MS`     | `2000`  | Maximum sleep between retries (ms)                                       |
| `OC_LLM_TIMEOUT`                | -       | Global LLM request timeout (seconds). Per-model config takes precedence. |

## Routing and Pools

| Variable                         | Default                | Description                                                   |
| -------------------------------- | ---------------------- | ------------------------------------------------------------- |
| `OC_LLM_DEFAULT_MODE`            | `fast`                 | Default routing mode (`fast`, `quality`)                      |
| `OC_LLM_MODEL_FAST`              | `gpt-4o-mini`          | Model for fast mode                                           |
| `OC_LLM_MODEL_QUALITY`           | `gpt-4o`               | Model for quality mode                                        |
| `OC_LLM_FAST_POOL`               | -                      | Fast pool config (e.g., `ollama:llama3.1,openai:gpt-4o-mini`) |
| `OC_LLM_QUALITY_POOL`            | -                      | Quality pool config                                           |
| `OC_LLM_POOL_NSFW`               | -                      | NSFW-capable pool config                                      |
| `OC_LLM_PROVIDER_WEIGHTS`        | `ollama:100,openai:20` | Provider preference weights                                   |
| `OC_LLM_MAX_FALLBACKS`           | `1`                    | Maximum fallback attempts                                     |
| `OC_LLM_FALLBACK_ON_TRANSIENT`   | `1`                    | Allow fallback on transient errors                            |
| `OC_LLM_FALLBACK_ON_CONSTRAINT`  | `1`                    | Allow fallback on constraint errors                           |
| `OC_LLM_FALLBACK_ON_REFUSAL`     | `0`                    | Allow fallback on refusals                                    |
| `OC_LLM_LOW_BUDGET_THRESHOLD`    | `500`                  | Token threshold for budget-aware routing                      |
| `OC_LLM_DOWNGRADE_ON_RATE_LIMIT` | `1`                    | Downgrade mode on rate limit                                  |
| `OC_LLM_CONTEXT_MAX_TOKENS`      | -                      | Maximum context window tokens                                 |

## Router Assist (ML-based routing)

| Variable                              | Default  | Description                          |
| ------------------------------------- | -------- | ------------------------------------ |
| `OC_ROUTER_ENABLED`                   | `true`   | Enable rule-based routing            |
| `OC_ROUTER_LOG_REASONS`               | `false`  | Log routing decisions                |
| `OC_ROUTER_ASSIST_ENABLED`            | `false`  | Enable ML-assisted routing           |
| `OC_ROUTER_ASSIST_BACKEND`            | `linear` | Backend type (`linear`, `onnx`)      |
| `OC_ROUTER_ASSIST_MODEL_PATH`         | -        | Path to router model JSON            |
| `OC_ROUTER_ASSIST_TIMEOUT_MS`         | `50`     | Router assist timeout (ms)           |
| `OC_ROUTER_NSFW_ROUTE_GTE`            | `0.70`   | NSFW routing threshold               |
| `OC_ROUTER_NSFW_UNCERTAIN_GTE`        | `0.45`   | NSFW uncertainty threshold           |
| `OC_ROUTER_PERSONA_UNCERTAIN_TO_NSFW` | `true`   | Route uncertain persona to NSFW pool |

## Privacy Gate

| Variable                            | Default | Description                                                                                |
| ----------------------------------- | ------- | ------------------------------------------------------------------------------------------ |
| `OC_PRIVACY_OUTBOUND_MODE`          | `off`   | Privacy mode (`off`, `warn`, `block`, `redact`)                                            |
| `OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY` | `true`  | Only apply to external providers                                                           |
| `OC_PRIVACY_OUTBOUND_CATEGORIES`    | -       | PII categories to detect (comma-separated: `email`, `phone`, `ip`, `ssn`, `cc`, `api_key`) |
| `OC_PRIVACY_OUTBOUND_REDACT_STYLE`  | `mask`  | Redaction style (`mask`, `remove`)                                                         |
| `OC_PRIVACY_OUTBOUND_LOG`           | `true`  | Log privacy events                                                                         |

## Conversation Defaults

| Variable                         | Default | Description                        |
| -------------------------------- | ------- | ---------------------------------- |
| `OC_CONVO_TEMPERATURE`           | `0.2`   | LLM sampling temperature           |
| `OC_CONVO_MAX_OUTPUT_TOKENS`     | `512`   | Maximum output tokens per turn     |
| `OC_CONVO_TOP_K_MEMORY`          | `8`     | Number of memory items to retrieve |
| `OC_CONVO_LAST_N`                | `10`    | Number of prior turns in context   |
| `OC_CONVO_INCLUDE_PINNED_MEMORY` | `true`  | Include pinned memory items        |

## Mixture-of-Experts (MoE)

| Variable             | Default | Description                                  |
| -------------------- | ------- | -------------------------------------------- |
| `OC_MOE_ENABLED`     | `false` | Enable MoE consensus mode                    |
| `OC_MOE_MIN_EXPERTS` | `2`     | Minimum number of experts for consensus      |
| `OC_MOE_TEMPERATURE` | -       | Temperature override for MoE runs (optional) |

## Embedding

All embedding settings follow three-layer precedence: env var > `core.json`
`"embedding"` section > dataclass default. The `core.json` approach is preferred
for local development; env vars are useful for Docker/CI overrides.

| Variable                  | `core.json` key        | Default              | Description                                                                                                         |
| ------------------------- | ---------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `OC_EMBEDDING_PROVIDER`   | `embedding.provider`   | `none`               | Embedding provider (`none`, `stub`, `openai`, `ollama`). `none` disables semantic search (FTS5 keyword only).       |
| `OC_EMBEDDING_MODEL`      | `embedding.model`      | _(provider default)_ | Embedding model name. Defaults: OpenAI=`text-embedding-3-small`, Ollama=`nomic-embed-text`, Stub=`stub`.            |
| `OC_EMBEDDING_DIMENSIONS` | `embedding.dimensions` | _(provider default)_ | Override embedding dimensions. Defaults: OpenAI=1536, Ollama=768, Stub=384.                                         |
| `OC_EMBEDDING_API_KEY`    | `embedding.api_key`    | -                    | API key for embedding provider. If unset, adapter falls back to provider-specific env var (e.g., `OPENAI_API_KEY`). |
| `OC_EMBEDDING_TIMEOUT`    | `embedding.timeout`    | `30`                 | Per-request timeout in seconds for embedding API calls. Applies to both OpenAI and Ollama adapters.                 |

## Media Generation

Media generation uses the model config system — the provider is derived from the
matching model config's `provider` field. Set `OC_MEDIA_MODEL` to a model name
that has `"image_generation": true` in its `capabilities` (see `config/models/`).
Special value `"stub"` uses the deterministic test adapter (no config file needed).

| Variable           | `core.json` key | Default              | Description                                                                                                                                                            |
| ------------------ | --------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OC_MEDIA_MODEL`   | `media.model`   | _(empty — disabled)_ | Model name for generation (e.g. `stub`, `flux`, `gpt-image-1`, `imagen-3.0-generate-002`). Empty disables media generation. Provider is derived from the model config. |
| `OC_MEDIA_TIMEOUT` | `media.timeout` | `120`                | Request timeout in seconds for media generation API calls.                                                                                                             |

## Search

| Variable                 | Default | Description                                 |
| ------------------------ | ------- | ------------------------------------------- |
| `OC_SEARCH_FTS5_ENABLED` | `1`     | Enable FTS5 full-text search when available |

## Telemetry

| Variable                                  | Default | Description                                          |
| ----------------------------------------- | ------- | ---------------------------------------------------- |
| `OC_TELEMETRY_ENABLED`                    | `true`  | Enable telemetry collection                          |
| `OC_TELEMETRY_PERF_ENABLED`               | `true`  | Enable performance telemetry                         |
| `OC_TELEMETRY_USAGE_ENABLED`              | `true`  | Enable usage telemetry                               |
| `OC_TELEMETRY_CONTEXT_ENABLED`            | `true`  | Enable context telemetry                             |
| `OC_TELEMETRY_MEMORY_ENABLED`             | `true`  | Enable memory telemetry                              |
| `OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED` | `false` | Enable LLM memory self-reporting                     |
| `OC_TELEMETRY_MEMORY_SELF_REPORT_MAX_IDS` | `20`    | Max memory IDs to report per turn                    |
| `OC_TELEMETRY_MEMORY_SELF_REPORT_STRICT`  | `false` | Strict mode for self-reporting                       |
| `OC_TELEMETRY_MCP_TRACKING_ENABLED`       | `true`  | Track MCP tool invocations (name, latency, success)  |
| `OC_TELEMETRY_MOE_TRACKING_ENABLED`       | `true`  | Track MoE consensus runs (agreement, tokens, winner) |

## HTTP API

| Variable                | Default     | Description                                                  |
| ----------------------- | ----------- | ------------------------------------------------------------ |
| `OC_API_HOST`           | `127.0.0.1` | Bind address for the HTTP API server                         |
| `OC_API_PORT`           | `8000`      | Port number for the HTTP API server                          |
| `OC_API_KEY`            | -           | API key for authentication (disabled if unset)               |
| `OC_API_RATE_LIMIT_RPM` | `120`       | Rate limit: requests per minute per client                   |
| `OC_API_CORS_ORIGINS`   | -           | Comma-separated allowed origins for CORS (disabled if unset) |

## MCP Server

| Variable           | Default     | Description                         |
| ------------------ | ----------- | ----------------------------------- |
| `OC_MCP_TRANSPORT` | `stdio`     | MCP transport mode (`stdio`, `sse`) |
| `OC_MCP_HOST`      | `127.0.0.1` | Bind address for SSE transport      |
| `OC_MCP_PORT`      | `8080`      | Port for SSE transport              |

## Discord Bot

| Variable                        | Default                      | Description                                                                |
| ------------------------------- | ---------------------------- | -------------------------------------------------------------------------- |
| `DISCORD_BOT_TOKEN`             | -                            | Bot authentication token (required; also accepted as `token` in core.json) |
| `OC_DISCORD_GUILD_IDS`          | -                            | CSV guild IDs for slash command sync                                       |
| `OC_DISCORD_CHANNEL_ALLOWLIST`  | -                            | CSV channel IDs (empty = all channels)                                     |
| `OC_DISCORD_SESSION_STORE_PATH` | `data/discord_sessions.json` | Session persistence path                                                   |
| `OC_DISCORD_CONVERSATION_TITLE` | `Discord chat`               | Default title for new conversations                                        |
| `OC_DISCORD_HISTORY_LIMIT`      | `5`                          | Default turn count for `/history` command                                  |

## Plugin System

| Variable                     | Default | Description                   |
| ---------------------------- | ------- | ----------------------------- |
| `OC_PLUGIN_ALLOW_COLLISIONS` | `0`     | Allow handler name collisions |

## Git Onboarding (`onboard_git` MCP tool)

| Variable       | Default   | Description                                                                                                                                                                                                                                                                                                                                                                                                                         |
| -------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OC_GIT_TOKEN` | _(unset)_ | GitHub PAT used by `onboard_git` to clone private repos. Fine-grained PAT with `contents:read` scope is sufficient. Injected as a bearer header via `GIT_CONFIG_PARAMETERS` (kept off argv). Scoped to `https://github.com/` requests only — won't be sent to other hosts. github.com only in v1; other hosts (GitLab, Bitbucket, etc.) would need their own host-scoped token vars. Without it, only public github.com repos work. |

## Docker Overrides

When running in Docker, these paths are typically overridden:

| Variable        | Docker Default           | Description                 |
| --------------- | ------------------------ | --------------------------- |
| `OC_DB_PATH`    | `/data/openchronicle.db` | Database inside data volume |
| `OC_CONFIG_DIR` | `/config`                | Config volume mount         |
| `OC_PLUGIN_DIR` | `/plugins`               | Plugin volume mount         |
| `OC_OUTPUT_DIR` | `/output`                | Output volume mount         |
| `OC_ASSETS_DIR` | `/assets`                | Asset storage volume mount  |

See `docker-compose.yml` and `.env.example` for reference.

## NAS Deployment — Portainer-Tunable Vars

The NAS-hosted OC stack (`docker-compose.nas.yml`) plumbs a curated subset of
the env vars on this page through to the running containers. Setting a var on
the Portainer stack only affects the container if it's listed in the compose
file's `x-oc-env` block.

Currently exposed (set via Portainer UI → Stacks → openchronicle-mcp →
Environment variables, then click "Update the stack"):

| Group               | Variables                                                                                                                                                                                                                                                                                  |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Provider keys       | `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`                                                                                                                                                                                   |
| Provider URLs       | `ANTHROPIC_BASE_URL`, `OLLAMA_HOST`, `OPENAI_BASE_URL`                                                                                                                                                                                                                                     |
| Per-provider models | `ANTHROPIC_MODEL`, `GEMINI_MODEL`, `GROQ_MODEL`, `OLLAMA_MODEL`, `OPENAI_MODEL`                                                                                                                                                                                                            |
| Routing             | `OC_LLM_PROVIDER`, `OC_LLM_DEFAULT_MODE`, `OC_LLM_MODEL_FAST`, `OC_LLM_MODEL_QUALITY`, `OC_LLM_FAST_POOL`, `OC_LLM_QUALITY_POOL`, `OC_LLM_POOL_NSFW`, `OC_LLM_PROVIDER_WEIGHTS`                                                                                                            |
| MoE                 | `OC_MOE_ENABLED`, `OC_MOE_MIN_EXPERTS`, `OC_MOE_TEMPERATURE`                                                                                                                                                                                                                               |
| Embedding           | `OC_EMBEDDING_API_KEY`, `OC_EMBEDDING_MODEL`, `OC_EMBEDDING_PROVIDER`                                                                                                                                                                                                                      |
| HTTP API            | `OC_API_KEY`, `OC_API_CORS_ORIGINS` (serve service only)                                                                                                                                                                                                                                   |
| Discord bot         | `DISCORD_BOT_TOKEN` (gates the whole bot — unset = no-op exit), `OC_DISCORD_GUILD_IDS`, `OC_DISCORD_CHANNEL_ALLOWLIST`, `OC_DISCORD_CONVERSATION_TITLE`, `OC_DISCORD_HISTORY_LIMIT` (discord service only — `OC_DISCORD_SESSION_STORE_PATH` is hardcoded to `/data/discord_sessions.json`) |
| Git onboarding      | `OC_GIT_TOKEN`                                                                                                                                                                                                                                                                             |

Vars on this page **not** in the table above are either OC-internal (paths,
limits with sane defaults) or specific to interfaces not currently deployed
on the NAS (MCP-stdio, etc.). To expose more, add them to the `x-oc-env`
block (or a service-specific block like discord's) in `docker-compose.nas.yml`
and redeploy.

## See Also

- [File-Based Configuration](config_files.md) — per-concern JSON config files
  with env var overrides
