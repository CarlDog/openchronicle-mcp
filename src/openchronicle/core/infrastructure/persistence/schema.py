PROJECTS_TABLE = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

AGENTS_TABLE = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    tags TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent_id TEXT,
    parent_task_id TEXT,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    error_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    task_id TEXT,
    agent_id TEXT,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    prev_hash TEXT,
    hash TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

RESOURCES_TABLE = """
CREATE TABLE IF NOT EXISTS resources (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

SPANS_TABLE = """
CREATE TABLE IF NOT EXISTS spans (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    agent_id TEXT,
    name TEXT NOT NULL,
    start_event_id TEXT,
    end_event_id TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ended_at TEXT,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
"""

# Performance indexes for common queries
INDEXES = [
    # Tasks: optimize project queries with ordering
    "CREATE INDEX IF NOT EXISTS idx_tasks_project_created ON tasks(project_id, created_at, id)",
    # Tasks: optimize parent task lookups (task trees)
    "CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_task_id)",
    # Tasks: optimize status filtering
    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
    # Tasks: optimize updated_at ordering
    "CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at)",
    # Events: optimize task event queries with ordering
    "CREATE INDEX IF NOT EXISTS idx_events_task_created ON events(task_id, created_at, id)",
    # Spans: optimize task span queries with ordering
    "CREATE INDEX IF NOT EXISTS idx_spans_task_created ON spans(task_id, created_at, id)",
]

ALL_TABLES = [PROJECTS_TABLE, AGENTS_TABLE, TASKS_TABLE, EVENTS_TABLE, RESOURCES_TABLE, SPANS_TABLE]
