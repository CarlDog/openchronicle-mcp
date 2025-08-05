# OpenChronicle – Next Steps: Architecture Hardening & Testing Expansion

**Date**: August 5, 2025  
**Author**: [System Evaluation Report]  

---

## ✅ 1. Registry Management – Hardening Actions

| Action                    | Priority | Description                                                                 | Overthinking? |
|--------------------------|----------|-----------------------------------------------------------------------------|---------------|
| Schema Validation        | High     | Add `pydantic` or JSON Schema validation for `model_registry.json`         | No            |
| Auto Backup on Save      | Medium   | Create `.bak` file before registry save to prevent accidental overwrites   | No            |
| Registry Uniqueness Check| Medium   | Ensure unique `model_name` and `id` values for all adapters                 | No            |
| Dynamic Fallback Logic   | Low      | Adjust fallback chains based on real-time performance logs                 | **Maybe**     |

> **Flag:** Dynamic fallback logic might be overkill unless real-time model switching is a goal. Could just log performance now, optimize later.

---

## ✅ 2. Logging System – Visibility & Control

| Action                    | Priority | Description                                                                 | Overthinking? |
|--------------------------|----------|-----------------------------------------------------------------------------|---------------|
| Log Rotation             | High     | Implement `RotatingFileHandler` to cap log file growth                      | No            |
| Add Context Tags         | Medium   | Include story ID, scene ID, adapter name in all log entries                 | No            |
| Standardize Log Levels   | Medium   | Normalize INFO/WARN/ERROR usage across modules                             | No            |
| Real-Time Alerts         | Low      | Stream critical logs to dashboard or Discord webhook                        | **Maybe**     |

> **Flag:** Real-time alerts could complicate the setup. Might be better as a separate utility or post-launch enhancement.

---

## ✅ 3. Startup Health & Resilience

| Action                      | Priority | Description                                                               | Overthinking? |
|----------------------------|----------|---------------------------------------------------------------------------|---------------|
| Database Integrity Check   | High     | Run `PRAGMA integrity_check` on SQLite DBs at startup                     | No            |
| Port Binding Validation    | Medium   | Ensure FastAPI or CLI doesn’t conflict with existing bound ports          | **Maybe**     |
| Config Change Detection    | Medium   | Detect and alert on changes to registry files (file watcher)              | **Maybe**     |

> **Flag:** Port binding checks and config watchers are nice, but could be added after stabilization if issues arise.

---

## ✅ 4. Testing Infrastructure – Coverage & Stability

| Action                      | Priority | Description                                                                 | Overthinking? |
|----------------------------|----------|-----------------------------------------------------------------------------|---------------|
| Test Coverage Reports      | High     | Use `pytest-cov`, aim for >80% coverage on core modules                    | No            |
| Integration Test Expansion | High     | Add tests for: scene generation, memory update, adapter fallback          | No            |
| Mock LLMs for Tests        | Medium   | Use test adapters to isolate model interactions during testing             | No            |
| E2E Session Test           | Medium   | Simulate full user flow from input → output → database write               | No            |
| Performance Benchmarks     | Low      | Add `pytest-benchmark` for scene generation timing                         | **Maybe**     |

> **Flag:** Performance benchmarks are great, but possibly premature unless you're actively chasing slowdowns.

---

## 🟢 Final Top 5 Immediate Actions

1. **Registry Schema Validation**  
2. **Log Rotation + Context Tags**  
3. **Startup Database Health Check**  
4. **Test Coverage & Expansion**  
5. **Mock Adapters for Reliable Testing**

---

## Submission Notes

- Flagged items can be deferred or scoped down without risk
- Immediate actions are low-friction with high impact
- All items respect existing project architecture and dev workflow

