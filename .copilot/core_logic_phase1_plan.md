# 🧠 Core Logic Phase 1 - Memory & Continuity Enhancement

## 🎯 Phase 1 Goals
- Ensure seamless fallback, tone continuity, and prompt formatting across models
- Integrate style and memory handling into timeline, rollback, and search layers
- Harden recovery + storytelling logic under token strain or model transition

## 📋 Implementation Status

### ✅ Prompt Layer - CONFIRMED OPERATIONAL (Polish Later)
- **context_builder.py** → Injects token logic, fallback, style blocks ✔
- **model_adapter.py** → Formats prompts by engine type ✔
- **character_style_manager.py** → Distributes style data to prompt builder ✔

### 🧠 Memory & Continuity - ENHANCEMENT NEEDED

#### 📌 memory_manager.py
- [ ] **Per-character memory snapshots**: Inject character-specific formatting (voice, mood)
- [ ] **Rollback refresh interface**: Add API for refreshing memory after rollback operations

#### 📌 timeline_builder.py
- [ ] **Tone consistency tracking**: Track per-turn tone tags for LLM consistency audit (optional)
- [ ] **Memory compaction**: Generate auto-summaries for long-term memory compaction

#### 📌 scene_logger.py
- [ ] **Structured scene tags**: Add structured tags (mood, scene_type) to logs for model context boosting
- [ ] **Token manager sync**: Sync scene logging with token_manager to flag long-turns

### 🔁 Fallback & Token Handling - SOLID BUT EXPANDABLE

#### 📌 token_manager.py
- [ ] **Token threshold API**: Expose token threshold API for use in scene_logger & timeline_builder
- [ ] **Per-character budgets**: Optionally allow per-character token budgets or alerts

#### 📌 rollback_engine.py
- [ ] **Style re-injection**: Re-parse style block & inject it post-rollback
- [ ] **Memory refresh trigger**: Trigger memory_manager refresh when rollback is invoked
- [ ] **Rollback transparency**: Log rollback origin & reason in scene_logger for transparency

### 📚 Canon/Search/Bookmark - UNTAPPED FOR CONTINUITY

#### 📌 search_engine.py
- [ ] **Canon search fallback**: Integrate canon search fallback into context_builder when tokens are tight
- [ ] **Fuzzy memory injection**: Allow fuzzy memory injection from prior scenes if direct canon isn't found

#### 📌 bookmark_manager.py
- [ ] **Tone override bookmarks**: Allow pinned bookmarks to override fallback tone injection (e.g. "drama pivot")

#### 📌 story_loader.py
- [ ] **Meta.yaml validation**: Validate `meta.yaml` entries: default_model, fallback_chain, style_guide
- [ ] **Style guide loading**: Load and return style data from `style_guide.md` if path present

### 💾 Persistence Layer - OPTIONAL, FUTURE PASS

#### 📌 database.py
- [ ] **Structure integrity**: Add integrity check for required storypack folders & structure
- [ ] **Backup integration**: Add backup hook into rollback_engine.py when a scene is versioned

### 📁 New Feature: Style Re-Injector Utility (PROPOSED)

#### 📌 style_reinjector.py (New Module)
- [ ] **Scene state input**: Accept current scene state and model choice
- [ ] **Style-locked output**: Output style-locked prompt rebuild with fallback continuity

## 🎯 Implementation Priority Order

### Phase 1A - Core Memory Enhancement (Weeks 1-2)
1. **memory_manager.py** - Per-character memory snapshots
2. **rollback_engine.py** - Style re-injection and memory refresh
3. **scene_logger.py** - Structured tags and token sync

### Phase 1B - Integration Layer (Weeks 3-4)
1. **token_manager.py** - Threshold API and character budgets
2. **search_engine.py** - Canon fallback and fuzzy memory
3. **story_loader.py** - Meta.yaml validation and style guide loading

### Phase 1C - Advanced Features (Week 5)
1. **style_reinjector.py** - New utility module
2. **bookmark_manager.py** - Tone override functionality
3. **timeline_builder.py** - Tone tracking and auto-summaries

## 🚀 Success Criteria

### Technical Goals
- [ ] Seamless model transitions without context loss
- [ ] Consistent character voice across different LLM providers
- [ ] Intelligent token management under memory pressure
- [ ] Robust rollback with style and memory preservation

### User Experience Goals
- [ ] Uninterrupted storytelling flow during model fallbacks
- [ ] Consistent narrative tone across sessions
- [ ] Transparent system behavior with clear logging
- [ ] Enhanced story continuity through better memory management

## 🔧 Testing Strategy

### Unit Tests
- [ ] Memory snapshot formatting validation
- [ ] Style re-injection accuracy
- [ ] Token threshold API functionality
- [ ] Rollback integrity with style preservation

### Integration Tests
- [ ] End-to-end fallback scenarios
- [ ] Memory consistency across rollbacks
- [ ] Multi-model style preservation
- [ ] Token pressure handling

### User Acceptance Tests
- [ ] Story continuity during model switches
- [ ] Character voice consistency
- [ ] Rollback transparency and accuracy
- [ ] Memory compaction effectiveness

## 📊 Dependencies

### Internal Dependencies
- Existing `model_adapter.py` fallback system
- `character_style_manager.py` style distribution
- `context_builder.py` prompt assembly
- `database.py` persistence layer

### External Dependencies
- SQLite 3.35+ (already met)
- Python 3.8+ (already met)
- LLM provider APIs (already configured)

## 🎯 Post-Phase 1 Priorities
1. **Publisher-Friendly Export System** - Story export capabilities
2. **Style Override Support** - Session-wide style mode locking
3. **Memory Versioning** - Track memory state changes over time
4. **CLI Time Machine Tooling** - Advanced debugging and story analysis tools
5. **Disk Guardrails** - Resource management for constrained deployments

---

*This document tracks the Core Logic Phase 1 implementation plan for OpenChronicle's memory and continuity enhancement initiative.*
