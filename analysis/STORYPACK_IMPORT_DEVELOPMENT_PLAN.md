# OpenChronicle Storypack Import Utility - Development Plan

## Project Overview
**Goal**: Create an AI-powered utility that transforms raw source material into structured OpenChronicle storypacks using templates and LLM analysis.

**Flow**: `analysis/` (source data) → [LLM Processing] → `templates/` (structure) → `storage/storypacks/` (output)

## Architecture Design

### Core Components

1. **Import Engine** (`utilities/storypack_importer.py`)
   - Main orchestration class
   - File discovery and preprocessing
   - Template management
   - Output generation

2. **Content Analysis Integration** (use existing `core/content_analyzer.py`)
   - Leverage existing LLM-powered content extraction
   - Extend with import-specific analysis methods
   - Use existing ModelManager integration
   - Reuse content categorization capabilities

3. **Template Processor** (`utilities/template_processor.py`)
   - Template loading and validation
   - Dynamic field population
   - Cross-reference generation
   - Output formatting

4. **Import CLI** (`utilities/import_cli.py`)
   - Command-line interface
   - Progress reporting
   - Validation and error handling
   - User interaction

### File Structure
```
utilities/
├── storypack_importer.py     # Main import engine
├── template_processor.py     # Template management
└── import_cli.py             # CLI interface

core/
└── content_analyzer.py       # Existing AI content analysis (reuse)

analysis/
├── import_staging/           # Organized import workspace
│   ├── characters/           # Character source files
│   ├── locations/            # Location descriptions
│   ├── lore/                 # World-building content
│   └── narrative/            # Story content
└── [existing analysis files]

storage/storypacks/
└── [generated storypacks]
```

## Development Phases

### Phase 1: Foundation (Session 1) ✅ COMPLETED
- [x] Create basic import engine structure
- [x] Implement template loading system
- [x] Set up ModelManager integration
- [x] Create simple file discovery

### Phase 2: AI Integration (Session 1-2) ✅ COMPLETED
- [x] Integrate existing content_analyzer.py with import engine
- [x] Create import-specific analysis prompts for character extraction
- [x] Extend analysis for location/world-building parsing
- [x] Add metadata generation capabilities to existing analyzer
- [x] Fix logging integration with proper parameter signatures
- [x] Test AI import pipeline with sample data

### Phase 3: Template Processing (Session 2)
- [ ] Dynamic template population
- [ ] Cross-reference generation
- [ ] Validation and error handling
- [ ] Output formatting

### Phase 4: CLI & User Experience (Session 2-3)
- [ ] Command-line interface
- [ ] Progress reporting
- [ ] Interactive mode
- [ ] Batch processing

### Phase 5: Testing & Refinement (Session 3)
- [ ] Test with sample data
- [ ] Error handling improvements
- [ ] Performance optimization
- [ ] Documentation

## Technical Specifications

### LLM Integration Points

**Character Extraction**:
```
Prompt: "Extract character information from this text. Return JSON with name, description, personality, relationships, and key traits."
```

**Location Analysis**:
```
Prompt: "Identify locations mentioned in this content. Extract descriptions, significance, and connections to other elements."
```

**Metadata Generation**:
```
Prompt: "Analyze this story content and suggest appropriate genre, tone, themes, and target audience."
```

### Template Mapping Strategy

**Template Priority**:
1. `meta_template.json` - Story metadata and configuration
2. `character_template.json` - Character profiles
3. `location_template.json` - World locations
4. `world_template.json` - Lore and world-building
5. `narrative_template.json` - Story structure
6. `style_guide_template.json` - Writing guidelines

**Field Population Logic**:
- Required fields: Must be populated or prompt user
- Optional fields: Auto-populate if data available, skip if not
- Cross-references: Generate based on content relationships

### Error Handling & Fallbacks

**LLM Unavailable**:
- Fall back to pattern matching and keyword extraction
- Provide manual data entry prompts
- Use template defaults where appropriate

**Malformed Source Data**:
- Attempt multiple parsing strategies
- Provide clear error messages
- Allow partial imports with warnings

**Template Issues**:
- Validate templates before processing
- Handle missing template fields gracefully
- Log template-related errors

## Implementation Guidelines

### Code Quality Standards
- Follow OpenChronicle coding conventions
- Use centralized logging system (`utilities/logging_system.py`)
- Implement proper error handling
- Add comprehensive docstrings

### ModelManager Integration
- Always check adapter availability before use
- Use fallback chains for resilience
- Log all LLM interactions
- Handle API timeouts gracefully

### File Operations
- Use Path objects for cross-platform compatibility
- Implement atomic file operations
- Create backups before overwriting
- Validate file formats before processing

### Testing Strategy
- Unit tests for individual components
- Integration tests with sample data
- Error condition testing
- Performance benchmarking

## Sample Data for Testing

### Create Test Content in `analysis/import_staging/`

**Character Sample** (`characters/sample_character.txt`):
```
Sir Marcus Thorne is a veteran knight of the Silver Order. At 45 years old, he bears the scars of countless battles but maintains an unwavering sense of honor. His sword, Dawnbreaker, was forged from meteoric steel and glows with a faint blue light. Marcus is known for his dry wit and protective nature toward younger knights.
```

**Location Sample** (`locations/sample_location.txt`):
```
The Whispering Woods stretch for miles north of Silverdale. Ancient oaks tower overhead, their branches forming a canopy so thick that sunlight barely touches the forest floor. Travelers report hearing voices in the wind, leading to local legends of spirits trapped within the trees. A hidden shrine to the old gods lies at the forest's heart.
```

**Lore Sample** (`lore/sample_lore.txt`):
```
The War of Broken Crowns lasted seven years and ended the Third Age. Three kingdoms fought for control of the Eternal Flame, a magical artifact said to grant immortality to its wielder. The war ended when the Flame was shattered, its pieces scattered across the realm. This event marked the beginning of the current Age of Shadows.
```

## Success Criteria

### Minimum Viable Product (MVP)
- [ ] Successfully import basic character data
- [ ] Generate valid storypack structure
- [ ] Integrate with at least one LLM adapter
- [ ] Provide CLI interface
- [ ] Handle common error conditions

### Enhanced Version
- [ ] Support multiple content types (characters, locations, lore)
- [ ] Advanced cross-reference generation
- [ ] Interactive import wizard
- [ ] Batch processing capabilities
- [ ] Comprehensive validation and error reporting

### Advanced Features (Future)
- [ ] Web-based import interface
- [ ] Multiple source format support (PDF, DOCX, etc.)
- [ ] Import from external sources (wikis, APIs)
- [ ] AI-assisted content enhancement
- [ ] Export to other story formats

## Session Checkpoint Recovery

### If Session Breaks, Resume By:
1. Check `utilities/` for created import files
2. Review `analysis/import_staging/` for test data
3. Test existing components with: `python -c "from utilities.storypack_importer import StorypackImporter; print('Import system loaded')"`
4. Continue from last completed phase in development plan
5. Run existing tests to validate current state

### Progress Tracking Files
- `utilities/import_progress.md` - Detailed progress notes
- `analysis/import_staging/test_results.json` - Test run results
- `logs/import_development.log` - Development session logs

## Notes
- Leverage existing OpenChronicle infrastructure (ModelManager, logging, database)
- Maintain backward compatibility with existing storypacks
- Design for extensibility (new template types, source formats)
- Focus on user experience and error recovery
- Document all AI prompts and processing logic

## Existing Core Infrastructure to Leverage

### Already Available for Reuse:
- **`core/content_analyzer.py`** - Sophisticated LLM-powered content analysis with ModelManager integration
- **`core/character_consistency_engine.py`** - Character data validation and consistency checking
- **`core/character_style_manager.py`** - Character writing style analysis and management
- **`core/memory_manager.py`** - Story memory organization and management
- **`core/story_loader.py`** - Story structure loading and validation
- **`core/context_builder.py`** - Context building from structured data
- **`utilities/logging_system.py`** - Centralized logging with test/production separation

### Extension Strategy:
1. **Extend, don't duplicate** - Add import-specific methods to existing classes
2. **Composition over creation** - Use existing engines as components in import pipeline
3. **Minimal additions** - Only create new utilities when existing ones can't be extended
4. **Maintain patterns** - Follow existing OpenChronicle architectural patterns

---

**Created**: July 26, 2025  
**Status**: Ready for Implementation  
**Next Step**: Begin Phase 1 - Foundation development
