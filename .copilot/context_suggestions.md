# 🧠 OpenChronicle Core Modules — Deep Dive TODO (Jul 2025)

This file outlines improvement targets based on review of `core/` modules:
- `content_analyzer.py`
- `model_adapter.py`
- `context_builder.py`
- `character_style_manager.py`
- `rollback_engine.py`

---

## 🧠 content_analyzer.py
- [ ] Add fast-track path for clearly safe content (skip deep analysis)
- [ ] Allow per-model NSFW/complexity score thresholds (from JSON config)
- [ ] (Optional) Add language detection step to support future multi-lingual parsing
- [ ] Track classifier latency and log warning if response exceeds timeout

---

## 🧩 model_adapter.py
- [ ] Add `supports_nsfw` boolean to adapter interface and per-model config
- [ ] Allow token feedback reporting (e.g., return tokens used with response)
- [ ] Add timeout fallback per model (configurable via adapter)
- [ ] Improve async initialization with event-based error handling

---

## 📦 context_builder.py
- [ ] Log canon snippets selected during context compilation
- [ ] Add “audit mode” to return memory, snippets, flags used
- [ ] Let users define context shaping style (e.g. narrative vs RPG vs screenplay)
- [ ] Consider context filter pass using character memory affinity or recent topic match

---

## 🎭 character_style_manager.py
- [ ] Define how consistency score is calculated — basic template or lexical diff?
- [ ] Add support for tone override via style guide flag
- [ ] Store scene-level style snapshots for rollback recovery
- [ ] Log tone inconsistencies between characters during cross-model scenes

---

## ⏪ rollback_engine.py
- [ ] Add CLI interface to list, preview, and restore rollback points
- [ ] Support maximum rollback depth in per-story config
- [ ] Define future ‘bookmark’ feature for non-destructive branches
- [ ] Log all rollback events and scene diffs for traceability

---

## 🔁 Cross-module Suggestions
- [ ] Establish `routing_rules.json` to centralize tone/model/NSFW decision logic
- [ ] Develop fallback chain with retry logic and last-known-good scene protection
- [ ] Pass audit trail across modules for debugging prompt flow and classification
