-- Migration 001: v3 baseline schema.
--
-- Establishes the projects + memory_items + memory_embeddings tables, plus
-- the schema_version table that the migrator uses to track applied migrations.
-- FTS5 virtual tables and triggers are NOT created here — they require
-- runtime feature detection (the SQLite build may lack FTS5) and live in
-- SqliteStore._ensure_fts5().

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER NOT NULL PRIMARY KEY,
    applied_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    metadata   TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_items (
    id         TEXT PRIMARY KEY,
    content    TEXT NOT NULL,
    tags       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    pinned     INTEGER NOT NULL,
    project_id TEXT,
    source     TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id    TEXT PRIMARY KEY,
    embedding    BLOB NOT NULL,
    model        TEXT NOT NULL,
    dimensions   INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memory_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_memory_pinned_created
    ON memory_items (pinned, created_at, id);

CREATE INDEX IF NOT EXISTS idx_memory_project_created
    ON memory_items (project_id, created_at, id);

CREATE INDEX IF NOT EXISTS idx_memory_source
    ON memory_items (source);
