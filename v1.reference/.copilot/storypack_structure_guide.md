# OpenChronicle Storypack Structure Guide

## Overview

OpenChronicle storypacks use an optimized structure that balances organization with usability. The design prioritizes individual files for maximum flexibility while keeping core configuration easily accessible.

## Directory Structure

```
storypack_name/
├── meta.json              # Core storypack metadata (REQUIRED)
├── README.md              # User documentation (AUTO-GENERATED)
├── style_guide.json       # Writing guidelines (OPTIONAL)
├── instructions.json      # AI behavior instructions (OPTIONAL)
├── content.json          # Item catalogs and generated content (OPTIONAL)
├── characters/           # Individual character files
│   ├── hero.json
│   ├── villain.json
│   └── README.md         # Directory documentation
├── locations/            # Individual location files
│   ├── tavern.json
│   ├── castle.json
│   └── README.md
├── lore/                 # World-building and items
│   ├── magic_system.json
│   ├── ancient_history.json
│   ├── legendary_weapons.json  # ← Items go here
│   └── README.md
└── narrative/            # Story structure (CREATED ON DEMAND)
    ├── main_plot.json
    ├── character_arcs.json
    └── README.md
```

## Design Principles

### 1. Root Configuration Pattern

- **Core files stay at root**: Essential configuration and documentation
- **Quick access**: User immediately sees meta.json, README.md, style_guide.json
- **No hunting**: All management functions accessible without navigation

### 2. Individual Files for Content

- **One element per file**: Each character, location, or lore element gets its own JSON file
- **Maximum flexibility**: Edit one character without affecting others
- **Git-friendly**: Clean diffs and collaboration-ready
- **Discoverable**: File explorer browsing reveals content structure

### 3. Semantic Organization

- **characters/**: People, beings, entities in the story
- **locations/**: Places, buildings, geographical areas
- **lore/**: World-building, magic systems, cultures, **items and artifacts**
- **narrative/**: Plot structure, acts, scenes, story progression

## Content Categorization Rules

### Characters

- **Individual files**: One JSON per character
- **Template**: character_template.json
- **Naming**: Descriptive names like `sarah_chen.json`, `dark_lord.json`
- **Content**: Personality, background, relationships, development arcs

### Locations

- **Individual files**: One JSON per significant location
- **Template**: location_template.json
- **Naming**: Clear identifiers like `tavern.json`, `castle_throne_room.json`
- **Content**: Atmosphere, features, story connections

### Lore (Including Items)

- **Individual files**: One JSON per world-building element
- **Templates**: world_template.json, content_template.json
- **Items placement**: **All significant items go in lore/**
- **Examples**:
  - `magic_system.json` - How magic works
  - `ancient_history.json` - Historical events
  - `legendary_weapons.json` - Important weapons and artifacts
  - `royal_bloodlines.json` - Family histories
  - `religious_orders.json` - Organizations and cults

### Narrative

- **Created on demand**: Only if story structure content is discovered
- **Templates**: narrative_template.json, scene_template.json
- **Examples**: `main_plot.json`, `character_arcs.json`, `act_1_setup.json`

## Item Classification System

### Where Items Belong

#### Legendary/Significant Items → `lore/`

```json
// lore/excalibur.json
{
  "name": "Excalibur",
  "type": "Legendary Sword",
  "description": "The sword of kings, forged in dragon fire",
  "special_properties": ["Unbreakable", "Glows near evil", "Chooses worthy wielder"],
  "history": "Pulled from the stone by Arthur..."
}
```

#### Personal Items → Referenced in character files

```json
// characters/arthur.json
{
  "name": "King Arthur",
  "personal_items": [
    {
      "name": "Excalibur",
      "significance": "Primary weapon and symbol of kingship",
      "lore_reference": "lore/excalibur.json"
    }
  ]
}
```

#### Location Items → Part of location descriptions

```json
// locations/round_table.json
{
  "location_name": "Round Table Chamber",
  "notable_features": [
    "The Round Table itself - seat of equality",
    "Siege Perilous - the dangerous seat"
  ]
}
```

### Item Categories in Lore

- **legendary_weapons.json**: Swords, artifacts, magical items of renown
- **magical_artifacts.json**: Enchanted objects, relics, cursed items
- **cultural_items.json**: Significant objects tied to cultures/traditions
- **technological_items.json**: Important devices, inventions, tools

## Importer Behavior

### Directory Creation Logic

1. **Always created**: characters/, locations/, lore/
2. **Created on demand**: narrative/ (only if narrative content discovered)
3. **Root files**: meta.json (always), README.md (auto-generated)
4. **Optional configs**: style_guide.json, instructions.json (created when relevant)

### Content Discovery and Sorting

```python
# Current content categories recognized by importer
content_categories = {
    'characters': ['character', 'person', 'hero', 'villain', 'npc'],
    'locations': ['location', 'place', 'city', 'castle', 'room'],
    'lore': ['lore', 'world', 'magic', 'history', 'culture', 'item', 'artifact', 'weapon'],
    'narrative': ['story', 'plot', 'scene', 'chapter', 'act']
}
```

### File Processing Rules

1. **Directory-based categorization**: Source file's parent directory name influences category
2. **Filename keyword matching**: File names containing category keywords are sorted appropriately
3. **Content analysis**: AI analysis can override directory-based categorization
4. **Default handling**: Uncategorized content goes to most appropriate category or creates new files

## Template Integration

### Template Mapping

- **meta.json**: meta_template.json
- **characters/*.json**: character_template.json
- **locations/*.json**: location_template.json
- **lore/*.json**: world_template.json OR content_template.json
- **narrative/*.json**: narrative_template.json OR scene_template.json
- **style_guide.json**: style_guide_template.json
- **instructions.json**: instructions_template.json

### Content Template for Items

```json
// Using content_template.json structure for items
{
  "items": {
    "rare_items": [
      {
        "name": "The Sword of Instant Death",
        "type": "Cursed Weapon",
        "description": "A blade that kills with one strike",
        "special_properties": [
          "Instant death on successful hit",
          "Corrupts wielder over time"
        ],
        "history": "Forged by dark magic in ancient times..."
      }
    ]
  }
}
```

## User Workflow

### Creating New Content

1. **Characters**: Add `new_character.json` to `characters/`
2. **Locations**: Add `new_location.json` to `locations/`
3. **Items/Lore**: Add `new_element.json` to `lore/`
4. **Story Structure**: Add files to `narrative/` (create directory if needed)

### Managing Items

1. **Legendary items**: Create in `lore/` with full details
2. **Reference in characters**: Add to character's `personal_items` array
3. **Location features**: Include in location's `notable_features`
4. **Plot elements**: Reference in narrative files

### Configuration

1. **Story metadata**: Edit `meta.json`
2. **Writing style**: Edit `style_guide.json`
3. **AI behavior**: Edit `instructions.json`
4. **Generated content**: Review `content.json`

## Migration from Old Structure

### Legacy Structure (demo-story)

```
demo-story/
├── meta.json
├── characters/
│   ├── kira_brightwell.json
├── canon/
│   ├── locations.json    # Consolidated file
│   └── timeline.json
└── memory/
    └── relationships.json
```

### New Optimized Structure

```
demo-story/
├── meta.json
├── README.md
├── characters/
│   ├── kira_brightwell.json
├── locations/           # Individual files
│   ├── brightwell_manor.json
│   ├── market_square.json
├── lore/
│   ├── family_histories.json
│   ├── magical_artifacts.json
└── narrative/
    ├── timeline.json
    ├── main_plot.json
```

## Best Practices

### File Naming

- **Descriptive**: `sarah_the_healer.json` not `character1.json`
- **Consistent**: Use underscores, lowercase
- **Logical**: Group related items with prefixes (`magic_sword.json`, `magic_staff.json`)

### Content Organization

- **Start simple**: Begin with characters and locations
- **Add detail gradually**: Expand lore and narrative as story develops
- **Cross-reference**: Use consistent naming to reference between files
- **Template compliance**: Follow OpenChronicle templates for compatibility

### Items and Artifacts

- **Significance test**: If it has a name and backstory, it belongs in `lore/`
- **Personal items**: Reference significant items in character files
- **Catalog approach**: Group similar items in themed files
- **Rich descriptions**: Include history, properties, and story connections

This structure provides maximum flexibility while maintaining clear organization and seamless integration with OpenChronicle's narrative AI engine.
