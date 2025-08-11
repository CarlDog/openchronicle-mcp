# Modular Storypack Import System

## Overview

The OpenChronicle Modular Storypack Import System replaces the monolithic 57KB `storypack_importer.py` with a focused, testable architecture following SOLID principles.

## Architecture

### Core Principles
- **Single Responsibility**: Each component has one clear purpose
- **Interface Segregation**: Focused interfaces with minimal surface area
- **Dependency Injection**: Components receive dependencies rather than hard-coding them
- **Open/Closed**: Easy to extend without modifying existing code
- **Testability**: Each component can be tested in isolation

### Components

#### Interfaces (`interfaces/`)
- **IContentParser**: File discovery and content reading operations
- **IMetadataExtractor**: Metadata extraction from content and files
- **IStructureAnalyzer**: Directory structure analysis and organization
- **IAIProcessor**: AI-powered content analysis (optional)
- **IContentClassifier**: Pattern-based content classification
- **IValidationEngine**: Content and system validation
- **IStorypackBuilder**: Storypack structure creation and organization
- **ITemplateEngine**: Template loading and processing
- **IOutputFormatter**: Result formatting and report generation

#### Parsers (`parsers/`)
- **ContentParser**: Discovers files, categorizes content, handles encoding detection
- **MetadataExtractor**: Extracts metadata using patterns and analysis
- **StructureAnalyzer**: Analyzes directory structures and suggests organization

#### Processors (`processors/`)
- **AIProcessor**: Integrates with OpenChronicle's AI capabilities
- **ContentClassifier**: Classifies content using heuristics and patterns
- **ValidationEngine**: Validates content formats and system readiness

#### Generators (`generators/`)
- **StorypackBuilder**: Creates storypack structures and organizes files
- **TemplateEngine**: Loads and processes templates for storypack creation
- **OutputFormatter**: Formats results and generates comprehensive reports

#### Orchestrator
- **StorypackOrchestrator**: Main coordination class using dependency injection
- Manages 8-phase import process
- Handles async operations and error management
- Provides clean API for import operations

## Usage

### Command Line Interface
```bash
# Basic import
python utilities/storypack_import_cli.py /path/to/content "My Storypack"

# With AI processing
python utilities/storypack_import_cli.py /path/to/content "My Storypack" --ai-enabled

# With custom template and detailed reporting
python utilities/storypack_import_cli.py /path/to/content "My Storypack" \
    --template fantasy_adventure --report-type detailed --save-report
```

### Programmatic Usage
```python
from utilities.storypack_import import StorypackOrchestrator
from utilities.storypack_import.parsers import ContentParser, MetadataExtractor, StructureAnalyzer
from utilities.storypack_import.processors import AIProcessor, ContentClassifier, ValidationEngine
from utilities.storypack_import.generators import StorypackBuilder, TemplateEngine, OutputFormatter

# Create components with dependency injection
orchestrator = StorypackOrchestrator(
    content_parser=ContentParser(),
    metadata_extractor=MetadataExtractor(),
    structure_analyzer=StructureAnalyzer(),
    ai_processor=AIProcessor(),  # Optional
    content_classifier=ContentClassifier(),
    validation_engine=ValidationEngine(),
    storypack_builder=StorypackBuilder(),
    template_engine=TemplateEngine(),
    output_formatter=OutputFormatter()
)

# Import storypack
result = await orchestrator.import_storypack(
    source_path=Path("/path/to/content"),
    storypack_name="My Storypack",
    target_dir=Path("storage/storypacks"),
    import_mode="basic"
)

# Format and display results
summary = orchestrator.output_formatter.format_import_result(result, 'summary')
print(summary)
```

## Import Process (8 Phases)

1. **Validation**: Check system readiness and source directory
2. **Discovery**: Find and categorize all content files
3. **Analysis**: Extract metadata and analyze content structure
4. **AI Processing**: Optional AI-powered content analysis
5. **Classification**: Classify content types and confidence scoring
6. **Organization**: Create storypack structure and organize files
7. **Generation**: Generate metadata files and apply templates
8. **Final Validation**: Validate generated storypack structure

## Testing

Run the comprehensive test suite:
```bash
python utilities/test_modular_import.py
```

Tests validate:
- Component instantiation
- Dependency injection
- Interface compliance
- SOLID principles adherence

## Migration from Legacy System

The modular system replaces `storypack_importer.py` with:
- **Better organization**: 9 focused components vs 1 monolithic file
- **Improved testability**: Each component can be tested independently
- **Enhanced maintainability**: Clear separation of concerns
- **Flexible architecture**: Easy to extend or replace components
- **Type safety**: Full type annotations throughout

## Error Handling

- Graceful degradation when optional dependencies unavailable
- Comprehensive error reporting with context
- Validation at multiple stages
- Detailed logging throughout the process

## Performance

- Efficient file discovery and processing
- Optional AI processing to balance speed vs capability
- Streaming file operations for large content sets
- Minimal memory footprint through focused components
