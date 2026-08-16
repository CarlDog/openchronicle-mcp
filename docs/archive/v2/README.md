# v2 documentation archive (frozen)

Frozen copies of the v2-only documentation, taken verbatim from the
`archive/openchronicle.v2` branch (`bb217d9`). These describe subsystems
the v3 slimming deleted — the conversation engine, plugins, Discord,
assets, STDIO RPC — and are preserved for reference only. Nothing here
is maintained, linted, or expected to match the current codebase.

Provenance note: Phase 7 (2026-05-05) classified these docs as
"archive" and recorded them as moved here, but a v2-era `.gitignore`
rule (`docs/archive/`) silently swallowed the move — the files were
never committed. Restored from the branch on 2026-08-16 (full-repo
review Batch E). The branch remains the authoritative v2 snapshot.

| File | What it covered |
|---|---|
| [CODEBASE_ASSESSMENT.md](CODEBASE_ASSESSMENT.md) | The v2 senior-dev assessment — the body that lived under the v3 status doc's addenda until the 2026-08-16 SSOT rewrite |
| [BACKLOG.md](BACKLOG.md) | v2 feature backlog |
| [architecture/ASSETS.md](architecture/ASSETS.md) | Asset storage subsystem |
| [architecture/PLUGINS.md](architecture/PLUGINS.md) | Plugin system architecture |
| [design/design_decisions.md](design/design_decisions.md) | v2 design decision log |
| [design/storage_architecture.md](design/storage_architecture.md) | 18-table v2 storage design |
| [integrations/discord_driver_contract.md](integrations/discord_driver_contract.md) | Discord bot driver |
| [plugins/plugin_backlog.md](plugins/plugin_backlog.md) | Plugin ideas backlog |
| [plugins/plugin_contract.md](plugins/plugin_contract.md) | Plugin API contract |
| [plugins/plugin_quickstart.md](plugins/plugin_quickstart.md) | Plugin authoring guide |
| [protocol/stdio_rpc_v1.md](protocol/stdio_rpc_v1.md) | STDIO RPC protocol (24 commands) |
| [runtime/docker_mvp.md](runtime/docker_mvp.md) | v2 3-service Docker deployment |
