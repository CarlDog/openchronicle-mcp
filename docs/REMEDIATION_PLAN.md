# OpenChronicle Remediation Plan

**Author / Prepared by:** Antigravity (Google DeepMind)
**Date:** 2026-09-18
**Target Repository:** `openchronicle-mcp` (v3 / v4 line)
**Primary Design Document:** [docs/design/0013-codebase-remediation-plan.md](design/0013-codebase-remediation-plan.md)

---

## Overview

This remediation plan synthesizes the findings of the September 2026 deep architectural and code-quality review of OpenChronicle. It outlines concrete technical specifications to address performance bottlenecks, query inefficiencies, edge-case bug risks, and scalability ceilings.

The full design and verification specification is recorded in:
👉 **[Design 0013 — Codebase Remediation and Modernization Plan](design/0013-codebase-remediation-plan.md)**

---

## Summary of Remediation Phases

### Phase 1: High-Priority Correctness & Reliability (P0)

- **Ollama Probe Backoff:** Resolve permanent failure caching in `OllamaEmbeddingAdapter.model_revision()` so transient startup network delays do not invalidate all stored vectors or report 100% space mismatch.
- **SQL Empty Set Guard:** Prevent syntax errors in `SqliteStore.list_embeddings()` when passed empty ID collections.
- **Query Parameter Chunking:** Enforce safe parameter boundaries on `WHERE id IN (...)` clauses to prevent exceeding SQLite variable limits.

### Phase 2: Core Data Access & Latency Optimization (P1)

- **SQL Vector Scope Pushdown:** Push project and tag scoping down into SQL in `list_embeddings()`, eliminating whole-database vector loads into Python memory on scoped searches.
- **Batch Candidate Hydration:** Replace sequential $N+1$ single-row `get_memory()` lookups in semantic search with a batched `get_memories()` query.
- **HTTP Connection Pooling:** Introduce persistent `httpx.Client` session management in `OllamaEmbeddingAdapter` to eliminate per-request TCP and TLS connection renegotiation.
- **Decoupled Rate Limiter Sweeps:** Remove full-client iteration from the hot request dispatch path in `RateLimitMiddleware`.

### Phase 3: Concurrency & Throughput Scaling (P2)

- **SQLite Concurrency Unlocking:** Implement a Reader/Writer connection split to unlock SQLite WAL mode's native concurrent read capability and relieve global `RLock` serialization.
- **Configurable Background Vector Generation:** Provide an option for memory creation mutations to compute embeddings asynchronously rather than blocking client requests.
- **Metric Observation Overhead Tuning:** Sample or streamline lock observation in `_observed_lock` to resolve performance gate overhead.

### Phase 4: Portability & Toolchain Modernization (P3)

- **Runtime Portability:** Standardize exception syntax to allow broadening runtime compatibility to Python 3.12+.
- **Deterministic Build Enforcement:** Enforce frozen `uv.lock` resolution in container builds and CI workflows.
- **Workspace Cleanliness:** Exclude root `.db` artifacts across predecessor directories.

---
*For full technical details, schema considerations, and verification matrices, refer to [Design 0013](design/0013-codebase-remediation-plan.md).*
