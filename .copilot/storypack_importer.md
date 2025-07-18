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