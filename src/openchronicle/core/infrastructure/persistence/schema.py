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

LLM_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS llm_usage (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    project_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    agent_id TEXT,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    request_id TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    latency_ms INTEGER,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
"""

CONVERSATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

TURNS_TABLE = """
CREATE TABLE IF NOT EXISTS turns (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    user_text TEXT NOT NULL,
    assistant_text TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    routing_reasons TEXT NOT NULL,
    memory_written_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
);
"""

MEMORY_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS memory_items (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    tags TEXT NOT NULL,
    created_at TEXT NOT NULL,
    pinned INTEGER NOT NULL,
    conversation_id TEXT,
    project_id TEXT,
    source TEXT NOT NULL,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

# Performance indexes for common queries

SCHEDULED_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    task_payload TEXT NOT NULL,
    status TEXT NOT NULL,
    next_due_at TEXT NOT NULL,
    interval_seconds INTEGER,
    cron_expr TEXT,
    fire_count INTEGER NOT NULL DEFAULT 0,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    max_failures INTEGER NOT NULL DEFAULT 0,
    last_fired_at TEXT,
    last_task_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
"""

MCP_TOOL_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS mcp_tool_usage (
    id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    started_at TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    success INTEGER NOT NULL,
    error_type TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL
);
"""

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
    # LLM Usage: optimize project queries with ordering
    "CREATE INDEX IF NOT EXISTS idx_llm_usage_project_created ON llm_usage(project_id, created_at, id)",
    # LLM Usage: optimize task queries with ordering
    "CREATE INDEX IF NOT EXISTS idx_llm_usage_task_created ON llm_usage(task_id, created_at, id)",
    # LLM Usage: optimize agent queries with ordering
    "CREATE INDEX IF NOT EXISTS idx_llm_usage_agent_created ON llm_usage(agent_id, created_at, id)",
    # Conversations: optimize created ordering
    "CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at, id)",
    # Turns: optimize conversation ordering
    "CREATE INDEX IF NOT EXISTS idx_turns_conversation_order ON turns(conversation_id, turn_index, id)",
    # Turns: prevent duplicate turn_index within a conversation
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_turns_conversation_turn_index ON turns(conversation_id, turn_index)",
    # Memory: optimize pinned ordering
    "CREATE INDEX IF NOT EXISTS idx_memory_pinned_created ON memory_items(pinned, created_at, id)",
    # Memory: optimize conversation ordering
    "CREATE INDEX IF NOT EXISTS idx_memory_convo_created ON memory_items(conversation_id, created_at, id)",
    # Memory: optimize project ordering
    "CREATE INDEX IF NOT EXISTS idx_memory_project_created ON memory_items(project_id, created_at, id)",
    # Scheduled jobs: optimize tick query (find due active jobs)
    "CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_due ON scheduled_jobs(status, next_due_at, created_at, id)",
    # Scheduled jobs: optimize project listing
    "CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_project ON scheduled_jobs(project_id, created_at, id)",
    # MCP tool usage: optimize tool_name + time queries
    "CREATE INDEX IF NOT EXISTS idx_mcp_tool_usage_tool_created ON mcp_tool_usage(tool_name, created_at, id)",
    # MCP tool usage: optimize time-range queries
    "CREATE INDEX IF NOT EXISTS idx_mcp_tool_usage_created ON mcp_tool_usage(created_at, id)",
]

ALL_TABLES = [
    PROJECTS_TABLE,
    AGENTS_TABLE,
    TASKS_TABLE,
    EVENTS_TABLE,
    RESOURCES_TABLE,
    SPANS_TABLE,
    LLM_USAGE_TABLE,
    CONVERSATIONS_TABLE,
    TURNS_TABLE,
    MEMORY_ITEMS_TABLE,
    SCHEDULED_JOBS_TABLE,
    MCP_TOOL_USAGE_TABLE,
]
