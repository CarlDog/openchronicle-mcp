# 🎭 Emotional Configuration Schema for Characters

## 📌 Purpose
Enable configurable emotional behaviors at the character level to prevent unwanted gratification loops and allow for deliberate character personalities such as emotionally volatile, needy, or stoic personas. This supports immersion and user agency, while keeping default interactions grounded and varied.

---

## 🧩 Key Goals

- Add `emotional_profile` block to `character.json`
- Support control over emotional volatility, gratification-seeking, boundaries, and repetition
- Prevent characters from falling into needy or repetitive emotional loops *by default*
- Allow power users to override safeguards and build clingy, codependent, or chaotic characters on purpose
- Improve realism by supporting rejection, withdrawal, pride, discomfort, and emotional shifts

---

## 📐 Proposed Schema Extension

```json
"emotional_profile": {
  "volatility": 0.3,               // 0.0 = stoic, 1.0 = emotionally explosive
  "gratification_drive": 0.1,      // 0.0 = self-sufficient, 1.0 = approval-addicted
  "emotional_cooldown": 4,         // number of turns before same emotion can be reused
  "boundaries_enabled": true,      // can character say no or resist advances?
  "needs_attention": false,        // will character seek validation when ignored?
  "loop_protection_enabled": true  // disable to allow repeat patterns (e.g., NSFW indulgence mode)
}
```

---

## 🛠️ Subtasks

- [ ] Add schema support to `schemas/character.json`
- [ ] Update character loader to validate and apply emotional profile fields
- [ ] Implement loop prevention logic based on `gratification_drive` and cooldown timers
- [ ] Modify LLM prompt builder to reflect emotional dynamics
- [ ] Add a config toggle in global settings to enforce minimum loop protection globally
- [ ] Add per-character override that disables all emotional restrictions
- [ ] Write unit test: character with high neediness vs character with stoic profile
- [ ] Create 3 sample emotional profiles: clingy rogue, stoic warrior, flirty healer

---

## 🧪 Testing Notes

- Use verbose logging to confirm emotional state triggers
- Test under interruptive scene conditions (e.g., character is interrupted mid-confession)
- Pair with character interaction goals for full conversational realism

---

## 🔮 Future Enhancements

- Emotional arc planning: characters evolve emotionally over the course of a story
- External triggers: events, betrayals, or trauma adjust volatility and gratification levels dynamically
- Visual tools to preview character emotional profiles