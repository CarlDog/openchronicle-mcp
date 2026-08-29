-- ADR 0005, Phase C half of the space identity: provider revision and
-- the settings fingerprint.
--
-- model_revision is NULLABLE — most providers have no revision (OpenAI,
-- stub); Ollama supplies a manifest digest when its probe can. Every
-- predicate over it MUST use IS / COALESCE matching, never `=`:
-- `model_revision = NULL` matches zero rows, which would blank semantic
-- search on the default NULL-revision deployment (the worst defect the
-- adversarial review found in ADR 0005 rev 1).
--
-- settings_fingerprint '' is a SENTINEL, same contract as migration
-- 002's: the row predates the field, is stale and search-ineligible,
-- and is retired by the same single reindex (002 and 003 ship in one
-- release, so there is one reindex, not two).
ALTER TABLE memory_embeddings ADD COLUMN model_revision TEXT NULL;
ALTER TABLE memory_embeddings ADD COLUMN settings_fingerprint TEXT NOT NULL DEFAULT '';
