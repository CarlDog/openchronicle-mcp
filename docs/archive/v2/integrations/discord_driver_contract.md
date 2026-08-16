# Discord driver contract (stdio RPC)

This contract defines how a Discord bot (or any chat front-end) talks to OpenChronicle core over STDIO RPC. It is doc-first and uses only existing commands.

## Goals and constraints

- Core runs as oc serve and speaks newline-delimited JSON over STDIO.
- Treat stdout as JSON-only. Send diagnostics to stderr on the client side.
- Use privacy.preview before convo.ask or convo.ask_async when user content may contain PII.
- Follow outbound privacy policy outcomes (warn/redact/block) and never auto-enable allow_pii.

## Recommended flows

### A) Sync mode (simple)

1. Health check

Request:

```json
{ "command": "system.health", "args": {} }
```

Response (ok):

```json
{
  "ok": true,
  "result": {
    "ok": true,
    "storage": { "type": "sqlite", "reachable": true },
    "config": { "config_dir": "...", "pools": ["default"] }
  }
}
```

1. Privacy preview

Request:

```json
{
  "command": "privacy.preview",
  "args": {
    "text": "contact me at a@b.com",
    "provider": "openai",
    "mode_override": "warn",
    "categories_override": ["email"]
  }
}
```

Response (warn):

```json
{
  "ok": true,
  "result": {
    "effective_policy": {
      "mode": "warn",
      "external_only": true,
      "applies": true
    },
    "report": {
      "categories": ["email"],
      "counts": { "email": 1 },
      "redactions_applied": false
    }
  }
}
```

1. Ask

Request:

```json
{
  "command": "convo.ask",
  "args": { "conversation_id": "...", "prompt": "hello" }
}
```

Response (ok):

```json
{
  "ok": true,
  "result": {
    "conversation_id": "...",
    "turn_id": "...",
    "assistant_text": "..."
  }
}
```

If the response error_code is OUTBOUND_PII_BLOCKED, prompt the user to redact or explicitly confirm allow_pii.

### B) Async mode (recommended for Discord)

1. Enqueue

Request:

```json
{
  "command": "convo.ask_async",
  "args": { "conversation_id": "...", "prompt": "hello" }
}
```

Response:

```json
{
  "ok": true,
  "result": { "task_id": "...", "status": "queued", "conversation_id": "..." }
}
```

1. Drain

Request:

```json
{ "command": "task.run_many", "args": { "limit": 10, "max_seconds": 1.5 } }
```

Response:

```json
{
  "ok": true,
  "result": {
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
}
```

1. Poll (optional)

Request:

```json
{ "command": "task.get", "args": { "task_id": "..." } }
```

Response:

```json
{
  "ok": true,
  "result": {
    "task": { "task_id": "...", "status": "completed", "type": "convo.ask" }
  }
}
```

If a task fails with OUTBOUND_PII_BLOCKED or NSFW_POOL_NOT_CONFIGURED, inform the user and do not retry automatically.

## Determinism and idempotency

- Provide request_id for all requests. In serve mode, duplicate request_id is deduped.
- task.run_many executes deterministically in created_at ASC, task_id ASC order.
- Use has_more and remaining_queued to drain in batches without guessing.

## Safety and UX recommendations

- If privacy.preview shows categories and policy would block, prompt user to redact or confirm allow_pii explicitly.
- Never auto-enable allow_pii.
- Do not log user content. Log request_id, task_id, and conversation_id only.

## Minimal config checklist

- OC_CONFIG_DIR
- OC_DB_PATH
- OC_PLUGIN_DIR
- OC_OUTPUT_DIR
- Provider configuration (e.g., OC_LLM_PROVIDER and pool env vars)

Readiness check:

- Call system.health and ensure ok true before accepting traffic.

## Notes

- No Discord code is included here.
