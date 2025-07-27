# Help users migrate existing work into OpenChronicle's storypack format. Accept legacy config files, Markdown scripts, character outlines, and even EPUBs or raw dialogue logs. Parse, organize, and scaffold a compatible `/storage/storypacks/` directory structure with minimal manual effort. Storypack Importer and Auto-Converter Utility

## 📌 Purpose
Help users migrate existing work into OpenChronicle’s storypack format. Accept legacy config files, Markdown scripts, character outlines, and even EPUBs or raw dialogue logs. Parse, organize, and scaffold a compatible `/storypacks/` directory structure with minimal manual effort.

---

## 🧠 LLM Assistance

Leverage local or cloud-based LLMs to enrich the import process:

- 🧠 Summarize prose into scene summaries and timelines
- 🗣️ Detect character voices and split monologues into structured dialogue
- 📘 Extract or infer missing metadata (relationships, tone, genre)
- 📐 Suggest style guide heuristics based on mood/tone/language patterns
- 🛠️ Normalize formats into OpenChronicle-compliant `.json`
- 📤 Fallback to manual-review mode if LLM confidence is low or ambiguous

**LLM Order of Preference**:  
`ollama` (local) → `openchronicle:api` (self-hosted) → `openai:gpt-4` (fallback)

---

## 🧩 Supported Input Types

- `.json` (structured configs, character files)
- `.yaml` (converted config notes)
- `.md` (scene scripts, world lore, or dialog drafts)
- `.txt` (raw notes, plaintext scenes)
- `.epub` (longform books or fanfics)

---

## 🛠️ Tasks

- [ ] Create `/tools/importer.py` with CLI interface
- [ ] Detect file types and extract metadata or relevant content
- [ ] Parse character profiles and world notes into OpenChronicle JSON structure
- [ ] Segment Markdown or text into logical scenes or chapters
- [ ] Use LLM(s) to assist with tagging, extraction, and auto-completion
- [ ] - [ ] Scaffold `/storage/storypacks/<n>/` with:
  - `characters/`
  - `scenes/`
  - `world/`
  - `style_guide.json`
  - `settings.json`
- [ ] Generate fallback files (`incomplete_*.json`) for ambiguous content
- [ ] Allow confirmation/review before saving parsed assets
- [ ] Optional batch mode for power users

---

## 🔮 Future Enhancements

- Web UI wizard for drag-and-drop ingestion
- Fine-tuning import presets for external tools (Twine, Ink, etc.)
- Merge conflict resolution with existing storypacks
- Export mirroring logic for seamless bidirectional conversion