# #memory (usememory.com) Review — Parity and Beyond

**Status:** Comparative review and the operator's aspiration. Nothing here is
scheduled or accepted: each proposal below needs the operator's ratification
before implementation, per the agent rules in `AGENTS.md`.

**Assessment date:** 2026-09-28 (America/Chicago)

**OpenChronicle baseline:** `main` at `99bd68cb` (v3.6.0).

**Operator aspiration (2026-09-28):** "I'd love it if we eventually did
everything they can do and better." This review turns that into a gap list with
roadmap IDs (ROADMAP Phase 9, `PAR-*`). It does not change the current order of
work, and accuracy then responsiveness remains the standing priority.

## Evidence and its limits

- **Sources.** Four public pages of usememory.com, read on 2026-09-28:
  `/developers` (the API reference), `/` (the product page), `/security` and
  `/connect`. They were read through a summarizing fetcher, so exact limits and
  field names below are as the fetcher reported them. No account was created
  and nothing was called.
- **Not stated anywhere read:** the operator's name or company, pricing,
  storage location or provider, encryption at rest, key custody,
  two-factor or passkey sign-in, backups, export, and a deletion timeline.
- **One inconsistency:** the product page shows a macOS app with iPhone "in
  development", while the security page says memories sync across iOS,
  Android, macOS and Windows. Treat platform coverage as unconfirmed.

## What #memory is

A hosted, cloud-only personal knowledge base with native apps. Its memories are
text (up to 10,000 characters) with optional attached photos, videos and
documents, each labeled with 1 to 10 user keywords. Retrieval is by keyword:
type a saved keyword to find the memory, even when the word is not in its
content, and add keywords to narrow. AI assistants connect through a hosted MCP
server; Claude connects from its connector directory, and ChatGPT is listed as
"in preparation".

- **MCP:** `https://www.usememory.com/api/mcp`, OAuth 2.0 authorization code
  with S256 PKCE and dynamic client registration. Access tokens last one hour;
  refresh tokens rotate within a 30-day connection. Scopes: `read`, and optional
  `write`, `delete` and `offline_access`. Write and delete are off by default
  when a user connects an assistant.
- **Keyword-restricted access:** a token can be limited to selected keywords.
- **REST** (bearer `mem_...` tokens, 120 requests a minute per token):
  - `POST /api/v1/memories`: create or update by `externalRef`, with a
    `sourceUpdatedAt` that makes an older write a no-op (200 "stale");
  - `GET /api/v1/memories`: newest first, cursor pagination, `updatedSince`
    polling;
  - `GET /api/v1/memories/{externalRef}` and `/memories/id/{id}`;
  - `DELETE /api/v1/memories/{externalRef}`: needs the `delete` scope, and is
    refused (409) for encrypted, shared or attached memories;
  - `GET /api/v1/search`: keyword full-text search ("keywords weigh more than
    body text"), then recency; results carry title, snippet, keywords,
    `updatedAt` and a score;
  - `GET /api/v1/keywords`: the keyword inventory with counts.
- **Encryption:** memories can be encrypted client-side; through the API an
  encrypted memory reads as `locked` with empty content and is not searchable.
- **Sharing:** read-only shares, revocable; revoking "cannot retrieve content
  an assistant has already received".
- **Monitoring boundary:** API monitoring records counts, timings, result counts
  and error categories, never search text, keywords or content.
- **Known gap, stated by them:** deletions are not reported through the API; a
  client must compare full lists.

## Where OpenChronicle is already ahead

- **Self-hosted, open source, LAN-local.** Data never leaves the operator's NAS
  except as age-encrypted offsite backups (v3.6.0).
- **Semantic recall.** Hybrid FTS5 plus embeddings fused by RRF, with per-call
  `mode` and `phrase`; #memory is keyword-only, and its encrypted memories are
  not searchable at all.
- **Structure.** Projects plus tags, pins as standing rules, `memory_stats`
  per-tag counts (close to their keyword inventory), `context_recent`.
- **Ingestion.** `onboard_git` turns a repository's history into memory
  clusters.
- **Size.** 100,000 characters per memory against their 10,000.
- **Recovery.** Verified local snapshots, a guarded restore path, `oc memory
  export/import`, and the nightly encrypted offsite push; #memory states no
  export or backup at all.
- **Safer deletes.** A required two-step preview before any delete.

## Gaps: what they do that OpenChronicle does not

Each gap names what "better" would mean here and its roadmap ID.

1. **Scoped, short-lived credentials (PAR-01).** OC has one static API key that
   every client shares, with full read, write and delete. *Better:* per-client
   tokens with `read`/`write`/`delete` scopes and a project or tag restriction,
   revocable one at a time, with each token named in the audit trail. This
   is also the precondition that makes the parked backup tools (OPS-07) and
   `memory_delete` safe to hand to an autonomous agent. OAuth 2.1 with PKCE and
   dynamic client registration is the MCP-spec route; per-client static tokens
   are the smaller first step.
2. **Integration sync semantics (PAR-02).** `externalRef` upsert with a
   `sourceUpdatedAt` staleness guard, `updatedSince` cursor polling. OC has
   neither; an external tool that re-sends a note creates a duplicate.
   *Better:* the same idempotent upsert, plus a deletion feed. They say
   deletions are not reported, which forces full-list comparison. This
   overlaps RET-03's operation-identity ADR, which should come first.
3. **Attachments (PAR-03).** Photos, videos and documents stored beside a
   memory. OC is text only. *Better:* attachments whose extracted text (and
   image captions from a local model) joins hybrid search, so an attachment is
   findable by meaning, not only by its keywords. Needs a blob store, and
   backup, export and offsite coverage for it. The largest item here.
4. **A human interface (RET-04, existing).** Native apps are their core
   product. OC has none. *Better, and smaller:* RET-04's human-facing memory
   inspector, web first; native apps are not a goal.
5. **Per-memory encryption (PAR-04, research).** Their client-side encryption
   leaves a memory unreadable to the server and unsearchable. On a self-hosted
   store the threat model differs: the server is the operator's own. *Better*
   is an open question: per-project encryption at rest with a key the operator
   holds, keeping search for unlocked projects. Research before any design.
6. **Sharing (PAR-05, research).** Read-only, revocable shares. OC has one
   operator. Only relevant if OC gains a second person; record, don't build.
7. **Keyword-first retrieval (PAR-06).** Their headline experience: type a
   label you chose, find the memory even when the word is absent from the text.
   OC already indexes tags in `memory_fts` beside the content, so a tag is
   searchable, but the default FTS5 rank weighs both columns equally, and
   #memory weighs keywords above body text. *Better:* give the `tags` column a
   higher `bm25()` weight in the keyword channel, measured under MEAS-04's
   evaluation so it cannot quietly hurt accuracy.
8. **A stated telemetry boundary (PAR-07).** Their monitoring never records
   search text, keywords or content. OC's metrics are off by default and their
   labels are bounded, but the guarantee is not written down or tested.
   *Better:* state it in `security_posture.md` and pin it with a test over the
   metric label sets.
9. **Directory listing.** Claude connects to #memory from its connector
   directory. Not pursued: that needs a public endpoint, and OC is deliberately
   LAN-only.

## Not copied

- **Cloud-only hosting**, and the account model that comes with it.
- **Keyword-only search.** It is a floor OC is already above.
- **Delete refusal (409) for shared or attached memories** as a rule. OC's
  two-step preview covers the same risk; revisit only with PAR-03 or PAR-05.

## Order, if ratified

PAR-07 (a document and a test) and PAR-01's per-client tokens first: they are
small and they unblock OPS-07. PAR-06 needs MEAS-04's evaluation. PAR-02 after
RET-03's ADR. PAR-03 is its own design with a plan review. PAR-04 and PAR-05
stay research.
