# Chatbot Importer

## Overview

The Chatbot Importer utility converts chatbot conversation data into OpenChronicle story format. It supports various input formats and chatbot platforms, automatically detecting conversation structure and converting it to a narrative format suitable for OpenChronicle.

## Features

### Supported Input Formats

- **JSON**: Standard chatbot export format
- **CSV**: Spreadsheet-based conversation logs
- **TXT**: Plain text conversation files
- **Auto-detection**: Automatically detects format from file extension and content

### Conversation Processing

- **Message Merging**: Combines consecutive messages from the same speaker
- **Timestamp Preservation**: Maintains original conversation timing
- **Speaker Identification**: Automatically identifies different conversation participants
- **Context Extraction**: Preserves conversation context and flow

### Output Format

- **OpenChronicle Story**: Creates properly structured story with scenes and dialogue
- **Character Generation**: Automatically creates character profiles for participants
- **Scene Segmentation**: Breaks conversations into logical scene divisions
- **Metadata Preservation**: Maintains original conversation metadata

## Usage

```bash
# Basic import
python utilities/main.py chatbot-importer conversations.json output_story/

# Specify format explicitly
python utilities/main.py chatbot-importer data.csv output_story/ --format csv

# Custom story details
python utilities/main.py chatbot-importer chat.txt output_story/ \
    --name "Customer Support Chat" \
    --description "Support conversation from 2025-08-08"

# Advanced options
python utilities/main.py chatbot-importer conversations/ output_story/ \
    --merge-messages \
    --preserve-timestamps \
    --format auto
```

## Planned Architecture

### Core Components

- **`importer.py`**: Main ChatbotImporter class
- **`parsers/`**: Format-specific parsers (JSON, CSV, TXT)
- **`converters/`**: Conversation to story converters
- **`utils/`**: Utility functions for text processing

### Input Processing

1. **Format Detection**: Identify input format and structure
2. **Parsing**: Extract messages, speakers, timestamps
3. **Validation**: Ensure data integrity and completeness
4. **Normalization**: Standardize message format

### Story Generation

1. **Character Creation**: Generate character profiles for participants
2. **Scene Division**: Break conversation into logical scenes
3. **Dialogue Formatting**: Convert messages to narrative dialogue
4. **Metadata Generation**: Create story metadata and context

## Implementation Status

**Status**: Planning/Design Phase
**Priority**: Medium
**Dependencies**: Core story creation system

### Development Plan

1. **Phase 1**: Basic JSON import functionality
2. **Phase 2**: CSV and TXT format support
3. **Phase 3**: Advanced conversation processing
4. **Phase 4**: Multi-file and batch import

## Configuration

Future configuration options will include:

- Default speaker names and roles
- Message merging thresholds
- Scene division criteria
- Character generation rules

## Integration

The Chatbot Importer will integrate with:

- OpenChronicle story creation system
- Character management system
- Scene logging and organization
- Metadata and tagging systems
