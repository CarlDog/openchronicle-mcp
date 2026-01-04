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

ALL_TABLES = [PROJECTS_TABLE, AGENTS_TABLE, TASKS_TABLE, EVENTS_TABLE, RESOURCES_TABLE]
