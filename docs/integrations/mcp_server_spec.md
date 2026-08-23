# MCP server tool surface (v3)

OpenChronicle's MCP server exposes 18 tools. They map 1:1 with the
HTTP REST surface (same use cases under both transports). All tools
return JSON-safe Python dicts; the FastMCP runtime handles
serialization to MCP's wire format.

For client setup see `docs/integrations/mcp_client_setup.md`. For
stability guarantees see `docs/api/STABILITY.md`.

## Memory

| Tool | Purpose |
|---|---|
| `memory_save` | Persist a memory item that should outlive the current session. `project_id` required. |
| `memory_search` | Hybrid FTS5 + semantic search via RRF, scoped optionally by `project_id` and `tags`. `compact` returns a content preview. `mode` (`hybrid`/`keyword`/`semantic`) picks the retrieval channel per call; `phrase` makes the keyword channel match the query as one adjacent-token phrase. Every result carries a `relevance` object (see below). |
| `memory_list` | Browse memory items newest-first (pinned float to the top). `project_id` filters strictly; `compact` returns a content preview. |
| `memory_get` | Fetch one memory by ID. |
| `memory_update` | Edit content/tags in place; preserves identity. |
| `memory_delete` | Preview (`confirm=false`) or hard-delete (`confirm=true`). `confirm` is **required** — omitting it is an error, not a preview. Two-step safety; the preview returns content/tags/project_id/pinned plus `deleted: false` and a `next_step`, without touching the DB. |
| `memory_pin` | Toggle pin state. |
| `memory_stats` | Counts + per-tag/per-source breakdown. |
| `memory_embed` | Generate missing (or all, with `force=true`) embeddings. |

The `memory_save` tool's input schema is the canonical "what does an
LLM need to write a memory" shape:

```json
{
  "content": "string, 1-100000 chars",
  "project_id": "string, required",
  "tags": ["decision", "rejected", "milestone", "context", "convention", "scope"],
  "pinned": false,
  "created_at": "ISO datetime, optional (for backdated imports)"
}
```

## Project

| Tool | Purpose |
|---|---|
| `project_create` | Create a new project namespace. |
| `project_get` | Fetch one project by ID. |
| `project_list` | List projects, newest first. `name_contains` is a literal case-insensitive substring filter; `compact` returns metadata keys + size instead of the blob. |
| `project_update` | Rename or update metadata. At least one of `name` / `metadata` must be set; omitted fields are left untouched (pass `metadata: {}` to clear). |
| `project_delete` | Preview (`confirm=false`) or hard-delete (`confirm=true`) a project and all its memories. `confirm` is **required**. The preview returns `name` + `memory_count` plus `deleted: false` and a `next_step`. No soft-delete; backups are the recovery path. |
| `project_delete_bulk` | Same two-step for many projects at once. Unknown ids come back in `missing` rather than aborting the batch; the delete itself runs in one transaction. Pair with `project_list(name_contains=...)` to build the id list. |

## Context

| Tool | Purpose |
|---|---|
| `context_recent` | Catch-up on prior context for a project. Returns recent memory items, optionally filtered by a `query` keyword. Use at session start (especially post-compression). `compact` returns a content preview. |

## Onboarding

| Tool | Purpose |
|---|---|
| `onboard_git` | Clone a remote git repo shallow into a server-side tmpdir, cluster commits, and return per-cluster summaries the caller synthesizes into memories. Params: `max_commits` (walk cap, default 500), `max_clusters` (default 15), `force` (wipe prior git-onboard memories + watermark and start over), `max_commits_per_cluster` (default 10, bounds each cluster's listing), `include_commit_detail` (adds bodies/file lists/diffstats; ~10x response growth), `branch` (ref to walk; default is the remote's DEFAULT branch — wrong for mirror-style repos, so check the echo). Every response carries the resolved `branch` + tip `head` SHA. Incremental runs resume past a stored watermark; if that watermark has become unreachable (history rewrite / force-push), the run auto-falls-back to a full walk, keeps existing memories, and flags `watermark_unreachable` + `ran_full_walk` — skip repeated cluster suggestions instead of re-saving. |

## System

| Tool | Purpose |
|---|---|
| `health` | Probe server state: DB reachability, config, embedding subsystem status, `maintenance_degraded`, `package_version`, `schema_version`, and `fts5_active`. Identical key set to `GET /api/v1/health`. |

## Tool design philosophy

Each tool's docstring answers "when would I call this vs the others?"
not "what does this do?" — the LLM's tool selection improves
dramatically when descriptions discriminate the choice. Concretely:

- `memory_search` vs `memory_list`: search when you have keywords;
  list when you want to enumerate a project or page through everything.
- `memory_search` vs `context_recent`: search for specific keywords;
  context_recent for "what was I working on last?"
- `memory_save` vs `memory_update`: save creates a new ID + timestamp;
  update preserves identity. Edits revise in place.
- `memory_delete` vs `memory_update`: delete is permanent; update
  revises. Don't use delete-then-save when revising — that loses the
  original `created_at`.
- `memory_pin`: changes pin state only; doesn't touch content/tags
  (use `memory_update` for those).
- `memory_delete` and `project_delete` are **two-step**: calling with
  `confirm=false` returns a preview so the LLM can see the blast radius
  and decide whether to re-call with `confirm=true`. Don't treat the
  preview response as a delete confirmation — it's diagnostic data, and
  it says so via `deleted: false` and `next_step`.
- `confirm` on both delete tools has **no default**. Omitting it raises
  rather than previewing. A preview is success-shaped, so defaulting to
  one means a caller that never asked for it sees what looks like a
  completed delete; that is a real bug this server shipped once, in a
  downstream client whose wrapper ignored the response body.

## Project scoping

Two rules are in play, and they answer different questions. They are not
meant to agree.

- **Strict** (`project_id = ?`) — enumeration and accounting. "What is in
  project X?", "how many?", "delete them all." A row from outside X,
  including a global one with no project, is a wrong answer.
  `memory_list`, `memory_stats`, and the `project_delete` cascade.
- **With global** (`project_id = ? OR project_id IS NULL`) — relevance
  retrieval. "What should I know while working in X?" A standing rule
  that belongs to no single project still applies inside one, so pinned
  global items surface. `memory_search`, and `context_recent` when a
  `query` is given. With no `query`, `context_recent` is a recency
  listing and follows the strict rule (routing an empty query through
  search would return nothing on the FTS5 path — fixed 2026-08-16).

The visible consequence: `memory_list(project_id=X, pinned_only=true)`
returns a different set than the pinned items `memory_search` surfaces
for X. That is intended. If you need "every standing rule that applies
here", search; if you need "everything filed under here", list.

## Projection

`memory_list`, `memory_search`, `context_recent`, and `project_list` all
take `compact: bool = false`. Set it when browsing rather than reading.

Compact **replaces** the expensive field rather than shortening it:
`content` becomes `content_preview` (120 chars) + `content_length`, and
`metadata` becomes `metadata_keys` + `metadata_size`. The rename is the
point — a caller reading `content` never silently receives a truncated
string, and the length tells you whether a `memory_get` is worth it.

`memory_get` has no `compact`; returning the whole item is its purpose.

## Relevance (search-surface v2, Q20/Q21)

Every `memory_search` result (and `context_recent` result when a
`query` is given) carries a `relevance` object explaining *why* it
surfaced. Fields are omitted when not applicable:

- `channel` (always present) — what produced the hit: `pinned` (a
  standing rule that matched and was floated to the top, no scores),
  `keyword`, `semantic`, or `hybrid` (both channels agreed).
- `semantic_similarity` — unit-cosine similarity (0–1); the only
  roughly interpretable score.
- `rrf_score` — the Reciprocal Rank Fusion value used for ordering.
  It is a rank-fusion artifact (~2/(k+1) ceiling), **not** calibrated
  confidence — do not threshold on it. This is why no `min_confidence`
  parameter ships.
- `keyword_rank` — 1-based position in the keyword ranking.

`mode` selects the retrieval channel per call: `hybrid` (default;
degrades to keyword-only on provider failure, per the documented
degradation policy), `keyword` (never touches the embedding provider),
or `semantic` (requires a provider; a missing provider is a validation
error and a provider failure is a `PROVIDER_ERROR` — never a silent
keyword fallback). `phrase=true` makes the keyword channel match the
whole query as one adjacent-token phrase.

The pinned **float** is query-aware and bounded. A pinned item leads the
results only when it *matches* the query, and at most `pinned_limit` of
them do (default 10, best-matching first, recency breaking ties).

Two independent questions, deliberately kept separate — conflating them
produced both of the bugs this replaced:

| | float (policy) | rank (visibility) |
|---|---|---|
| `pinned_limit=10` (default) | up to 10 matching pins lead | the rest rank normally |
| `pinned_limit=0` | none lead | **all pins still rank** |
| `include_pinned=false` | none lead | pins hidden entirely |

History, so it isn't reintroduced: until 2026-08-17 the float was a
blanket prepend of *every* pin regardless of the query (a `top_k=2`
search answered with 85 pins). Capping that prepend then made pins past
the cap unreachable by **any** query, because the ranking excluded all
pinned rows. The float is now a real query and the exclusion covers only
the pins actually floated. Enumerate every standing rule — matching or
not — with `memory_list(pinned_only=true)`.

## Cut from v2

These v2 MCP tools were dropped along with their subsystems:

- `conversation_create` / `conversation_list` / `conversation_history`
  / `conversation_ask` / `conversation_set_mode` /
  `conversation_get_mode` — conversation engine archived.
- `turn_record` / `context_assemble` — depended on conversation/turn
  storage.
- `search_turns` — turns table is gone.
- `tool_stats` / `moe_stats` — telemetry archived (V3_PLAN Q8).
- `asset_*` / `webhook_*` / `media_generate` — subsystems archived.

If a future project needs any of these, copy from
`archive/openchronicle.v2`.

## See also

- `docs/integrations/mcp_client_setup.md` — wiring up Claude Code,
  Goose, etc.
- `docs/cli/commands.md` — CLI commands that mirror these tools
- `docs/api/STABILITY.md` — what's stable across versions
