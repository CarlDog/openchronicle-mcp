# 0015 — Prompt Library (procedural memory) for OpenChronicle

**Status:** Research recorded; proposal unratified and unscheduled. Not an
ADR. Nothing here changes current behavior until
[CODEBASE_ASSESSMENT.md](../CODEBASE_ASSESSMENT.md) records it as shipped.

**Assessment date:** 2026-09-22 (America/Chicago).

**Baseline:** `main` at `429f137a` (release `v3.3.0` plus the unreleased
metrics work), MCP Python SDK `1.29.1`.

**Work-item key:** `CarlDog/openchronicle-mcp#research-0015-prompt-library`

**Operator request (2026-09-22):** "LLM prompt caching". Well-defined,
well-written prompts come out of LLM work sessions and should be captured,
stored and reused. **Scope decision (operator, same day):** the library
serves *any MCP client* (Claude Code, Gemini CLI/Antigravity, Codex, VS
Code, goose, and others), not only Claude Code sessions.

## Conclusion

1. **Name it a Prompt Library of saved prompts, not "prompt caching".**
   "Prompt caching" already names three unrelated mechanisms that this
   design has to discuss:
   - provider-side exact-prefix KV caching (Anthropic `cache_control`,
     OpenAI automatic caching, Gemini context caching, llama.cpp/Ollama
     prefix reuse);
   - the MCP 2026-07-28 caching utility, which puts `ttlMs`/`cacheScope` on
     `prompts/list` itself;
   - the client-side caches that prompt-management SDKs keep.

   The category is **procedural memory**: memory of *how* to do something,
   as distinct from OC's existing episodic and semantic memories.
2. **It is feasible on today's stack.**
   - OC already advertises an empty MCP `prompts` capability
     (`listChanged: false`).
   - A probe confirmed that database-backed `prompts/list` and
     `prompts/get` work by overriding two methods on OC's existing
     `MetricsFastMCP` subclass. It needs no new dependency and no in-process
     registry.
3. **Recommended shape (Option B): dedicated tables with immutable,
   content-hashed versions and one approved pointer, served three ways:**
   - **tools**, which the model can call, so every MCP client can use them;
   - **MCP prompts**, which the user invokes as slash commands where the
     client supports them;
   - **REST**, for Open WebUI and scripts.

   Prompts never enter `memory_search` ranking. That keeps them out of the
   retrieval-accuracy path, which ADR 0008's pin-crowding result shows is
   easy to damage.
4. **The hard problem is trust, not storage.** A saved prompt is replayed
   *as instructions, with the user's authority*, and on this LAN any client
   can write, because auth is intentionally off. The evidence is consistent:
   - self-generated agent skills scored *below* having no skills at all,
     while curated ones added +16.6 percentage points (SkillsBench);
   - poisoned skill marketplaces exist in the wild (ClawHavoc);
   - OWASP's 2026 guidance says instruction-bearing memory writes are
     privileged and should be approved before they persist.

   So capture lands in **draft**. **Promotion to approved is a human act
   through a channel an agent cannot self-serve.** Only approved versions
   are served as MCP prompts or returned by default.
5. **The ecosystem is moving from stored prompt objects to Agent Skills.**
   - OpenAI deprecated reusable prompt objects on 2026-06-03, with shutdown
     on 2026-11-30.
   - Anthropic's Workbench saved prompts ended on 2026-08-17.
   - Humanloop shut down on 2025-09-08.
   - The open Agent Skills format (`SKILL.md`) is now read by Claude Code,
     Codex, Gemini CLI, Cursor, VS Code/Copilot and Devin.

   OC's differentiator is being the **cross-client, searchable, versioned,
   provenance-carrying library with a human gate**. `SKILL.md` export is a
   delivery format, not a competitor.
6. **Start with a zero-code Stage 0.** Save candidate prompts as memories in
   a dedicated OC project for two weeks. That produces the real examples
   that become Stage 1's evaluation fixture, and it shows whether reuse
   actually happens before any code is written.

## 1. Terminology

| | Provider prompt caching | Prompt library (this proposal) |
|---|---|---|
| Purpose | Cheaper and faster repeated request prefixes | Consistent reuse of good instructions |
| Unit | A hashed token prefix | A named, versioned document |
| Identity | Exact bytes up to a breakpoint | Slug plus version or label |
| Lifetime | Minutes to about a day | Until retired |
| Controlled by | The provider (automatic or hinted) | The user or agent (save, promote, retire) |
| Discoverable | No | List, search, get |
| Failure mode | A miss, so you pay full price | A wrong, stale or poisoned prompt, so wrong behavior |

**Where the two interact.** A rendered saved prompt helps provider caching
only when it forms a byte-stable prefix, which is the API-caller case where
it becomes a system prompt. MCP prompts arrive as *user* messages after
the client's own system prompt and tool list, and most saved prompts are
below the providers' minimum cacheable lengths:

- Anthropic: 512–4,096 tokens, depending on the model;
- OpenAI: 1,024 tokens on GPT-5.6;
- Gemini implicit caching: 2,048–4,096 tokens.

The larger cache lever is on OC's own side. **Never put dynamic library
data** (catalogues, counts, timestamps) **in tool descriptions or server
`instructions`.** Those sit at the front of every client's cached prefix,
and the MCP 2026-07-28 revision asks servers to return tools in a stable
order for exactly this reason.

**Side note for the operator's own rules.** Ollama 0.33.3 (2026-09-02)
added `prompt_eval_cached_count`, so a cache hit on the NAS is now
observable. The fleet rule file that says there is "no cache-hit signal"
is stale on this point.

## 2. What OC has today, and what a prompt needs that it lacks

| Need | Closest existing feature | Gap |
|---|---|---|
| An instruction that always applies | A pinned memory tagged `convention`, which floats into matching searches | That is *guidance retrieved by relevance*, not a procedure the user deliberately runs |
| Exact lookup by a stable name | `memory_get` takes a UUID; `memory_search(phrase=true)` still ranks | No slug, and nothing enforces uniqueness |
| Parameters | None | Content is opaque text |
| Immutable versions | `memory_update` replaces content in place | No history (edit history is deferred, V3_PLAN) |
| Verbatim rendering | `memory_get` returns a dict, delivered as JSON-escaped text | The body always arrives wrapped |
| User invocation | None | No slash-command path |
| Outcome or usage signal | None, by design (telemetry dropped, V3_PLAN Q8) | Would revisit a recorded decision |

**The zero-code baseline ("Option 0").** Each prompt revision is saved as
a new memory in a dedicated `prompt-library` project, tagged `prompt` and
`prompt:<slug>`. The latest one is fetched with:

```text
memory_list(project_id=LIB, tags=["prompt:<slug>"], order_by="created_at", limit=1)
```

Tags filter as "all of" in SQL before the limit is applied. Searches in
other projects never see these rows unless they are pinned and global.

This gives near-exact lookup, a revision history and no code. It does
*not* give enforced uniqueness or immutability, parameters, verbatim
output, slash commands, or a trust gate.

## 3. Evidence from the ecosystem (condensed; sources at the end)

### 3.1 Prompt registries converge on one data model

Langfuse, MLflow Prompt Registry, LangSmith, Braintrust, PromptLayer,
Portkey and Agenta share the same model:

- **A named prompt.** A slug with folders, per project or workspace.
- **Immutable versions.** Each holds the template or messages, the template
  format, model settings (often), and a commit note, author and time.
- **Movable pointers.** Called labels, aliases or environments:
  `production`/`staging` plus a reserved `latest`. Rollback means moving
  the pointer; protected pointers need approval.
- **A usage link.** Each trace or run records the version that produced
  it.
- **Variable syntax.** Mostly `{{var}}`; logic-capable engines such as
  Jinja2 and Nunjucks are opt-in.

No surveyed product serves its stored prompts through the MCP `prompts`
primitive. They all expose **tools**. The first-party hosted prompt objects
from OpenAI, Anthropic's Workbench and Humanloop have been retired or are
being retired.

### 3.2 The MCP `prompts` primitive and client reality

**The spec.** Current revision 2026-07-28; prompts are *not* deprecated.

- The user chooses *when* to run a prompt. The model cannot invoke one.
- Arguments are string-to-string maps. Messages are `user` or `assistant`
  only; there is no system role.
- `prompts/list` must carry `ttlMs`/`cacheScope`. List changes travel over
  `subscriptions/listen`.
- The spec's only prompt-specific security rule: validate inputs and
  outputs.

**What OC's pinned SDK can do.** Version 1.29.1 speaks revisions up to
2025-11-25. In OC's stateless streamable-HTTP mode, a
`notifications/prompts/list_changed` has no stream to travel on, so
clients see new prompts only when they reconnect. SDK 2.0.0 (2026-07-28)
is the first to support the 2026-07-28 revision. This is a named trigger
for the already-parked mcp 2.x migration, not a blocker.

**Client support (checked against client source and docs, 2026-09-22).**

| Client | Lists prompts | How the user invokes one | Arguments |
|---|---|---|---|
| Claude Code | Yes | `/server:prompt`, or typed `/mcp__server__prompt` | Positional, split on whitespace |
| VS Code + Copilot | Yes | `/server.prompt` | One picker per argument; the only client with argument completion |
| Gemini CLI | Yes | `/prompt` or `/server.prompt` | Named or positional; uses only the *first* message returned |
| Devin Desktop (formerly Windsurf) | Yes | `/mcp__server__prompt` | Positional |
| goose | Yes | `/prompt name key=value` | Returned messages must alternate roles |
| Zed | Partly: hides prompts with more than one argument | `/prompt` | 0 or 1 |
| Continue | Partly, and the repo is now read-only | `/prompt` | Sends every argument as an empty string |
| Claude Desktop, claude.ai | Yes, per MCP docs | "+" menu → Connectors | Unverified |
| Codex CLI | **No** | — | — |
| Open WebUI | **No** (native MCP tools only) | — | — |
| Google Antigravity | Undocumented | — | — |

**What that means for a library meant for any client.**

- **Tools are the universal channel.** No client lets the *model* call a
  prompt.
- **MCP prompts are the human convenience layer.** The portable shape is:
  - no arguments, or one optional free-text argument;
  - a single user-role text message;
  - a short list that fits on one page, because several clients read only
    the first page.

### 3.3 Procedural memory research: validation is what makes reuse work

| System | How it validates what it stores | Result, and the catch |
|---|---|---|
| Voyager | Keeps a skill only after a self-check succeeds | Removing the check cut discoveries by 73% |
| Agent Workflow Memory | Keeps only workflows from runs an LLM grader judged successful | WebArena 35.5 vs 23.5; online mode can learn wrong workflows |
| ExpeL | Up- and down-votes insights and retires them at zero | ALFWorld 59.0% vs 40.3% |
| ACE | Makes small edits to a playbook with helpful/harmful counters | Warns about *context collapse*: repeated whole rewrites shrank one context from 18,282 tokens to 122 |
| SkillsBench (2026) | Compares curated skills with ones agents wrote for themselves | Curated: +16.6 pp. Self-generated: below using no skills at all, on all three setups |

OC runs no model. The transferable lessons are the ones a store can
enforce without judging content:

- Keep a "when to use this" description separate from the body, and
  search on it.
- Retrieve few results.
- Supersede explicitly; never overwrite.
- Prefer small edits to wholesale rewrites.
- Show the closest existing prompts on save rather than auto-merging.
- Record provenance and human approval.
- Store caller-reported outcomes; don't grade content itself.

### 3.4 File formats: Agent Skills is the export target

**The landscape.**

- Claude Code's `.claude/commands` has been merged into Skills.
- Codex's `~/.codex/prompts` was removed in v0.118.0 (2026-03-31) in favor
  of skills.
- VS Code `.prompt.md` files are deprecated for agent-host sessions.
- Continue is frozen.
- The `SKILL.md` spec: `name` of 1–64 characters (lowercase letters,
  digits, hyphens) plus a `description`.

**Placeholder syntaxes conflict:**

- Claude Code's `$0` is the *first* argument, while Codex used `$1` for it.
- Gemini CLI's `{{args}}` collides with Jinja2 and Mustache.
- Continue treats unknown `{{x}}` as a file read.

**Executable directives are common.** These include shell (`` !`cmd` ``,
`!{}`), file inclusion (`@path`, `#file:`, `${file:}`), environment and
secret references (`${env:}`), tool grants and bundled `scripts/`.

**For OC, this means:**

- Slugs should be `SKILL.md`-compatible, so export is lossless and names
  stay slash-safe.
- Any future importer must store directives byte for byte, never resolve
  or run them, and flag them.

### 3.5 Risk register

| Risk | Mechanism | Control this design adopts |
|---|---|---|
| Laundering at capture | An agent saves a "good prompt" containing text it read from an untrusted page or file | Save as a draft; a human promotes through an agent-inaccessible channel; record provenance |
| Invisible or control characters | Tag characters (U+E0000–E007F), variation selectors, zero-width characters, bidi controls and ANSI escapes hide instructions from a reviewer | **Refuse at write time** (never strip), naming the code points; escape them on display |
| Secrets in the body | Session text carries tokens and hostnames into every later request and into exports and backups | Offline secret-pattern scan at write time; refuse on a hit; never redact on read |
| Edit after approval | An approved prompt is changed later | Immutable, content-hashed versions; any edit creates a new unapproved version |
| Template injection | Template engines evaluate expressions (CVE-2025-65106 class) | Literal single-pass `{{name}}` substitution only; inserted values are never re-expanded |
| Output injection via `prompts/get` | Fake assistant turns; poisoned output (a 93.3% success rate in one published setup) | A single user-role text message; approved versions only |
| Unauthenticated writes | Any LAN host, or a browser via DNS rebinding | The existing Host allowlist, plus the promotion gate below |
| Trusting a classifier as the gate | Adaptive attacks beat most published detectors more than 90% of the time | Detectors may only ever be *advisory* |

## 4. Constraints from OC's own records

| Constraint | Source | Consequence here |
|---|---|---|
| Accuracy first, responsiveness second | AGENTS.md (2026-09-08); 0011 | Prompts stay out of `memory_fts`, the pin float and embeddings. Measure p95/p99 latency of `prompts/list` and `prompt_get` proportionately. |
| Edit history deferred; "revision-dependent features wait for the lifecycle design" | V3_PLAN; 0011 §3 | **Revisit explicitly.** A reproducible slash-command body *is* the "real consumer" that deferral waited for. The ADR must say how prompt versions reconcile with any later memory-history design. |
| Operation identity for retries | 0011 §2; 0004 Finding 7 | A template version *is* its content, so identity is (scope, slug) plus body hash. A retry with the same body is a no-op; a stale `base_version` is an explicit conflict. |
| "`source="mcp"` is not an authority level" | 0011; 0002 Finding 6 | Record `created_via` as a transport label only. The enforceable control is *who may promote*. |
| A `confirm` flag is advisory against an autonomous agent | Fleet MCP-authoring rule | Promotion can't be a tool parameter. It needs a channel the agent cannot self-supply. |
| Validate every field before the first durable write | Fleet MCP-authoring rule | The save use case validates slug, body, parameters, caps, the Unicode policy and the secret scan, then writes |
| Zero secrets; logs are not redacted | AGENTS.md; security_posture.md | Refuse credential-shaped bodies; never log bodies |
| `MAX_CONTENT_CHARS` enforced in use cases | memory_item.py | Reuse it for bodies; also cap argument values and rendered output |
| Auth intentionally off on a trusted LAN | security_posture.md | The trust gate must not assume authentication exists |
| STABILITY.md covers REST and MCP *tools* | docs/api/STABILITY.md | New tools, routes and tables are MINOR. Amend STABILITY to cover the `prompts/*` *mechanism* (naming, argument semantics, error codes), not the user-data list. |
| Branch policy | AGENTS.md | Additive, so MINOR (e.g. 3.4.0) from `main`, then merge `main` → `v4/develop` |
| Hexagonal boundaries; no `mcp` import in core | Boundary tests | The renderer and use cases live in core. `PromptMessage` is built only in `interfaces/mcp`. |
| Persistence only through ports; no server-side state outside the DB | 0007 rules 1 and 3 | A `PromptStorePort`; handlers read the DB per request, not a FastMCP in-process registry |
| SQLite is canonical; Markdown/git as canonical is outside the direction | 0011; V3_PLAN | Rules out a git-canonical store (Option C) as the primary design |
| Hard delete, no soft delete | V3_PLAN | `prompt_delete` hard-deletes behind the two-step confirm. Revoking approval clears a pointer; it is not a soft delete. |
| Tool count and snapshot | mcp_server_spec.md; schema snapshot test | 18 → 22 tools; regenerate the snapshot |

## 5. Options

### Option A: prompts as typed memories

Add `kind`, `slug` and `version` columns to `memory_items`.

- **Upside:** cheapest start, about 3–4 sessions.
- **The cost is retrieval correctness.** Prompt rows would have to be
  excluded on about eight read paths: FTS5, the fallback scorer,
  eligibility, the pin float, list, stats, `context_recent`, export and
  backfill.
- **The git-onboard watermark shows how that goes.** It is a non-memory
  row in `memory_items`, and only export and import special-case it. Every
  missed path is a silent accuracy regression: prompt instructions
  surfacing in memory search, getting embedded, even getting tombstoned.
  Immutability would be a guard, not a structure.
- **Semver risk:** it changes what existing reads can return unless every
  default excludes prompts.

**Not recommended.**

### Option B (recommended): dedicated tables, immutable versions, three surfaces

```sql
-- migration 005_prompt_library.sql (prompt_fts + triggers go in _ensure_fts5,
-- because the migration splitter cannot hold trigger bodies)
CREATE TABLE IF NOT EXISTS prompt_templates (
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,   -- SKILL.md-compatible slug, validated in the use case
    project_id       TEXT,            -- NULL = global library
    title            TEXT,
    description      TEXT NOT NULL,   -- "when to use this"; the search target
    tags             TEXT NOT NULL,   -- JSON array, same shape as memory_items.tags
    head_version     INTEGER NOT NULL,
    approved_version INTEGER,         -- what prompts/list serves; NULL = draft only
    created_at       TEXT NOT NULL,
    updated_at       TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_templates_scope_name
    ON prompt_templates (COALESCE(project_id, ''), name);

CREATE TABLE IF NOT EXISTS prompt_versions (   -- append-only: the port exposes no UPDATE
    prompt_id    TEXT NOT NULL,
    version      INTEGER NOT NULL,
    body         TEXT NOT NULL,                -- <= MAX_CONTENT_CHARS
    parameters   TEXT NOT NULL,                -- JSON [{name, description, required, max_length}]
    body_hash    TEXT NOT NULL,                -- sha256 over canonical (body, parameters)
    created_via  TEXT NOT NULL,                -- transport label: mcp|api|cli|import (NOT authority)
    source_ref   TEXT,                         -- optional provenance: repo/path/commit, session, model
    change_note  TEXT,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (prompt_id, version),
    FOREIGN KEY (prompt_id) REFERENCES prompt_templates(id) ON DELETE CASCADE
);
```

#### Surfaces

- **Tools (4; 18 → 22).** These are the channel the model uses.
  - `prompt_save(name, body, description, …, base_version=None)` creates a
    new draft version. The same body is a no-op; a stale `base_version` is
    a conflict. The response lists the nearest existing prompts.
  - `prompt_get(name, version=None, arguments=None, include_drafts=False)`
    returns the body verbatim as the first text block, with structured
    metadata (status, version, hash, provenance). The annotated
    `CallToolResult` form keeps an output schema for the snapshot guard.
  - `prompt_search(query=None, tags=None, project_id=None,
    include_drafts=False)` searches FTS5 over name, title, description and
    tags. It returns **metadata only, never bodies**.
  - `prompt_delete(name, confirm)`: two-step, hard delete.
  - Descriptions are static text.
- **MCP `prompts/list` and `prompts/get`.** These are the human channel.
  - They serve **approved** versions only, as a short one-page list in
    deterministic order.
  - Each prompt takes zero or one optional free-text argument and renders
    to one user-role text message.
  - An unknown name or a missing argument returns `-32602`.
  - Provenance goes in `description`; ids and the hash go in `_meta`.
  - Missing or empty arguments are tolerated, because Continue sends empty
    strings.
- **REST** under `/api/v1/prompt`, mirroring the tools, with **no** approve
  route.
- **CLI:** `oc prompt save|list|show|render|delete|approve|revoke`.

#### Rendering

- Literal single-pass `{{name}}` substitution. A value containing
  `{{x}}` stays literal.
- The placeholders must match the declared parameters exactly at save
  time.
- The output bytes are deterministic, and the content hash is returned so
  callers can check byte stability.
- No Jinja2 and no `str.format`.

#### Write-time checks

These refuse; they never strip, and every field is validated before the
first write:

- a slug regex;
- size caps;
- the Unicode policy in §3.5;
- a secret-pattern scan;
- parameter and placeholder agreement.

#### Trust gate (operator decision; §7 Q1)

Promotion to approved happens **only through the host CLI**
(`oc prompt approve`). No MCP tool and no REST route can set
`approved_version`, and an inventory test enforces that.

This assumes agents have no shell on the OC host. If they do, require an
out-of-band operator token for approval instead, one that is not present
in any agent environment.

#### Packaging

- **Export/import:** bump the envelope to v2 with templates and every
  version. Import accepts v1 and v2. An older build rejects v2 loudly
  rather than silently dropping the unknown array.
- **Project delete:** remove the project's templates explicitly; their
  versions cascade.
- **Health:** add an approved-prompt count key.
- **Effort:** about 6–9 sessions (inferred).
- **Semver:** MINOR.

### Option C: OC as an index over git-canonical prompt or skill files

OC syncs `SKILL.md` and command files from repositories and stores only
metadata, provenance and a body cache.

- **It conflicts with three records:**
  - SQLite, not Markdown or git, is canonical;
  - v3 keeps SQLite plus embeddings;
  - no filesystem coupling beyond the store.
- **It widens `onboard_git`'s deliberately narrow clone boundary**, which
  never checks out file contents.
- **Rendering forces a choice:** from a live fetch it is slow and depends
  on git being reachable, and with a cache it is Option B plus an
  importer.

Keep its best idea instead: the `source_ref` provenance field in Option B,
and a trigger-gated importer (§6, Stage 2).

### Comparison

| | Option 0 (memories + tags) | A: typed memories | **B: dedicated tables** | C: git index |
|---|---|---|---|---|
| Stable-name lookup | By convention | Partial unique index | **Enforced** | Yes |
| Parameters | No | Bolted on | **Yes** | From front matter |
| Immutable versions | By convention | Guard only | **Append-only table** | Git history |
| Kept out of memory search | Project scoping only | Filter on about 8 paths | **By construction** | By construction |
| Trust gate | None | Hard | **CLI promotion** | Git review |
| Fits the recorded direction | Yes | Overloads `memory_items` | **Yes** | Contradicts 3 records |
| Effort | 0 | 3–4 sessions | **6–9 sessions** | 5–7 sessions plus ops |

## 6. Staged path

Each stage opens only when its trigger fires. Recording this document
does not schedule any of it.

- **Stage 0 (now, no code).**
  - The operator saves candidate prompts into a dedicated OC project
    (tags `prompt`, `prompt:<slug>`) for about two weeks, noting when
    each gets reused.
  - **Exit:** at least 10 prompts that were actually reused, or an honest
    "reuse didn't happen", which closes the proposal.
  - The reused set becomes the Stage 1 gold set (intent → slug, hit@1 and
    hit@3).
- **Stage 1 (trigger: Stage 0 exit met and the operator ratifies an ADR).**
  - Build Option B's core (schema, port, use cases, the four tools, CLI
    approve and revoke, `prompts/*` for approved versions, REST, export
    v2, write-time checks).
  - **The plan gets its own adversarial review before implementation.**
    The fleet pre-deploy rule applies to plans.
  - **Acceptance:**
    - every write-time check refuses the bad inputs in §3.5 and is
      mutation-verified;
    - no MCP or REST path can promote;
    - end-to-end tests through the mounted stateless `/mcp` endpoint show
      `prompts/*` serving approved prompts only, in deterministic order;
    - FTS hit@3 on the Stage 0 gold set is at least Option 0's;
    - p95/p99 latency of `prompts/list` and `prompt_get` is within the
      existing noise budgets of `memory_get`;
    - memory-retrieval benchmark results are unchanged.
- **Stage 2 (trigger-gated follow-ons).**
  - A `prompt_feedback` outcome log (append-only; it revisits the
    telemetry decision, so the operator must choose it).
  - `SKILL.md` export first, Prompty v2 for fidelity.
  - A quarantining importer for `SKILL.md` and commands, which stores
    directives byte for byte and flags them.
  - Embeddings for prompt search, only if FTS misses the hit@3 bar.
- **Stage 3 (trigger: the mcp 2.x migration happens for any reason).**
  - `ttlMs`/`cacheScope` on `prompts/list`.
  - `subscriptions/listen` delivery of `list_changed`.
  - Named labels beyond latest and approved, if two versions ever need to
    be live at once.

**Stop conditions:**

- Stage 0 shows no real reuse.
- The trust gate cannot be made agent-inaccessible in this deployment.
- Stage 1 cannot meet its accuracy or latency acceptance within the
  existing budgets.

Negative results are recorded, not buried.

## 7. Open questions for the operator

1. **Promotion gate.** Is host-CLI-only enough (do any agents have a shell
   on the NAS?), or should approval need an out-of-band token, or wait
   for 0011 §5's human-facing inspector?
2. **Scope of the served list.** `prompts/list` takes no project argument
   and must not vary per connection. The proposal is one global slug
   namespace, with project as a tag and a search filter.
3. **Arguments in v1.** Verbatim-only, or at most one optional free-text
   argument (the portable maximum)?
4. **Relationship to the git-canonical fleet skills.** OC as the
   cross-client runtime library and capture inbox, with git remaining
   canonical for curated fleet skills and export/import as the bridge? Or
   should OC replace them?
5. **Capture.** Explicit saves only (recommended)? Hook-drafted candidates
   (Claude Code's `UserPromptSubmit`) would add per-turn latency and
   privacy and secret exposure.
6. **Outcome signals.** Add `prompt_feedback`, which revisits the dropped
   telemetry decision, or rely on human curation only?
7. **Tool budget.** Is 18 → 22 tools acceptable?
8. **Draft retention.** Keep drafts forever, or expire unapproved drafts,
   as OWASP ASI06 suggests?
9. **Stage 0 first?** (Recommended.)

## Sources (accessed 2026-09-22)

MCP specification and SDK:

- <https://modelcontextprotocol.io/specification/2026-07-28/server/prompts>
- <https://modelcontextprotocol.io/specification/2026-07-28/changelog>
- <https://modelcontextprotocol.io/specification/2026-07-28/server/utilities/caching>
- <https://github.com/modelcontextprotocol/python-sdk/releases>

Clients:

- <https://code.claude.com/docs/en/mcp>
- <https://github.com/microsoft/vscode-docs/blob/main/docs/agent-customization/mcp-servers.md>
- <https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/tools/mcp-server.md>
- <https://developers.openai.com/codex/mcp>
- <https://docs.openwebui.com/features/workspace/prompts/>

Provider caching:

- <https://platform.claude.com/docs/en/build-with-claude/prompt-caching>
- <https://developers.openai.com/api/docs/guides/prompt-caching>
- <https://ai.google.dev/gemini-api/docs/caching>
- <https://github.com/ollama/ollama/releases/tag/v0.33.3>

Registries and retirements:

- <https://langfuse.com/docs/prompt-management/data-model>
- <https://github.com/mlflow/mlflow/blob/master/docs/docs/genai/prompt-registry/index.mdx>
- <https://developers.openai.com/api/docs/deprecations>
- <https://platform.claude.com/docs/en/release-notes/overview>
- <https://humanloop.com/docs/guides/migrating-from-humanloop>

Skills and formats:

- <https://agentskills.io/specification>
- <https://code.claude.com/docs/en/skills>
- <https://developers.openai.com/codex/custom-prompts.md>
- <https://raw.githubusercontent.com/microsoft/prompty/main/web/src/content/docs/core-concepts/file-format.mdx>

Research:

- CoALA <https://arxiv.org/abs/2309.02427>
- Voyager <https://arxiv.org/abs/2305.16291>
- AWM <https://arxiv.org/abs/2409.07429>
- ExpeL <https://arxiv.org/abs/2308.10144>
- ACE <https://arxiv.org/abs/2510.04618>
- SkillsBench <https://arxiv.org/abs/2602.12670>

Risks:

- OWASP LLM Top 10 2026 <https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/>
- OWASP Agentic Top 10 <https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/>
- MCP prompt attacks <https://arxiv.org/abs/2509.24272>
- Adaptive attacks <https://arxiv.org/abs/2510.09023>
- ClawHavoc <https://www.antiy.net/p/clawhavoc-analysis-of-large-scale-poisoning-campaign-targeting-the-openclaw-skill-market-for-ai-agents/>
- LangChain template CVE <https://github.com/advisories/GHSA-6qv9-48xg-fc7f>

Internal evidence (probes against `main` 429f137a and SDK 1.29.1) is
retained in the session scratchpad. It shows:

- OC advertises `prompts` with an empty list;
- a subclass override serves prompts from a mutable store per request,
  with cursor pagination and `-32602` errors;
- FastMCP's registry cannot replace or remove prompts;
- `send_prompt_list_changed()` never reaches the wire in stateless mode;
- `completion/complete` returns `-32601`.
