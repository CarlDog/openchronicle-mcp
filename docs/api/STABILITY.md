# API + MCP tool stability

What stays stable, what's allowed to change, and the deprecation
process when something must break.

**In force since the `v3.0.0` tag (2026-08-28).** The pre-tag escape
hatch that stood here until then has been removed, as it instructed.

## Surfaces under this promise

- **HTTP REST**: `/api/v1/*` routes documented in the auto-generated
  OpenAPI spec at `/openapi.json`.
- **MCP tools**: the tool surface registered by
  `interfaces/mcp/server.create_server`. Listed in
  `docs/integrations/mcp_server_spec.md`.

`/health` (the public liveness probe) and `/openapi.json` are also
stable but not under semver — they are operator infrastructure, not
client API.

## Versioning

OC follows [Semantic Versioning](https://semver.org/). The version has
one source — `pyproject.toml`, read at runtime through
`src/openchronicle/version.py` (`importlib.metadata`) — consumed by the
FastAPI app, the CLI, and both health surfaces' `package_version`
field. Release flow: bump `pyproject.toml` in the same commit that the
`v*` tag points at; CI refuses to build a tag whose name doesn't match
the declared version (`v3.0.0-rc6` ↔ `3.0.0rc6`).

| Bump | Trigger |
|---|---|
| MAJOR | Breaking changes to `/api/v1/*` schemas, MCP tool signatures, or the `core.json` schema. Triggers a `/api/v2/*` parallel deployment for a deprecation window. |
| MINOR | Additive features. New tools, new fields on existing responses, new optional parameters, new env vars with safe defaults. |
| PATCH | Bug fixes, performance improvements, doc-only changes, internal refactors with no observable surface change. |

## Allowed-without-major-bump

- Adding new fields to response objects (consumers must tolerate
  unknown fields).
- Adding new optional query parameters / request body fields.
- Adding new MCP tools.
- Renaming an MCP tool when the old name is kept as an alias for at
  least one MAJOR cycle.
- Removing fields from request bodies if they were previously
  ignored / default-only.
- Tightening input validation that rejects values the prior version
  was already documented to reject (e.g. lengthening a min_length from
  unset to 1 on a field documented as "non-empty").

## Requires-major-bump

- Removing a route or MCP tool.
- Removing a field from a response.
- Renaming a field in a request or response.
- Changing a field's type (string → integer, etc.).
- Changing the meaning of an existing field.
- Tightening input validation that rejects values the prior version
  accepted (e.g. shortening a max_length).
- Changes to the `core.json` schema that aren't backward-compatible.
- Changes to env var names.

## Deprecation window

When a MAJOR change is required:

1. Implement the new shape behind a new prefix or tool name.
2. Mark the old shape deprecated in docs and the OpenAPI spec
   (`deprecated: true` on the route).
3. Keep the old shape working for at least one MAJOR cycle. Both
   versions ship in the same image; operators choose which to use via
   the URL.
4. Remove the old shape in the MAJOR after that.

For server-side changes that don't have a clean parallel-deployment
shape (e.g. a fundamental SQLite schema overhaul), use the schema
migration framework (`infrastructure/persistence/migrator.py`) to
apply changes idempotently and document the data migration path in
the release notes.

## Why this matters

OpenChronicle has no active external consumers today — this is a
single-user personal project. The rule exists so future-us doesn't
accidentally break our own `~/.claude.json` config or any tooling
that's accumulated around the surface. Locking the rule down at v3
means future feature work doesn't get into "wait, can we change
this?" debates.

## See also

- `docs/integrations/mcp_server_spec.md` — the full MCP tool surface
- `docs/configuration/env_vars.md` — env var inventory
