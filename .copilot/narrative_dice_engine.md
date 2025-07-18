# 🎲 Narrative Dice Engine: Story-Driven Success/Failure System

## 📌 Purpose
Introduce an optional, RPG-style success/failure engine for OpenChronicle. Allow characters to succeed or fail based on die rolls, influenced by stats like intelligence or charisma. Failure should be narratively meaningful and open new branches in the story.

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

- [ ] Create `/engine/modules/resolution.py` with basic roll + modifier logic
- [ ] Add RNG logic with pluggable dice support (`roll_d20()`, `roll_2d10()`)
- [ ] Extend scene engine to support resolution calls with outcomes passed to prompt
- [ ] Add basic `difficulty` field support to scene segments
- [ ] Implement prompt builder logic to narrate failure path or fallback
- [ ] Allow resolution system to influence emotional state (e.g., shame on failure)
- [ ] Create config toggle in storypack config to enable or disable per story

---

## 📚 Example

**Scene Directive**:
```json
"resolution_check": {
  "type": "persuasion",
  "difficulty": 16,
  "stat": "charisma",
  "success_branch": "path-a",
  "failure_branch": "path-b"
}
```

**Character has charisma 4, rolls 12 → 16 → success.**

---

## 🔮 Future Extensions

- Custom resolution tables for social, physical, or magical actions
- Stat advancement on successful or failed attempts
- Style guide integration for tone-appropriate failure outcomes