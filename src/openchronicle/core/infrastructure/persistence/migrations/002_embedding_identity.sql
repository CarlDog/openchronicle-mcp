-- ADR 0005 (rev 2): composite embedding identity, Phase B.
--
-- Adds the provider half of the embedding-space identity and the
-- content identity to memory_embeddings. The '' defaults are SENTINELS:
-- a row carrying one predates this migration, cannot be trusted to any
-- identity it does not carry (the ratified never-guess rule), and is
-- therefore stale AND search-ineligible until the forced reindex that
-- ships in the same release regenerates it through the normal save
-- path. No app-level backfill happens here on purpose — this runner
-- executes plain SQL with no config access, and no data source records
-- which provider produced a pre-migration vector.
--
-- Idempotency note: SQLite has no ADD COLUMN IF NOT EXISTS. Re-run
-- safety lives in the migrator itself — the schema_version gate skips
-- applied migrations, and the per-migration savepoint rolls back a
-- partial failure — not in these statements.
ALTER TABLE memory_embeddings ADD COLUMN provider TEXT NOT NULL DEFAULT '';
ALTER TABLE memory_embeddings ADD COLUMN content_hash TEXT NOT NULL DEFAULT '';
