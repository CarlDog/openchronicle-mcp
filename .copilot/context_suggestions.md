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

# 🧩 OpenChronicle Core Modules — Expansion TODO (Jul 2025)

This task list focuses on remaining core modules beyond initial LLM routing and style control. These modules handle memory, scenes, search, tokens, and user navigation.

---

## 📌 bookmark_manager.py
- [ ] Add tagging system for bookmarks (plot, clue, twist, emotional)
- [ ] Let bookmarks inherit tone/style snapshot from the scene
- [ ] Create CLI interface to list/jump/create/delete bookmarks

---

## 🧠 memory_manager.py
- [ ] Estimate token cost for memory blobs before context injection
- [ ] Support scoped memory entries (e.g., character-specific, global, world state)
- [ ] Log memory delta between scenes to track world/story evolution

---

## 🗃️ database.py
- [ ] Implement schema version tracking (for future upgrades)
- [ ] Create a migration utility for backward compatibility
- [ ] Add optional per-story size limits or age-based pruning

---

## 📘 scene_logger.py
- [ ] Log generation time per scene for performance auditing
- [ ] Add optional “story arc” and “emotion tag” fields
- [ ] Flag scene records that involve NSFW routing or multi-model stitching

---

## 🔎 search_engine.py
- [ ] Build CLI search tool for power users and devs
- [ ] Support character- vs narrator-perspective filtering
- [ ] Add search analytics: top terms, frequent scenes, overlap with bookmarks

---

## 📦 story_loader.py
- [ ] Add “auto-fix” tool for incomplete or misnamed storypacks
- [ ] Tag storypacks with capabilities (e.g., NSFW-compatible, API-ready)
- [ ] Add import/export pipeline for community or shared storypacks

---

## 🗓️ timeline_builder.py
- [ ] Support grouping by emotional tone or character focus
- [ ] Mark rising/falling action arcs automatically using memory/flag shifts
- [ ] Enable timeline range export (for review, export, publishing)

---

## 📏 token_manager.py
- [ ] Forecast token usage across an arc or chapter (via summaries)
- [ ] Add overflow strategy options (trim memory, model shift, multi-pass)
- [ ] Let users define token budget per story, session, or interaction

---

## 🔁 Cross-module Refactors
- [ ] Connect scene_logger to memory_manager for deeper memory snapshot audits
- [ ] Consider adding a "session UUID" to trace grouped interactions
- [ ] Track memory/token/context for rollback diffs (scene → rollback → scene)
