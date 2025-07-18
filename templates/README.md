# OpenChronicle Templates System

The templates system provides standardized JSON templates for creating new storypacks with consistent structure and format. All templates use placeholder values that can be customized for each story.

## 📁 Expected Storypack Structure

Every storypack should follow this directory structure:

```
storypacks/
└── your-story-name/
    ├── meta.json                 # Story metadata (required)
    ├── style_guide.json          # Writing guidelines (required)
    ├── canon/                    # World-building files (required)
    │   ├── locations.json        # Locations and geography
    │   ├── history.json          # Historical events and lore
    │   └── [other_canon].json    # Additional canon files as needed
    ├── characters/               # Character definitions (required)
    │   ├── character1.json       # Individual character files
    │   ├── character2.json       # Follow character_template.json format
    │   └── character3.json       # All characters in JSON format
    └── memory/                   # Memory system files (required)
        └── current_state.json    # Current story state
```

## 🎯 Available Templates

### Core Templates
- **`meta_template.json`** - Story metadata and configuration
- **`style_guide_template.json`** - Writing guidelines and character voice rules
- **`character_template.json`** - Individual character definition format
- **`current_state_template.json`** - Story memory state template

### Canon Templates  
- **`locations_template.json`** - Locations and world geography
- **`history_template.json`** - Historical events and world lore

### Reference Templates
- **`memory_templates.json`** - Comprehensive memory system examples and patterns

## 🚀 Using Templates

### 1. Create Storypack Directory Structure
```bash
mkdir -p storypacks/my-story/{canon,characters,memory}
```

### 2. Copy and Customize Templates
```bash
# Copy core templates
cp templates/meta_template.json storypacks/my-story/meta.json
cp templates/style_guide_template.json storypacks/my-story/style_guide.json
cp templates/current_state_template.json storypacks/my-story/memory/current_state.json

# Copy canon templates
cp templates/locations_template.json storypacks/my-story/canon/locations.json
cp templates/history_template.json storypacks/my-story/canon/history.json

# Copy character template for each character
cp templates/character_template.json storypacks/my-story/characters/protagonist.json
cp templates/character_template.json storypacks/my-story/characters/mentor.json
```

### 3. Edit Template Files
Replace all `{{PLACEHOLDER}}` values with your actual content:
- `{{STORY_NAME}}` - Your story's internal name
- `{{STORY_TITLE}}` - Display title
- `{{CHARACTER_NAME}}` - Character names
- `{{LOCATION_NAME}}` - Location names
- And many more...

### 4. Validate Your Storypack
```bash
python -c "from core.story_loader import load_storypack; print('✅ Success!' if load_storypack('my-story') else '❌ Failed')"
```

## 📋 Template Placeholder Conventions

### Naming Pattern
- `{{UPPERCASE_WITH_UNDERSCORES}}` for all placeholders
- Descriptive names that indicate the expected content
- Numbered variants: `{{CHARACTER_1}}`, `{{CHARACTER_2}}`, etc.

### Common Placeholders
- **Story Level:** `{{STORY_NAME}}`, `{{STORY_TITLE}}`, `{{AUTHOR_NAME}}`
- **Characters:** `{{CHARACTER_NAME}}`, `{{CHARACTER_TITLE}}`, `{{PERSONALITY_TRAIT}}`
- **Locations:** `{{LOCATION_NAME}}`, `{{LOCATION_TYPE}}`, `{{LOCATION_DESCRIPTION}}`
- **Dates:** `{{CREATION_DATE}}`, `{{LAST_MODIFIED_DATE}}`

## ✅ Requirements

### File Format Requirements
- **All files must be valid JSON** - No YAML, TXT, or other formats
- **UTF-8 encoding** for all text files
- **Consistent naming** using lowercase with underscores

### Required Files
Every storypack must include:
1. `meta.json` - Story metadata
2. `style_guide.json` - Writing guidelines  
3. At least one file in `canon/` directory
4. At least one file in `characters/` directory
5. `memory/current_state.json` - Initial memory state

### Content Requirements
- **100% original content** - No copyrighted material
- **Appropriate for target audience** - Follow content guidelines
- **Complete character definitions** - Include all required character fields
- **Consistent world-building** - Maintain internal consistency

## 🧪 Testing and Validation

### Quick Validation
```bash
# Test story loading
python -c "from core.story_loader import list_storypacks, load_storypack; print('Available:', list_storypacks()); load_storypack('your-story')"

# Test character loading
python -c "from core.character_style_manager import CharacterStyleManager; csm = CharacterStyleManager(); print('Characters:', csm.load_character_styles('storypacks/your-story'))"

# Test canon loading  
python -c "from core.context_builder import load_canon_snippets; print('Canon files:', len(load_canon_snippets('storypacks/your-story')))"
```

### Common Issues
- **Missing required fields** - Check template completeness
- **Invalid JSON syntax** - Validate JSON formatting
- **Placeholder not replaced** - Search for remaining `{{}}` patterns
- **File encoding issues** - Ensure UTF-8 encoding

## 📚 Example

See `storypacks/demo-story/` for a complete, working example that follows all these conventions.

## 🎨 Best Practices

### Organization
- Use descriptive filenames for canon files
- Name character files after the character
- Keep related canon information in separate files

### Content Quality
- Write complete character backstories
- Create rich, detailed world-building
- Maintain consistent tone and style
- Include character growth arcs

### Maintenance
- Update templates when adding new features
- Keep placeholder names descriptive
- Document any custom fields or extensions
- Test templates with multiple story types
