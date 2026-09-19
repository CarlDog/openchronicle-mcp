# 0013 — Codebase Remediation and Modernization Plan

**Status:** PROPOSED · **Date:** 2026-09-18
**Author / Prepared by:** Antigravity (Google DeepMind)
**Target Repository:** `openchronicle-mcp` (OpenChronicle v3 / v4 line)
**Related Documents:** [0005](0005-embedding-identity.md), [0007](0007-long-term-scale-and-resilience.md), [0008](0008-pins-as-ranking-prior.md), [0009](0009-permanent-embed-failure-classification.md), [0010](0010-performance-measurement.md)

---

## 1. Executive Summary & Intent

An in-depth review of the OpenChronicle codebase reveals an engineering foundation with exemplary hygiene:

- AST-enforced hexagonal architectural boundaries (`domain` → `application` → `infrastructure` → `interfaces`).
- Automated zero-secrets and zero-technical-debt verification suites.
- Strict data durability patterns, online backups, and savepoint-atomic migrations.

However, several architectural bottlenecks and subtle edge-case risks limit throughput, latency, and operational resilience under concurrent load. This remediation plan details prioritized, actionable specifications to resolve these inefficiencies.

---

## 2. Phase 1: High-Priority Correctness & Edge-Case Resilience (P0)

### 1.1. Eliminate Permanent Failure Caching in the Ollama Capability Probe

- **Component:** `openchronicle.core.infrastructure.embedding.ollama_adapter.OllamaEmbeddingAdapter`
- **File:** `src/openchronicle/core/infrastructure/embedding/ollama_adapter.py`
- **Problem Analysis:**
  In `model_revision()`, `self._probed_revision` starts as `_UNPROBED`. On the first invocation, `_probe_digest()` queries `/api/tags`. If Ollama is starting up, unreachable, or under initial container initialization, `_probe_digest()` catches the exception and returns `None`. `self._probed_revision` is then set to `None`.
  Because `None` is distinct from `_UNPROBED`, `_probe_digest()` will never be called again. If the database already contains embeddings with recorded manifest digests (`sha256:...`), `stale_embedding_counts()` evaluates `model_revision IS NOT ?` as true for all records, reporting **100% space mismatch**. Semantic search subsequently queries `model_revision IS NULL`, returning zero results.
- **Remediation Specification:**
  1. Do not cache a `None` result permanently on failure.
  2. Record a retry timestamp (`self._probe_failed_at: float | None`) or an exponential backoff interval (e.g. retry after 10 seconds, up to 60 seconds).
  3. Only cache `self._probed_revision` permanently when a valid digest string is obtained or when Ollama explicitly answers 200 OK with the model list missing the tag.

### 1.2. Guard Against Empty Memory ID Syntax Error in `list_embeddings`

- **Component:** `openchronicle.core.infrastructure.persistence.sqlite_store.SqliteStore`
- **File:** `src/openchronicle/core/infrastructure/persistence/sqlite_store.py`
- **Problem Analysis:**
  `list_embeddings()` builds `memory_id IN ({placeholders})`. If an empty sequence (`memory_ids=[]`) is passed, `placeholders` evaluates to `""`, constructing invalid SQL (`WHERE ... AND memory_id IN ()`), which triggers `sqlite3.OperationalError: near ")": syntax error`.
- **Remediation Specification:**
  Add an immediate return guard at the start of `list_embeddings`:

  ```python
  if memory_ids is not None and len(memory_ids) == 0:
      return {}
  ```

### 1.3. Bounded Chunking for SQLite Parameter Limits

- **Component:** `openchronicle.core.infrastructure.persistence.sqlite_store.SqliteStore`
- **File:** `src/openchronicle/core/infrastructure/persistence/sqlite_store.py`
- **Problem Analysis:**
  SQLite enforces `SQLITE_LIMIT_VARIABLE_NUMBER` (typically 999 or 32,766 parameters depending on build). Unbounded parameter expansion in `IN (?, ?, ...)` constructs risks runtime crashes when operating on large memory sets.
- **Remediation Specification:**
  Introduce an internal query helper `_chunked_in_query()` that slices parameter collections into bounded batches of 500 items and unions or combines results.

---

## 3. Phase 2: Query Optimization & Resource Efficiency (P1)

### 2.1. Push Project and Tag Scoping into SQL for Vector Retrieval

- **Component:** `openchronicle.core.application.services.embedding_service.EmbeddingService` & `SqliteStore`
- **Files:**
  - `src/openchronicle/core/application/services/embedding_service.py`
  - `src/openchronicle/core/infrastructure/persistence/sqlite_store.py`
- **Problem Analysis:**
  Currently, `_semantic_search` calls `self._store.list_embeddings(...)` without project or tag constraints, loading all stored vectors across the entire database for the active model into Python memory. In a database of 20,000 memories where a project contains 25 items, all 20,000 vector blobs are unpacked via `struct.unpack`, converted to Python float lists, and stored in a dictionary before Python discards 19,975 of them.
- **Remediation Specification:**
  1. Extend `MemoryStorePort.list_embeddings` to accept optional `project_id: str | None` and `tags: list[str] | None`.
  2. Implement an inner join in `SqliteStore`:

     ```sql
     SELECT e.memory_id, e.embedding
     FROM memory_embeddings e
     JOIN memory_items m ON m.id = e.memory_id
     WHERE e.status = 'ok'
       AND e.model = ?
       AND e.provider = ?
       AND e.dimensions = ?
       AND (m.project_id = ? OR (m.pinned = 1 AND m.project_id IS NULL))
     ```

  3. Leverage SQLite's existing index `idx_memory_project_created` to read only the vector blobs relevant to the query scope.

### 2.2. Batch Candidate Hydration in Semantic Search (Eliminate $N+1$ Queries)

- **Component:** `openchronicle.core.application.services.embedding_service.EmbeddingService`
- **File:** `src/openchronicle/core/application/services/embedding_service.py`
- **Problem Analysis:**
  In `search_hybrid` (lines 671-677) and `search_semantic` (lines 841-852), candidate items not present in the keyword list are fetched one by one via `self._store.get_memory(mid)`. For 20–40 results, this executes 20–40 distinct SQL queries and lock acquisitions.
- **Remediation Specification:**
  1. Add `get_memories(memory_ids: list[str]) -> dict[str, MemoryItem]` to `MemoryStorePort` and `SqliteStore`.
  2. Fetch all missing candidate memories in a single batched SQL query using `WHERE id IN (...)`.

### 2.3. Implement Persistent Connection Pooling in `OllamaEmbeddingAdapter`

- **Component:** `openchronicle.core.infrastructure.embedding.ollama_adapter.OllamaEmbeddingAdapter`
- **File:** `src/openchronicle/core/infrastructure/embedding/ollama_adapter.py`
- **Problem Analysis:**
  Every call to `embed_batch` uses `httpx.post(...)` directly, creating and destroying a new TCP socket and performing a TLS handshake on each chunk. Under batch backfills or continuous search queries, this causes socket churn and avoidable latency.
- **Remediation Specification:**
  1. Initialize `self._client = httpx.Client(timeout=self._timeout, verify=self._verify_tls)` in `__init__`.
  2. Use `self._client.post(...)` for embedding requests.
  3. Provide a `close()` lifecycle method connected to container teardown.

### 2.4. Decouple Idle Client Sweeping in Rate Limiter Middleware

- **Component:** `openchronicle.interfaces.api.middleware.rate_limit.RateLimitMiddleware`
- **File:** `src/openchronicle/interfaces/api/middleware/rate_limit.py`
- **Problem Analysis:**
  On every single incoming HTTP request, the middleware iterates through every tracked client IP in `self._requests` inside `with self._lock:` to prune expired timestamps. Under diverse client IP distributions, this turns an $O(1)$ lookup into an $O(N)$ scan held under a thread lock.
- **Remediation Specification:**
  Prune only the active `client_ip` during request dispatch. Run a full dictionary expiration sweep only periodically (e.g. once every 60 seconds) or when `len(self._requests)` exceeds a designated threshold.

---

## 4. Phase 3: Concurrency & Throughput Scaling (P2)

### 3.1. SQLite Reader/Writer Connection Concurrency Split

- **Component:** `openchronicle.core.infrastructure.persistence.sqlite_store.SqliteStore`
- **File:** `src/openchronicle/core/infrastructure/persistence/sqlite_store.py`
- **Problem Analysis:**
  `SqliteStore` uses a single `sqlite3.Connection` behind a `threading.RLock()`. SQLite WAL mode natively supports concurrent readers alongside a writer. Process-level serialization in Python eliminates this capability, creating artificial head-of-line blocking.
- **Remediation Specification:**
  1. Separate read operations from mutating operations.
  2. Maintain a single dedicated writer connection protected by a write lock for `INSERT`, `UPDATE`, `DELETE`, and `BEGIN IMMEDIATE`.
  3. Maintain thread-local read-only connections (`PRAGMA query_only = ON;`) for select queries (`get_memory`, `list_memory`, `search_memory`, `count_memory`).
  4. Allow read queries to execute concurrently across threads without blocking on long-running operations.

### 3.2. Configurable Background Embedding for Memory Mutations

- **Component:** `openchronicle.core.application.use_cases.add_memory`
- **Files:**
  - `src/openchronicle/core/application/use_cases/add_memory.py`
  - `src/openchronicle/interfaces/mcp/tools/memory.py`
  - `src/openchronicle/interfaces/api/routes/memory.py`
- **Problem Analysis:**
  `add_memory.execute` calls `embedding_service.generate_for_memory(...)` synchronously. When using local inference (Ollama), cold model loads can stall the calling agent for 5–30 seconds.
- **Remediation Specification:**
  1. Add an optional parameter `background_embed: bool = False` to `memory_save`.
  2. When enabled, persist the memory record immediately (making it instantly FTS5-searchable) and schedule vector generation asynchronously, allowing interactive tools to respond immediately.

### 3.3. Reduce Overhead in Metric Instrumentation

- **Component:** `openchronicle.core.infrastructure.persistence.sqlite_store._observed_lock`
- **File:** `src/openchronicle/core/infrastructure/persistence/sqlite_store.py`
- **Problem Analysis:**
  Profiling evidence in [0010-4c-attribution.md](0010-4c-attribution.md) revealed that lock observation accounted for over 56% of recording CPU time in isolated cycles. Wrapping every store read method causes significant measurement overhead.
- **Remediation Specification:**
  Sample lock hold duration only on transaction boundaries and long-running operations rather than every individual read query, unblocking the performance gate for runtime metrics.

---

## 5. Phase 4: Portability & Toolchain Hygiene (P3)

### 4.1. Re-Evaluate Python Runtime Floor

- **Observation:** `pyproject.toml` requires `python >= 3.14` solely for minor PEP 758 syntax conveniences (`except A, B:` without parentheses).
- **Remediation:** Standardizing exception syntax to `except (A, B):` would allow lowering the floor to Python `>= 3.12` or `>= 3.13`, dramatically increasing operational compatibility on standard Linux LTS distributions, TrueNAS, and Synology DSM environments.

### 4.2. Enforce Deterministic Lockfile Consumption

- **Observation:** `uv.lock` is present in the repository but CI and Docker installations resolve from `pyproject.toml`.
- **Remediation:** Configure Docker and CI test workflows to install directly from `uv.lock` using `uv sync --frozen`, ensuring fully reproducible builds and eliminating exposure to unpinned transitive dependency updates.

### 4.3. Workspace Repository Hygiene

- **Observation:** Predecessor repositories (`openchronicle-core` and `openchronicle-plugins`) contain orphaned local artifacts (such as an untracked 2.85MB `test.db` in `openchronicle-core`).
- **Remediation:** Ensure local `.gitignore` configurations exclude `*.db` at repository roots and clearly document repository status in developer navigation.

---

## 6. Implementation & Verification Matrix

| Step | Item | Files Affected | Verification Criterion |
| :--- | :--- | :--- | :--- |
| **1.1** | Ollama Probe Backoff | `ollama_adapter.py` | Unit test simulating initial connection error followed by successful probe; assert `model_revision` recovers and does not report 100% stale embeddings. |
| **1.2** | Empty ID List Guard | `sqlite_store.py` | `test_list_embeddings_empty_ids()` passes without SQLite syntax error. |
| **1.3** | Parameter Chunking | `sqlite_store.py` | Querying >1,000 IDs succeeds without `too many SQL variables`. |
| **2.1** | SQL Vector Scope Join | `embedding_service.py`, `sqlite_store.py` | Benchmarked memory allocation during project-scoped search on multi-project database shows proportional reduction. |
| **2.2** | Batch Candidate Hydration | `embedding_service.py`, `sqlite_store.py` | Query counter test verifies single query for semantic candidate hydration. |
| **2.3** | Persistent HTTP Client | `ollama_adapter.py` | Assert single `httpx.Client` instance reused across multiple batch embeddings. |
| **2.4** | Rate Limiter Pruning | `rate_limit.py` | Micro-benchmark shows $O(1)$ dispatch time independent of total client count. |
| **3.1** | Reader/Writer Split | `sqlite_store.py` | Concurrent read test executes while a write transaction is in progress without blocking. |
| **3.2** | Background Vector Embedding | `add_memory.py`, `memory.py`, `embedding_service.py` | Async vector generation scheduled in background with immediate memory persistence. |
| **3.3** | Metric Overhead Reduction | `sqlite_store.py` | Thread-local readers bypass writer lock observation on disk databases. |
| **4.1** | Python Runtime Compatibility | `pyproject.toml`, codebase | Exception syntax standardized to `except (A, B):`, enabling Python >=3.12 support. |
| **4.2** | Deterministic Lockfile Builds | `Dockerfile`, `test.yml`, `uv.lock` | Enforce `uv sync --frozen` across Dockerfile builder and CI workflows. |
| **4.3** | Repository Hygiene | `.gitignore`, test suites | Enforced zero-tolerance checks for prohibited debt tokens and unmocked clocks. |
