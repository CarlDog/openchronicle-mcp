# File-Based Configuration

OpenChronicle uses a single `core.json` configuration file alongside
per-model JSON configs. Environment variables override any file values.

## Precedence (Three Layers)

```text
Dataclass defaults  →  JSON config file  →  Environment variable
     (lowest)            (middle)              (highest)
```

- **Missing `core.json`** is silently treated as empty (identical to
  running without a config file).
- **Invalid JSON** is a hard error with the file path in the message.
- **Env vars always win** when set, even if the JSON file has a value.

## Config Directory Layout

```text
config/
  core.json         # All runtime settings (routing, budget, privacy, etc.)
  models/           # Per-model JSON configs (provider, limits, capabilities)
plugins/            # Plugin code + optional per-plugin JSON configs
```

Run `oc init-config` to generate `core.json` and example model configs.

## core.json

All non-model, non-plugin runtime configuration in one file. Sections
map directly to internal factory functions.

```json
{
  "provider": "stub",
  "default_mode": "fast",
  "model_fast": "gpt-4o-mini",
  "model_quality": "gpt-4o",
  "context_max_tokens": 8192,
  "pools": {
    "fast": "",
    "quality": "",
    "nsfw": ""
  },
  "weights": {
    "ollama": 100,
    "openai": 20
  },
  "fallback": {
    "max_fallbacks": 1,
    "on_transient": true,
    "on_constraint": true,
    "on_refusal": false
  },
  "budget": {
    "max_total_tokens": 0,
    "max_llm_calls": 0
  },
  "retry": {
    "max_retries": 2,
    "max_retry_sleep_ms": 2000,
    "rate_limit_max_wait_ms": 5000
  },
  "privacy": {
    "mode": "off",
    "external_only": true,
    "categories": ["email", "phone", "ip", "ssn", "cc", "api_key"],
    "redact_style": "mask",
    "log_events": true
  },
  "telemetry": {
    "enabled": true
  },
  "conversation": {
    "temperature": 0.2,
    "max_output_tokens": 512,
    "top_k_memory": 8,
    "last_n": 10,
    "include_pinned_memory": true
  },
  "discord": {
    "guild_ids": [],
    "channel_allowlist": [],
    "session_store_path": "data/discord_sessions.json",
    "conversation_title": "Discord chat",
    "history_limit": 5
  },
  "router": {
    "rules": {
      "enabled": true,
      "log_reasons": false,
      "nsfw_route_gte": 0.70,
      "nsfw_uncertain_gte": 0.45,
      "persona_uncertain_to_nsfw": true
    },
    "assist": {
      "enabled": false,
      "backend": "linear",
      "model_path": "",
      "timeout_ms": 50
    }
  }
}
```

### Field Reference

**Top-level fields** — provider selection and model routing defaults.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `provider` | `OC_LLM_PROVIDER` | `stub` |
| `default_mode` | `OC_LLM_DEFAULT_MODE` | `fast` |
| `model_fast` | `OC_LLM_MODEL_FAST` | `gpt-4o-mini` |
| `model_quality` | `OC_LLM_MODEL_QUALITY` | `gpt-4o` |

**`pools`** — multi-provider pool routing. Comma-separated `provider:model` pairs.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `pools.fast` | `OC_LLM_FAST_POOL` | `""` |
| `pools.quality` | `OC_LLM_QUALITY_POOL` | `""` |
| `pools.nsfw` | `OC_LLM_POOL_NSFW` | `""` |
| `weights` | `OC_LLM_PROVIDER_WEIGHTS` | `ollama:100,openai:20` |

**Note:** `weights` can be a JSON object (`{"ollama": 100}`) in the file
or a CSV string (`ollama:100,openai:20`) in the env var.

**`fallback`** — fallback behavior when an LLM call fails.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `fallback.max_fallbacks` | `OC_LLM_MAX_FALLBACKS` | `1` |
| `fallback.on_transient` | `OC_LLM_FALLBACK_ON_TRANSIENT` | `true` |
| `fallback.on_constraint` | `OC_LLM_FALLBACK_ON_CONSTRAINT` | `true` |
| `fallback.on_refusal` | `OC_LLM_FALLBACK_ON_REFUSAL` | `false` |

**`budget`** — token and call budget limits. `0` means no constraint.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `budget.max_total_tokens` | `OC_BUDGET_MAX_TOKENS` | `0` (unlimited) |
| `budget.max_llm_calls` | `OC_BUDGET_MAX_CALLS` | `0` (unlimited) |

**`retry`** — retry and rate-limit wait behavior.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `retry.max_retries` | `OC_LLM_MAX_RETRIES` | `2` |
| `retry.max_retry_sleep_ms` | `OC_LLM_MAX_RETRY_SLEEP_MS` | `2000` |
| `retry.rate_limit_max_wait_ms` | `OC_LLM_MAX_WAIT_MS` | `5000` |

**`privacy`** — outbound PII detection and redaction.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `privacy.mode` | `OC_PRIVACY_OUTBOUND_MODE` | `off` |
| `privacy.external_only` | `OC_PRIVACY_OUTBOUND_EXTERNAL_ONLY` | `true` |
| `privacy.categories` | `OC_PRIVACY_OUTBOUND_CATEGORIES` | all 6 |
| `privacy.redact_style` | `OC_PRIVACY_OUTBOUND_REDACT_STYLE` | `mask` |
| `privacy.log_events` | `OC_PRIVACY_OUTBOUND_LOG` | `true` |

**`telemetry`** — telemetry data collection.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `telemetry.enabled` | `OC_TELEMETRY_ENABLED` | `true` |

**`conversation`** — default parameters for conversation turns (temperature,
context window, memory retrieval). These are the fallback values used by
CLI, Discord, and RPC when no per-call override is provided.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `conversation.temperature` | `OC_CONVO_TEMPERATURE` | `0.2` |
| `conversation.max_output_tokens` | `OC_CONVO_MAX_OUTPUT_TOKENS` | `512` |
| `conversation.top_k_memory` | `OC_CONVO_TOP_K_MEMORY` | `8` |
| `conversation.last_n` | `OC_CONVO_LAST_N` | `10` |
| `conversation.include_pinned_memory` | `OC_CONVO_INCLUDE_PINNED_MEMORY` | `true` |

**`discord`** — Discord bot operational settings. The bot token can be
provided via `DISCORD_BOT_TOKEN` env var or as `token` in this section
(env var takes precedence).

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `discord.token` | `DISCORD_BOT_TOKEN` | (required) |
| `discord.guild_ids` | `OC_DISCORD_GUILD_IDS` (CSV) | `[]` |
| `discord.channel_allowlist` | `OC_DISCORD_CHANNEL_ALLOWLIST` (CSV) | `[]` |
| `discord.session_store_path` | `OC_DISCORD_SESSION_STORE_PATH` | `data/discord_sessions.json` |
| `discord.conversation_title` | `OC_DISCORD_CONVERSATION_TITLE` | `Discord chat` |
| `discord.history_limit` | `OC_DISCORD_HISTORY_LIMIT` | `5` |

**`router.rules`** — interaction router thresholds.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `router.rules.enabled` | `OC_ROUTER_ENABLED` | `true` |
| `router.rules.log_reasons` | `OC_ROUTER_LOG_REASONS` | `false` |
| `router.rules.nsfw_route_gte` | `OC_ROUTER_NSFW_ROUTE_GTE` | `0.70` |
| `router.rules.nsfw_uncertain_gte` | `OC_ROUTER_NSFW_UNCERTAIN_GTE` | `0.45` |
| `router.rules.persona_uncertain_to_nsfw` | `OC_ROUTER_PERSONA_UNCERTAIN_TO_NSFW` | `true` |

**`router.assist`** — optional ML-assisted routing.

| Field | Env Override | Default |
| ----- | ----------- | ------- |
| `router.assist.enabled` | `OC_ROUTER_ASSIST_ENABLED` | `false` |
| `router.assist.backend` | `OC_ROUTER_ASSIST_BACKEND` | `linear` |
| `router.assist.model_path` | `OC_ROUTER_ASSIST_MODEL_PATH` | `""` |
| `router.assist.timeout_ms` | `OC_ROUTER_ASSIST_TIMEOUT_MS` | `50` |

## Model Configs (`config/models/`)

Each model gets its own JSON file with provider details, operational
limits, capabilities, and cost tracking. These are self-contained — all
the information needed to use a model lives in its config file.

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "display_name": "OpenAI GPT-4o",
  "description": "GPT-4o - OpenAI's flagship multimodal model",
  "api_config": {
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "default_base_url": "https://api.openai.com/v1",
    "timeout": 60,
    "auth_header": "Authorization",
    "auth_format": "Bearer {api_key}",
    "api_key": "changeme-openai-key"
  },
  "limits": {
    "max_tokens": 16384,
    "context_window": 128000,
    "rate_limit_rpm": null,
    "rate_limit_tpm": null
  },
  "capabilities": {
    "text_generation": true,
    "streaming": true,
    "function_calling": true,
    "vision": true
  },
  "cost_tracking": {
    "input_cost_per_1k": 2.5,
    "output_cost_per_1k": 10.0,
    "currency": "USD"
  },
  "performance": {
    "priority": "balanced",
    "recommended_for": [
      "general_purpose",
      "vision_tasks",
      "reasoning"
    ]
  }
}
```

### Model Config Sections

| Section | Purpose |
| ------- | ------- |
| `api_config` | Endpoint, auth, timeout — everything needed to connect |
| `limits` | Token limits and rate limits (provider-imposed constraints) |
| `capabilities` | What the model supports (streaming, vision, tools, etc.) |
| `cost_tracking` | Per-1K token costs for budget calculations |
| `performance` | Priority tier and recommended use cases for routing |

**Note:** `limits.rate_limit_rpm` and `limits.rate_limit_tpm` are stubs
for future per-model rate limiting. Set to `null` until wired into the
execution layer.

## Plugin Configuration

Each plugin can include a `config.json` inside its package directory.
The config is injected into the plugin's `register()` context as
`context["config"]`.

```text
plugins/
  hello/
    __init__.py       # package init
    plugin.py         # register() entry point
    config.json       # plugin configuration (optional)
```

```json
{
  "greeting": "Hello from config!"
}
```

Plugins opt in by reading from context:

```python
def register(registry, handler_registry, context):
    config = (context or {}).get("config", {})
    greeting = config.get("greeting", "Hello!")
    # ...
```

## CLI Commands

```bash
# Generate core.json and example model configs
oc init-config

# Show effective configuration with value sources
oc config show

# JSON output
oc config show --json
```

`oc config show` displays `[default]`, `[file]`, or `[env]` next to the
provider field to indicate where each value came from.

## See Also

- [Environment Variables Reference](env_vars.md) — full list of env vars
- [Architecture](../architecture/ARCHITECTURE.md) — system architecture
