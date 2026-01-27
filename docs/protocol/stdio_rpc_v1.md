# OpenChronicle STDIO RPC Protocol v1

## Version

```json
{ "protocol_version": "1" }
```

protocol_version: "1"

## Overview

The STDIO RPC protocol defines newline-delimited JSON requests sent to `oc serve` and `oc rpc` and JSON responses
written to stdout. Stdout must contain JSON only. Diagnostics must be sent to stderr.

Integrations: [../integrations/discord_driver_contract.md](../integrations/discord_driver_contract.md)

## Request schema

Requests are single JSON objects on one line.

```json
{"protocol_version":"1","command":"...","args":{...},"request_id":"..."}
```

- `protocol_version` (optional, recommended): must be "1" for this protocol version. If provided and not "1",
  the server responds with `UNSUPPORTED_PROTOCOL_VERSION`.
- `command` (required): string command name.
- `args` (optional): object containing command arguments. Defaults to `{}` when omitted.
- `request_id` (optional): string identifier for client retries. If provided, it must be a string.

## Response envelope

Responses are single JSON objects on one line.

```json
{"protocol_version":"1","command":"...","ok":true,"result":{...},"error":null,"request_id":"..."}
```

- `protocol_version` (optional, recommended): "1".
- `command`: echoes the request command.
- `ok`: boolean success flag.
- `result`: object or `null`.
- `error`: object or `null`.
- `request_id`: echoes the request identifier when provided.

### Error object

```json
{ "error_code": "INVALID_JSON", "message": "...", "hint": null }
```

- `error_code`: string or `null`.
- `message`: string.
- `hint`: string or `null`.
- `details`: object or `null`.

## Error codes

- `INVALID_JSON`
- `INVALID_REQUEST`
- `INVALID_ARGUMENT`
- `INTERNAL_ERROR`
- `UNKNOWN_COMMAND`
- `TASK_NOT_FOUND`
- `NSFW_POOL_NOT_CONFIGURED`
- `OUTBOUND_PII_BLOCKED`
- `UNSUPPORTED_PROTOCOL_VERSION`

## Serve-mode behavior (best-effort)

When running `oc serve`, the server keeps a small in-memory FIFO cache keyed by `request_id`. If a
request arrives with a `request_id` that already exists in the cache, the cached response is returned
without re-executing the command. This cache is bounded and is not persisted across restarts.

`oc serve` also accepts an optional `--idle-timeout-seconds` flag. When set to a value greater than
zero, the server exits after that many seconds without receiving any input line.

## Supported commands

### system.info

Args: `{}`

Result:

```json
{
  "name": "openchronicle",
  "protocol_version": "1",
  "capabilities": { "serve": true, "rpc": true }
}
```

### system.metrics

Args: `{}`

Result:

```json
{
  "started_at": "...",
  "uptime_seconds": 1.23,
  "telemetry_enabled": true,
  "requests": {
    "total": 1,
    "ok": 1,
    "error": 0,
    "by_command": { "system.metrics": 1 },
    "by_error_code": {}
  },
  "tasks": { "run_one": 0, "run_many": 0, "completed": 0, "failed": 0 },
  "llm": {
    "calls_total": 0,
    "calls_by_provider": {},
    "calls_by_model": {},
    "tokens_prompt_total": 0,
    "tokens_completion_total": 0,
    "tokens_total": 0,
    "usage_unknown_calls": 0,
    "rate_limit_hits": 0,
    "quota_hits": 0
  },
  "perf": {
    "ask_total_ms_sum": 0.0,
    "ask_total_ms_count": 0,
    "provider_call_ms_sum": 0.0,
    "provider_call_ms_count": 0,
    "context_assemble_ms_sum": 0.0,
    "context_assemble_ms_count": 0
  },
  "context": {
    "max_tokens_known_calls": 0,
    "prompt_tokens_sum": 0,
    "max_context_tokens_sum": 0,
    "utilization_sum": 0.0
  },
  "memory": {
    "retrieved_total": 0,
    "pinned_total": 0,
    "retrieved_chars_total": 0,
    "duplicate_retrieval_total": 0,
    "unique_memory_ids_seen_total": 0,
    "retrieval_reason_counts": { "heuristic_v0": 0 },
    "self_report_enabled": false,
    "self_report_valid_total": 0,
    "self_report_invalid_total": 0,
    "used_ids_total": 0,
    "used_rate_avg": 0.0
  }
}
```

### system.commands

Args: `{}`

Result:

```json
{
  "commands": [
    "convo.ask",
    "convo.ask_async",
    "convo.export",
    "convo.mode",
    "convo.show",
    "convo.verify",
    "privacy.preview",
    "task.get",
    "task.list",
    "task.run_one",
    "task.run_many",
    "system.commands",
    "system.health",
    "system.info",
    "system.metrics",
    "system.ping",
    "system.shutdown"
  ]
}
```

### system.health

Args: `{}`

Result:

```json
{
  "ok": true,
  "storage": { "type": "sqlite", "reachable": true },
  "config": {
    "config_dir": "config",
    "pools": ["FAST", "QUALITY"],
    "nsfw_pool_configured": false
  }
}
```

### system.ping

Args: `{}`

Result:

```json
{ "pong": true }
```

### system.shutdown

Args: `{}`

Result:

```json
{ "shutdown": true, "reason": "requested" }
```

### convo.export

Args:

```json
{ "conversation_id": "...", "explain": false, "verify": false }
```

Result: the existing export payload.

### convo.verify

Args:

```json
{ "conversation_id": "..." }
```

Result:

```json
{
  "conversation_id": "...",
  "verification": {
    "ok": true,
    "failure_event_id": null,
    "expected_hash": null,
    "actual_hash": null
  }
}
```

### convo.ask

Args:

```json
{
  "conversation_id": "...",
  "prompt": "...",
  "last_n": 10,
  "top_k_memory": 8,
  "include_pinned_memory": true,
  "explain": false,
  "allow_pii": false
}
```

Result:

```json
{
  "conversation_id": "...",
  "turn_id": "...",
  "turn_index": 1,
  "assistant_text": "...",
  "explain": null
}
```

### convo.ask_async

Args:

```json
{
  "conversation_id": "...",
  "prompt": "...",
  "explain": false,
  "allow_pii": false,
  "metadata": {}
}
```

Result:

```json
{ "conversation_id": "...", "task_id": "...", "status": "queued" }
```

This enqueues work for a future worker; no LLM execution happens immediately. Setting `allow_pii` bypasses
the outbound privacy gate for this request and emits an audit event.

### task.get

Args:

```json
{ "task_id": "..." }
```

Result:

```json
{
  "task": {
    "task_id": "...",
    "type": "...",
    "status": "pending",
    "created_at": "...",
    "updated_at": "...",
    "parent_task_id": null
  }
}
```

### task.list

Args (all optional):

```json
{
  "status": "pending",
  "limit": 50,
  "offset": 0,
  "sort": "created_at",
  "order": "desc"
}
```

Result:

```json
{
  "tasks": [
    {
      "task_id": "...",
      "type": "...",
      "status": "pending",
      "created_at": "...",
      "updated_at": "..."
    }
  ],
  "total": 1
}
```

### task.run_one

Args:

```json
{ "type": "convo.ask" }
```

Result:

```json
{
  "ran": true,
  "task_id": "...",
  "status": "completed",
  "conversation_id": "...",
  "turn_id": "...",
  "error": null
}
```

This runs at most one queued task deterministically (created_at ASC, task_id ASC). No background loop is started.

### task.run_many

Args:

```json
{ "type": "convo.ask", "limit": 10, "max_seconds": 0 }
```

Result:

```json
{
  "ran": 2,
  "completed": 2,
  "failed": 0,
  "has_more": false,
  "remaining_queued": 0,
  "tasks": [
    {
      "task_id": "...",
      "status": "completed",
      "conversation_id": "...",
      "turn_id": "...",
      "error": null
    }
  ]
}
```

This runs up to the requested number of queued tasks deterministically (created_at ASC, task_id ASC). No background loop is started.

### privacy.preview

Args:

```json
{
  "text": "...",
  "provider": "openai",
  "mode_override": "warn",
  "external_only_override": true,
  "categories_override": ["email"],
  "redact_style_override": "mask"
}
```

Result:

```json
{
  "effective_policy": {
    "mode": "warn",
    "external_only": true,
    "applies": true
  },
  "report": {
    "categories": ["email"],
    "counts": { "email": 1 },
    "redactions_applied": false,
    "summary": "Detected: email(1)."
  }
}
```

This performs a preflight check only; no LLM call is made. Task payloads are never returned by this command.

### convo.show

Args:

```json
{ "conversation_id": "...", "limit": 10, "explain": false }
```

Result:

```json
{
  "conversation_id": "...",
  "mode": "general",
  "turns": [
    {
      "turn_id": "...",
      "turn_index": 1,
      "user_text": "...",
      "assistant_text": "...",
      "explain": null
    }
  ]
}
```

### convo.mode

Args (get):

```json
{ "conversation_id": "..." }
```

Args (set):

```json
{ "conversation_id": "...", "mode": "persona" }
```

Result:

```json
{ "conversation_id": "...", "mode": "persona" }
```
