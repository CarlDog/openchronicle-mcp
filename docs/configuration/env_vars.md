# Environment Variables Reference

Canonical reference for all OpenChronicle environment variables.

## Core Paths

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_DB_PATH` | `data/openchronicle.db` | SQLite database location |
| `OC_CONFIG_DIR` | `config` | Configuration directory |
| `OC_PLUGIN_DIR` | `plugins` | Plugin directory |
| `OC_OUTPUT_DIR` | `output` | Output/artifacts directory |

## Provider Selection

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_LLM_PROVIDER` | `stub` | Primary LLM provider (`stub`, `openai`, `ollama`, `anthropic`) |
| `OPENAI_API_KEY` | - | Required for OpenAI provider |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `OPENAI_BASE_URL` | - | Custom OpenAI API endpoint |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.1` | Default Ollama model |

## Budget and Rate Limiting

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

## Routing and Pools

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

## Privacy Gate

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_PRIVACY_OUTBOUND_MODE` | `off` | Privacy mode (`off`, `warn`, `block`, `redact`) |
| `OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY` | `true` | Only apply to external providers |
| `OC_PRIVACY_OUTBOUND_CATEGORIES` | - | PII categories to detect (comma-separated) |
| `OC_PRIVACY_OUTBOUND_REDACT_STYLE` | `mask` | Redaction style (`mask`, `remove`) |
| `OC_PRIVACY_OUTBOUND_LOG` | `true` | Log privacy events |

## Telemetry

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_TELEMETRY_ENABLED` | `true` | Enable telemetry collection |
| `OC_TELEMETRY_PERF_ENABLED` | `true` | Enable performance telemetry |
| `OC_TELEMETRY_USAGE_ENABLED` | `true` | Enable usage telemetry |
| `OC_TELEMETRY_CONTEXT_ENABLED` | `true` | Enable context telemetry |
| `OC_TELEMETRY_MEMORY_ENABLED` | `true` | Enable memory telemetry |
| `OC_TELEMETRY_MEMORY_SELF_REPORT_ENABLED` | `false` | Enable LLM memory self-reporting |

## Router Assist (ML-based routing)

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

## Conversation Defaults

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_CONVO_TEMPERATURE` | `0.2` | LLM sampling temperature |
| `OC_CONVO_MAX_OUTPUT_TOKENS` | `512` | Maximum output tokens per turn |
| `OC_CONVO_TOP_K_MEMORY` | `8` | Number of memory items to retrieve |
| `OC_CONVO_LAST_N` | `10` | Number of prior turns in context |
| `OC_CONVO_INCLUDE_PINNED_MEMORY` | `true` | Include pinned memory items |

## Discord Bot

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `DISCORD_BOT_TOKEN` | - | Bot authentication token (required; also accepted as `token` in core.json) |
| `OC_DISCORD_GUILD_IDS` | - | CSV guild IDs for slash command sync |
| `OC_DISCORD_CHANNEL_ALLOWLIST` | - | CSV channel IDs (empty = all channels) |
| `OC_DISCORD_SESSION_STORE_PATH` | `data/discord_sessions.json` | Session persistence path |
| `OC_DISCORD_CONVERSATION_TITLE` | `Discord chat` | Default title for new conversations |
| `OC_DISCORD_HISTORY_LIMIT` | `5` | Default turn count for `/history` command |

## Plugin System

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `OC_PLUGIN_ALLOW_COLLISIONS` | `0` | Allow handler name collisions |

## See Also

- [File-Based Configuration](config_files.md) — per-concern JSON config files
  with env var overrides
