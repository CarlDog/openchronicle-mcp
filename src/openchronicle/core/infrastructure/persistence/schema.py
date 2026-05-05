"""SQLite schema for v3 — projects + memory + embeddings only."""

PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

MEMORY_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    tags TEXT NOT NULL,
    created_at TEXT NOT NULL,
    pinned INTEGER NOT NULL,
    project_id TEXT,
    source TEXT NOT NULL,
    updated_at TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

MEMORY_EMBEDDINGS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_embeddings (
    memory_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    FOREIGN KEY(memory_id) REFERENCES memory_items(id) ON DELETE CASCADE
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_memory_pinned_created ON memory_items(pinned, created_at, id)",
    "CREATE INDEX IF NOT EXISTS idx_memory_project_created ON memory_items(project_id, created_at, id)",
    "CREATE INDEX IF NOT EXISTS idx_memory_source ON memory_items(source)",
]

ALL_TABLES = [
    PROJECTS_TABLE,
    MEMORY_ITEMS_TABLE,
    MEMORY_EMBEDDINGS_TABLE,
]

# FTS5 virtual table + triggers — applied conditionally by
# SqliteStore._ensure_fts5() once FTS5 availability has been probed.

FTS5_TABLES = [
    """CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
        content, tags,
        content='memory_items', content_rowid='rowid'
    )""",
]

FTS5_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS memory_fts_ai AFTER INSERT ON memory_items BEGIN
        INSERT INTO memory_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
    END""",
    """CREATE TRIGGER IF NOT EXISTS memory_fts_ad AFTER DELETE ON memory_items BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content, tags)
            VALUES('delete', old.rowid, old.content, old.tags);
    END""",
    """CREATE TRIGGER IF NOT EXISTS memory_fts_au AFTER UPDATE ON memory_items BEGIN
        INSERT INTO memory_fts(memory_fts, rowid, content, tags)
            VALUES('delete', old.rowid, old.content, old.tags);
        INSERT INTO memory_fts(rowid, content, tags) VALUES (new.rowid, new.content, new.tags);
    END""",
]
