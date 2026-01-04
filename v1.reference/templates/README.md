# 📋 **OpenChronicle Template System Guide**

## **🎯 Overview**

OpenChronicle templates provide flexible, import-adaptable character and scene definitions with granular optional controls. Templates maintain user choice while supporting sophisticated organizational features.

---

## **📂 Template Files**

### **Core Templates:**

- **`character_template.json`** - Comprehensive character profiles with expandable arrays
- **`location_template.json`** - Unified location template for rooms, buildings, regions, or worlds
- **`scene_template.json`** - Scene metadata with optional enhancements
- **`meta_template.json`** - Story metadata and organizational features
- **`style_guide_template.json`** - Writing style and tone guidance
- **`instructions_template.json`** - AI behavior guidance

### **Advanced World-Building Templates (Optional):**

- **`world_template.json`** - Sophisticated world systems (magical geography, calendar, cultures)
- **`narrative_template.json`** - Faction networks and narrative progression mechanics
- **`content_template.json`** - Procedural content generation (creatures, loot, encounters)
- **`chatbot_template.json`** - AI chatbot configuration for single-voice persona management

**Note**: Memory tracking, conversation threading, current state snapshots, and historical event tracking are automatically handled by OpenChronicle's engines (MemoryManager, SceneLogger, CharacterInteractionEngine, TimelineBuilder) and do not require separate templates.

---

## **🔧 Key Features**

### **1. Granular Optional Control**

```json
{
  "required_field": "{{PLACEHOLDER}}",
  "optional_section": {
    "_optional": true,
    "optional_field": {
      "_optional": true,
      "value": "{{PLACEHOLDER}}"
    }
  }
}
```

### **2. Import Adaptability**

- **Expandable Arrays:** All arrays can grow to accommodate unlimited entries
- **Dynamic Relationships:** Supports family, friend, enemy, lover, mentor, rival, etc.
- **Flexible Structure:** Import processes can expand arrays dynamically
- **No Data Truncation:** Template shows minimum structure, not maximum

### **3. Smart Application Processing**

- **Ignores:** Empty strings, null values, unmodified placeholders
- **Processes:** Only fields with actual content
- **Validates:** Required fields must have meaningful values

---

## **📋 Character Template Structure**

### **Required Fields (5):**

- `name` - Character name
- `basic_info.age` - Character age
- `physical_description.hair` - Hair description
- `physical_description.eyes` - Eye description
- `personality.core_traits` - Core personality traits (array)

### **Optional Sections (12):**

1. **`title`** - Character title/role
2. **`basic_info`** - Race, gender, occupation, origin
3. **`physical_description`** - Height, build, clothing
4. **`personality`** - Values, fears, motivations
5. **`background`** - Childhood, education, events, situation
6. **`abilities`** - Skills, magical abilities, weaknesses
7. **`relationships`** - Important people with relationship details
8. **`story_role`** - Importance, arc, scenes, growth
9. **`dialogue_style`** - Speech patterns, vocabulary, characteristics
10. **`character_tier`** - Main/supporting/background classification
11. **`emotional_framework`** - Emotional state, triggers, dynamics
12. **`specialized_details`** - Physical modifications, personal items

---

## **🔄 Import Guidelines**

### **Array Expansion Example:**

```json
// Template provides ONE relationship:
"important_people": [
  {
    "name": "{{PERSON_NAME}}",
    "relationship": "{{RELATIONSHIP_TYPE}}",
    "description": "{{RELATIONSHIP_DESCRIPTION}}"
  }
]

// Import should create MULTIPLE entries:
"important_people": [
  { "name": "Sarah", "relationship": "sister", "description": "Protective of her" },
  { "name": "Marcus", "relationship": "enemy", "description": "Former friend turned rival" },
  { "name": "Elena", "relationship": "lover", "description": "Secret romantic relationship" }
  // ... unlimited relationships
]
```

### **Physical Modifications Scaling:**

```json
// Import supports unlimited modifications:
"physical_modifications": {
  "tattoos": [
    { "location": "Right shoulder", "description": "Celtic knot", "significance": "Family memorial" },
    { "location": "Left wrist", "description": "Infinity symbol", "significance": "Never give up" }
    // ... all tattoos found in source data
  ],
  "scars": [ /* all scars */ ],
  "piercings": [ /* all piercings */ ]
}
```

---

## **💡 Usage Examples**

### **Minimal Character (Required Only):**

```json
{
  "name": "Alexandra Thompson",
  "basic_info": { "age": "25" },
  "physical_description": { "hair": "Brown", "eyes": "Green" },
  "personality": { "core_traits": ["Creative", "Thoughtful", "Independent"] }
}
```

### **Enhanced Character (Optional Features):**

```json
{
  "name": "Marcus Knight",
  "character_tier": { "_optional": true, "value": "main" },
  "relationships": {
    "_optional": true,
    "important_people": [
      { "name": "Elena", "relationship": "lover", "description": "Secret romance" },
      { "name": "Baron Aldric", "relationship": "enemy", "description": "Political rival" }
    ]
  },
  "specialized_details": {
    "_optional": true,
    "physical_modifications": {
      "scars": [
        {
          "location": "Left shoulder",
          "description": "Jagged sword wound",
          "origin_story": "Battle of Ashford Keep",
          "significance": "Reminder of duty"
        }
      ]
    }
  }
}
```

---

## **🎉 Template Philosophy**

**✅ OPTIONAL:** Users decide which features to use - delete unwanted sections
**✅ EXPANDABLE:** Import processes can scale to any character complexity
**✅ CONSISTENT:** Uniform placeholder format and optional field patterns
**✅ STORYTELLING-FOCUSED:** Every field serves narrative development needs

The template system provides comprehensive character development tools while maintaining clean, consistent structure focused entirely on storytelling requirements!
