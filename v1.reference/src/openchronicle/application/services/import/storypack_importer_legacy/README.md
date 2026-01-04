# Storypack Importer

## Overview

The Storypack Importer is a utility for importing storypack files into OpenChronicle format. This utility is designed to replace the legacy `storypack_import` functionality with a more robust, flexible, and maintainable implementation.

## Purpose

- Import existing storypack files (.zip, .json, .tar.gz) into OpenChronicle
- Validate storypack structure and content
- Convert legacy formats to current OpenChronicle schema
- Provide detailed import reports and error handling
- Support batch processing of multiple storypacks

## Features (Planned)

- **Multi-Format Support**: Handle various storypack formats and versions
- **Schema Validation**: Ensure imported data meets OpenChronicle standards
- **Legacy Compatibility**: Import older storypack formats with automatic conversion
- **Batch Import**: Process multiple storypacks in a single operation
- **Detailed Reporting**: Comprehensive import logs and validation reports
- **Error Recovery**: Graceful handling of corrupted or incomplete storypacks
- **Preview Mode**: Inspect storypack contents before import
- **Selective Import**: Choose specific stories or characters to import

## Usage (When Implemented)

```bash
# Import a single storypack
python utilities/main.py storypack-importer path/to/storypack.zip

# Import with validation
python utilities/main.py storypack-importer path/to/storypack.zip --validate-strict

# Batch import multiple storypacks
python utilities/main.py storypack-importer path/to/storypacks/ --batch

# Preview storypack contents
python utilities/main.py storypack-importer path/to/storypack.zip --preview-only

# Import specific stories
python utilities/main.py storypack-importer path/to/storypack.zip --stories "Story1,Story3"
```

## Command-Line Options (Planned)

- `--validate-strict`: Strict validation mode with comprehensive checks
- `--batch`: Process all storypacks in a directory
- `--preview-only`: Show storypack contents without importing
- `--stories`: Comma-separated list of specific stories to import
- `--characters`: Import only specified characters
- `--output-format`: Choose output format for import reports
- `--backup`: Create backup before import
- `--force`: Override validation warnings
- `--dry-run`: Show what would be imported without making changes

## Implementation Status

- **Status**: Planning/Stub Phase
- **Priority**: High (replacement for legacy system)
- **Dependencies**: Core story system, database systems
- **Testing**: Comprehensive test suite planned for various storypack formats

## Development Notes

This utility will completely replace the existing `storypack_import` functionality:

- More robust error handling
- Better validation and reporting
- Support for newer storypack formats
- Improved user experience with detailed feedback
- Integration with OpenChronicle's modern architecture

## Related Systems

- Story Loading System
- Database Management
- Validation Engine
- Character Management
- Memory Systems
