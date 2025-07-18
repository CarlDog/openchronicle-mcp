# 📦 Storypack Importer and Auto-Converter Utility

## 📌 Purpose
Help users migrate existing work into OpenChronicle’s storypack format. Accept legacy config files, Markdown scripts, character outlines, and even EPUBs or raw dialogue logs. Parse, organize, and scaffold a compatible `/storypacks/` directory structure with minimal manual effort.

---

## 🛠️ Tasks

- [ ] Create `/tools/importer.py` for core CLI logic
- [ ] Support input types: `.json`, `.yaml`, `.md`, `.txt`, `.epub`
- [ ] Detect and parse character profiles from structured or semi-structured text
- [ ] Attempt to generate:
  - `character.json` files
  - `scene-*.json` files (from Markdown, transcript, etc)
  - `settings.json` for world metadata
  - `style_guide.json` (optional heuristics)
- [ ] Scaffold complete `/storypacks/<name>/` directory with content
- [ ] Mark unresolved or ambiguous entries as `incomplete_*.json` for review
- [ ] Offer CLI confirmations or silent batch mode

---

## 🔍 Optional Features

- EPUB reader with chapter detection
- Use summarization LLM (local or API) for fuzzy character/scene extraction
- Language auto-detection
- Suggest ideal folder name based on story title

---

## 🚀 Future Enhancements

- Web-based drag-and-drop wizard UI
- Import/export converter between OpenChronicle and other formats (Twine, Ink, Scrivener)
# 📦 Storypack Importer and Auto-Converter Utility

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

## 🧩 System Components

```json
"resolution_system": {
  "enabled": true,
  "dice_engine": "d20",
  "modifier_tolerance": 3,
  "skill_dependency": true,
  "failure_narrative_required": true
}
```

- `enabled`: Activates resolution mechanics
- `dice_engine`: RNG base (d6, d20, etc.)
- `modifier_tolerance`: How far stats can sway a roll
- `skill_dependency`: Uses character_stats modifiers (e.g., intelligence, charisma)
- `failure_narrative_required`: Forces authors to provide failed scene branches

---

## 🛠️ Tasks

- [ ] Create `/tools/importer.py` with CLI interface
- [ ] Add input format detection: `.json`, `.yaml`, `.md`, `.txt`, `.epub`
- [ ] Parse character profiles and extract scene structure
- [ ] Use LLM to suggest scene/character mappings and tag emotion arcs
- [ ] Scaffold `/storypacks/<name>/` and write partial or complete files
- [ ] Auto-generate fallback `incomplete_*.json` for unresolved inputs
- [ ] Add toggle for `llm_assistance: true/false` in config
- [ ] Allow user confirmation or overwrite of auto-generated content

---

## 🔮 Future Enhancements

- Web UI wizard for drag-and-drop story building
- Auto-matching of characters with prior entries (de-dupe logic)
- Version-control diff tool for updating storypacks over time
- Seamless export to `.zip`, `.md`, `.epub`, or `.json` bundles