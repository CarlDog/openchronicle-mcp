# Asset Management System

## Overview

The asset system provides filesystem storage, content-addressable dedup,
and generic entity linking for binary media (images, audio, video,
documents). It replaces the unused `Resource` model with a proper
infrastructure layer that future media features (image generation,
multimodal conversations) build on.

## Data Flow

```text
User provides a file
        |
        v
  +-----------+     SHA-256 hash     +----------------+
  | CLI / MCP |  ----------------->  | upload_asset    |
  | interface |                      | (use case)      |
  +-----------+                      +----------------+
                                           |
                             +---------+---+---+---------+
                             |         |       |         |
                             v         v       v         v
                         dedup?    store     persist   emit
                         (hash     file      to DB     event
                         lookup)   to disk
```

## Scenarios

### 1. Upload a reference image for a conversation

**Via CLI:**

```bash
oc asset upload proj-123 ./reference-art.png \
    --link-to-type conversation \
    --link-to-id conv-456 \
    --link-role input
```

**Via MCP (what Goose/Serena/Claude would call):**

```python
asset_upload(
    project_id="proj-123",
    source_path="./reference-art.png",
    link_target_type="conversation",
    link_target_id="conv-456",
    link_role="input",
)
```

**What happens internally:**

1. **`asset_upload` MCP tool** (or CLI `cmd_asset`) receives the call and
   gets the `CoreContainer` from context.

2. **`upload_asset.execute()`** is called with the container's `storage`
   (SqliteStore), `asset_file_storage` (AssetFileStorage), and
   `event_logger.append` as the event emitter.

3. **Hash computation** -- `AssetFileStorage.compute_hash_from_path()`
   reads the file in 8KB chunks and produces a SHA-256 hex digest. This
   never loads the full file into memory.

4. **Dedup check** -- `store.get_asset_by_hash(project_id, content_hash)`
   queries against the `ux_assets_project_hash` unique index. If the same
   bytes were already uploaded to this project, it skips to step 7.

5. **Filesystem storage** -- `AssetFileStorage.store_file()` copies the
   file to `data/assets/proj-123/{asset-uuid}.png`. The project
   subdirectory is created if needed.

6. **DB persistence** -- `store.add_asset(asset)` inserts a row into the
   `assets` table with the id, project\_id, filename, mime\_type,
   file\_path, size\_bytes, content\_hash, metadata (JSON), and
   created\_at. An `asset.created` event is emitted.

7. **Linking** -- An `AssetLink` is created: `asset_id` ->
   `target_type="conversation"`, `target_id="conv-456"`, `role="input"`.
   Inserted into the `asset_links` table. An `asset.linked` event is
   emitted (with `dedup: true` in payload if step 4 found an existing
   asset).

8. **Return** -- The tool returns `(asset, is_new)`. The MCP tool
   serializes it as a dict with `is_new: true/false` so the caller knows
   whether this was a fresh upload or a dedup hit.

### 2. Same file uploaded again (dedup)

```bash
oc asset upload proj-123 ./reference-art.png \
    --link-to-type turn \
    --link-to-id turn-789 \
    --link-role reference
```

Steps 1-3 are identical. At step 4, `get_asset_by_hash` returns the
existing asset. The file is **not** copied again. A **new link** is created
pointing the same asset to `turn-789`. The caller gets back
`is_new: false`.

One file on disk. Two links. Two different entities can reference it.

### 3. Browse and inspect

```bash
# List all assets in a project
oc asset list proj-123 --json

# Show a specific asset's metadata + all its links
oc asset show asset-uuid-here --json
```

The `asset_get` MCP tool returns the asset metadata plus all `AssetLink`
rows, so any client can see every entity the asset is attached to and what
role it plays.

### 4. Link an existing asset to a new entity

```bash
oc asset link asset-uuid-here memory_item mem-321 --role reference
```

This calls `link_asset.execute()`, which validates the asset exists,
creates the link, and emits `asset.linked`. No file operations.

## Filesystem Layout

```text
data/assets/
  proj-123/
    a1b2c3d4-...-e5f6.png      # reference-art.png (one copy)
    f7g8h9i0-...-j1k2.jpg      # another asset
  proj-456/
    m3n4o5p6-...-q7r8.wav      # audio file in different project
```

Configurable via the `OC_ASSETS_DIR` environment variable (default:
`data/assets`).

## Database Tables

```text
assets                          asset_links
+------------------+            +------------------+
| id (PK)          |<----+      | id (PK)          |
| project_id (FK)  |     +------| asset_id (FK)    |
| filename         |            | target_type      |  "conversation", "turn",
| mime_type         |            | target_id        |  "memory_item", "event", etc.
| file_path         |            | role             |  "input", "output", "reference"
| size_bytes        |            | created_at       |
| content_hash      |            +------------------+
| metadata (JSON)   |
| created_at        |
+------------------+
```

### Indexes

| Index | Table | Columns | Purpose |
|-------|-------|---------|---------|
| `ux_assets_project_hash` | assets | project\_id, content\_hash | Dedup enforcement (unique per project) |
| `idx_assets_project_created` | assets | project\_id, created\_at, id | List by project |
| `idx_asset_links_asset` | asset\_links | asset\_id, created\_at, id | "What's linked to this asset?" |
| `idx_asset_links_target` | asset\_links | target\_type, target\_id, created\_at, id | "What assets are on this conversation/turn?" |

## Event Trail

Every operation leaves an auditable event:

| Action | Event type | Key payload |
|--------|-----------|-------------|
| New upload | `asset.created` | asset\_id, filename, mime\_type, size\_bytes, content\_hash |
| Link created | `asset.linked` | asset\_id, link\_id, target\_type, target\_id, role |
| Dedup + link | `asset.linked` | same as above + `dedup: true` |

## Key Files

| File | Layer | Purpose |
|------|-------|---------|
| `core/domain/models/asset.py` | Domain | `Asset` and `AssetLink` dataclasses |
| `core/domain/ports/asset_store_port.py` | Domain | `AssetStorePort` ABC (8 methods) |
| `core/application/services/asset_storage.py` | Application | `AssetFileStorage` -- filesystem ops, hashing |
| `core/application/use_cases/upload_asset.py` | Application | Upload with hash, dedup, store, persist, link, events |
| `core/application/use_cases/link_asset.py` | Application | Link an existing asset to any entity |
| `core/infrastructure/persistence/sqlite_store.py` | Infrastructure | `AssetStorePort` implementation (CRUD) |
| `interfaces/mcp/tools/asset.py` | Interface | 4 MCP tools: upload, list, get, link |
| `interfaces/cli/commands/asset.py` | Interface | 4 CLI commands: upload, list, show, link |

## Link Semantics

The `target_type` / `target_id` pair is polymorphic -- any entity in the
system can be a link target:

| target\_type | Example use |
|-------------|-------------|
| `project` | Project avatar or branding asset |
| `conversation` | Reference material for a conversation |
| `turn` | Image attached to a specific message |
| `memory_item` | Visual context for a memory |
| `event` | Artifact produced by a task event |
| `agent` | Agent avatar or profile image |

The `role` field captures directional semantics:

| Role | Meaning |
|------|---------|
| `input` | User-provided (inbound) |
| `output` | System-generated (outbound) |
| `reference` | Context/background material |
| `avatar` | Profile/identity image |
| `thumbnail` | Derived preview |

## Not Yet Wired (Deferred)

The conversation pipeline integration. Today you manually upload and link.
The follow-up would:

- Add `asset_ids: list[str]` to `ask_conversation.execute()`
- Build multimodal message content blocks for LLM adapters
- Auto-link assets to turns with `role="input"` / `role="output"`

The infrastructure is ready -- the linking mechanism and storage are in
place.
