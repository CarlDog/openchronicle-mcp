# CLI Command Reference

All commands are invoked via the `oc` entry point. Commands are grouped by
category. Most post-container commands require a running database; pre-container
commands (marked below) work without one.

---

## System / Setup

### `oc version`

**Pre-container.** Print version information.

```text
oc version [--json]
```

| Flag | Description |
|------|-------------|
| `--json` | Emit JSON envelope with `package_version`, `python_version`, `protocol_version` |

### `oc init`

**Pre-container.** Initialize runtime directories (database parent, config,
plugins, output) and optional template files.

```text
oc init [--json] [--force] [--no-templates]
```

### `oc init-config`

**Pre-container.** Generate example model configuration files.

```text
oc init-config [--config-dir DIR]
```

### `oc provider`

**Pre-container.** Provider setup and management.

```text
oc provider list              # List known providers and models
oc provider setup [OPTIONS]   # Set up model configs (interactive or scripted)
oc provider custom [OPTIONS]  # Create a custom provider config
```

### `oc config show`

**Pre-container.** Show effective runtime configuration: resolved paths,
provider, pools, budget, privacy, telemetry, and router assist settings. API
keys in `OC_*` env vars are automatically masked.

```text
oc config show [--json]
```

### `oc list-models`

List loaded model configurations from the config directory.

```text
oc list-models [--config-dir DIR]
```

### `oc list-handlers`

List registered task handlers (built-in and plugin).

```text
oc list-handlers
```

### `oc diagnose`

Run diagnostics: check runtime paths, persistence, provider config.

```text
oc diagnose [--json]
```

---

## Database Maintenance

### `oc db info`

Show database file size, WAL size, row counts per table, pragma values, and
integrity check result.

```text
oc db info [--json]
```

### `oc db vacuum`

Compact the database with `VACUUM` and truncate the WAL. Prints before/after
file sizes.

```text
oc db vacuum
```

### `oc db backup`

Hot-backup the database to a file using SQLite's online backup API.

```text
oc db backup <path> [--force]
```

| Flag | Description |
|------|-------------|
| `--force` | Overwrite if destination file already exists |

### `oc db stats`

Show global token usage statistics: total calls, input/output/total tokens, and
breakdown by provider/model.

```text
oc db stats [--json]
```

---

## Project Management

### `oc init-project`

Create a new project.

```text
oc init-project <name>
```

### `oc list-projects`

List all projects.

```text
oc list-projects
```

### `oc show-project`

Show aggregated project details: name, agents, task status breakdown, token
usage, conversation count, and latest activity timestamp.

```text
oc show-project <project_id> [--json]
```

### `oc register-agent`

Register an agent in a project.

```text
oc register-agent <project_id> <name> [--role ROLE] [--provider PROVIDER] [--model MODEL]
```

### `oc resume-project`

Resume orphaned tasks (RUNNING -> PENDING) in a project.

```text
oc resume-project <project_id> [--continue]
```

### `oc replay-project`

Derive project state from the event log.

```text
oc replay-project --project-id ID [--show-llm]
```

---

## Event Log

### `oc events`

View the raw event log for a project. Events are shown in chronological order
(most recent last). Supports filtering by task ID, event type, and limiting
output to the N most recent events.

```text
oc events <project_id> [--task-id ID] [--type TYPE] [--limit N] [--json]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--task-id` | | Filter events by task ID |
| `--type` | | Filter by event type (e.g. `llm.requested`, `task.completed`) |
| `--limit` | 50 | Show only the N most recent matching events |
| `--json` | | Emit JSON envelope with full event payloads |

---

## Task Management

### `oc run-task`

Submit and execute a task.

```text
oc run-task <project_id> <task_type> <payload> [--agent-id ID]
```

### `oc show-task`

Show a task's timeline.

```text
oc show-task <task_id> [--result]
```

### `oc list-tasks`

List tasks in a project.

```text
oc list-tasks <project_id>
```

### `oc verify-task`

Verify a task's event hash chain.

```text
oc verify-task <task_id>
```

### `oc verify-project`

Verify all task chains in a project.

```text
oc verify-project <project_id>
```

### `oc replay-task`

Replay task execution.

```text
oc replay-task <task_id> [--mode {verify|replay-events|dry-run}]
```

### `oc explain-task`

Show detailed execution trace for a task.

```text
oc explain-task <task_id>
```

### `oc task-tree`

Show task tree with routing and usage.

```text
oc task-tree <task_id> [--depth N] [--show-reasons]
```

### `oc usage`

Show LLM usage statistics for a project.

```text
oc usage <project_id> [--limit N]
```

---

## Conversations

### `oc convo new`

Create a new conversation.

```text
oc convo new [--title TITLE]
```

### `oc convo list`

List conversations.

```text
oc convo list [--limit N]
```

### `oc convo show`

Show conversation transcript.

```text
oc convo show [<conversation_id>] [--latest] [--limit N] [--explain] [--json]
```

### `oc convo ask`

Send a prompt in a conversation.

```text
oc convo ask [<conversation_id>] [<prompt>] [--latest] [--last-n N] [--top-k-memory N]
             [--explain] [--allow-pii] [--enqueue-if-unavailable]
             [--include-pinned-memory | --no-include-pinned-memory] [--json]
```

### `oc convo export`

Export conversation as JSON.

```text
oc convo export [<conversation_id>] [--latest] [--explain] [--verify]
                [--fail-on-verify] [--json]
```

### `oc convo verify`

Verify conversation event hash chain.

```text
oc convo verify <conversation_id> [--json]
```

### `oc convo mode`

Get or set conversation mode.

```text
oc convo mode <conversation_id> [--set {general|creative|...}] [--json]
```

### `oc convo remember`

Save a turn as a memory item.

```text
oc convo remember <conversation_id> <turn_index> --which {user|assistant}
                  [--tags TAGS] [--pin] [--source SOURCE]
```

### `oc convo delete`

Delete a conversation and all related data (turns, memory items, events).
Requires `--force` because the operation is destructive and removes hash-chained
events.

```text
oc convo delete <conversation_id> --force [--json]
```

---

## Memory

### `oc memory add`

Add a memory item.

```text
oc memory add <content> [--tags TAGS] [--pin] [--source SOURCE]
              [--conversation-id ID] [--project-id ID]
```

### `oc memory list`

List memory items.

```text
oc memory list [--limit N] [--pinned-only]
```

### `oc memory show`

Show a memory item's full details.

```text
oc memory show <memory_id>
```

### `oc memory pin`

Toggle memory pin state.

```text
oc memory pin <memory_id> {--on | --off}
```

### `oc memory search`

Search memory items by keyword.

```text
oc memory search <query> [--top-k N] [--conversation-id ID] [--project-id ID]
                 [--include-pinned | --no-include-pinned]
```

### `oc memory delete`

Delete a memory item and clean up turn references
(`memory_written_ids`).

```text
oc memory delete <memory_id> [--json]
```

---

## Chat

### `oc chat`

Interactive chat session with streaming responses.

```text
oc chat [--conversation-id ID] [--resume] [--title TITLE] [--no-stream]
```

| Flag | Description |
|------|-------------|
| `--resume` | Resume the most recent conversation |
| `--no-stream` | Disable streaming (wait for complete response) |

---

## Server / RPC

### `oc serve`

Run the STDIO JSON RPC server.

```text
oc serve [--idle-timeout-seconds N]
```

### `oc rpc`

Run a single JSON RPC request (reads from stdin or `--request`).

```text
oc rpc [--request JSON]
```

---

## Testing / Debug

### `oc selftest`

Run deterministic CLI-only selftest.

```text
oc selftest [--dir DIR] [--json] [--keep-artifacts] [--no-plugins]
            [--telemetry-self-report]
```

### `oc smoke-live`

Smoke test with a real LLM provider.

```text
oc smoke-live [--provider NAME] [--model NAME] [--prompt TEXT] [--json]
```

### `oc acceptance`

Run deterministic acceptance workflow.

```text
oc acceptance [--json]
```

### `oc demo-summary`

Run supervisor+worker summary demo.

```text
oc demo-summary <project_id> <text> [--use-openai] [--mode {fast|quality}]
                [--mix {fast_then_quality|quality_then_fast}]
```

---

## JSON Output

Most commands support a `--json` flag that emits a standard envelope:

```json
{
  "ok": true,
  "command": "version",
  "result": { ... },
  "error": null
}
```

On error:

```json
{
  "ok": false,
  "command": "version",
  "result": null,
  "error": {
    "error_code": "...",
    "message": "...",
    "hint": "..."
  }
}
```
