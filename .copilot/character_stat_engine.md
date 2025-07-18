# 🎲 Character Stat Engine (Narrative Trait Framework)

## 📌 Purpose
Add a set of standardized, RPG-style narrative traits to each character — such as intelligence, charisma, courage, and greed — which affect how they think, speak, and act across story scenes. This enables deep emotional realism, more nuanced responses, and dynamic inter-character conflict.

---

## 🧩 Trait Schema (Recommended Defaults)

```json
"character_stats": {
  "intelligence": 7,
  "wisdom": 5,
  "charisma": 6,
  "willpower": 4,
  "creativity": 8,
  "humor": 6,
  "courage": 5,
  "loyalty": 9,
  "greed": 3,
  "temper": 2
}
```

---

## 🛠️ Tasks

- [ ] Extend `/schemas/character.json` to support `character_stats`
- [ ] Update character loader to validate and expose stats internally
- [ ] Update prompt builder to reference stat values for tone/risk/emotion
- [ ] Add conditionals in response planner to reflect stat influence (e.g., greedy character tempted by reward)
- [ ] Create test scene files where stats result in diverging reactions
- [ ] Add optional stat progression mechanic (for user-driven character growth)

---

## 🎭 Use Cases

- A **low-charisma** mage speaks bluntly, without sugarcoating
- A **high-loyalty** knight will defend allies even against their better judgment
- A **low-courage** scribe might run during a crisis, even if they *want* to help
- A **high-humor** rogue under stress cracks jokes while bleeding

---

## 🔮 Future Extensions

- Allow dynamic stat updates across long-form narratives
- Integrate with character memory logs (“Temper increased after betrayal”)
- Visual radar chart for users to preview personality profile