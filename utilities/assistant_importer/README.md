# Assistant Importer

## Overview

The Assistant Importer utility converts AI assistant conversation data into OpenChronicle story format. It specializes in handling conversations from various AI assistants, understanding their specific formats and conversation patterns.

## Features

### Supported AI Assistants
- **ChatGPT**: OpenAI ChatGPT conversation exports
- **Claude**: Anthropic Claude conversation data
- **Copilot**: GitHub Copilot and Microsoft Copilot conversations
- **Gemini**: Google Gemini conversation exports
- **Generic**: Standard AI assistant format

### Supported Input Formats
- **JSON**: Standard assistant API response format
- **Markdown**: Human-readable conversation exports
- **HTML**: Web-based conversation exports
- **TXT**: Plain text conversation logs
- **Auto-detection**: Automatically detects format and assistant type

### Conversation Processing
- **Session Management**: Handles multi-session conversations
- **System Message Handling**: Processes system instructions and context
- **Role Identification**: Distinguishes between user, assistant, and system messages
- **Context Preservation**: Maintains conversation flow and continuity

### Output Format
- **OpenChronicle Story**: Creates structured narrative with proper dialogue
- **Character Profiles**: Generates distinct characters for user and assistant
- **Chapter Division**: Organizes sessions into story chapters
- **Metadata Integration**: Preserves assistant-specific metadata

## Usage

```bash
# Basic import with auto-detection
python utilities/main.py assistant-importer conversation.json output_story/

# Specify assistant type
python utilities/main.py assistant-importer chatgpt_export.json output_story/ \
    --assistant-type chatgpt

# Include system messages
python utilities/main.py assistant-importer claude_chat.md output_story/ \
    --assistant-type claude \
    --include-system-messages

# Split by sessions
python utilities/main.py assistant-importer conversations/ output_story/ \
    --split-by-session \
    --format auto

# Custom story details
python utilities/main.py assistant-importer gemini_export.html output_story/ \
    --assistant-type gemini \
    --name "AI Research Collaboration" \
    --description "Research discussion with Gemini AI"
```

## Planned Architecture

### Core Components
- **`importer.py`**: Main AssistantImporter class
- **`parsers/`**: Assistant-specific parsers (ChatGPT, Claude, etc.)
- **`converters/`**: Conversation to narrative converters
- **`processors/`**: Message processing and enhancement
- **`utils/`**: Utility functions for assistant data handling

### Assistant-Specific Handling
- **ChatGPT Parser**: Handles OpenAI conversation exports
- **Claude Parser**: Processes Anthropic conversation format
- **Copilot Parser**: Manages Microsoft/GitHub conversation data
- **Gemini Parser**: Handles Google AI conversation exports
- **Generic Parser**: Fallback for unknown assistant formats

### Processing Pipeline
1. **Format Detection**: Identify assistant type and data format
2. **Parsing**: Extract messages, roles, timestamps, metadata
3. **Session Segmentation**: Group messages into conversation sessions
4. **Content Processing**: Handle code blocks, formatting, special content
5. **Narrative Conversion**: Transform to story format with proper dialogue

### Story Generation
1. **Character Creation**: Generate user and assistant character profiles
2. **Scene Organization**: Structure conversations into narrative scenes
3. **Dialogue Formatting**: Convert messages to natural dialogue
4. **Chapter Division**: Organize sessions into story chapters
5. **Metadata Preservation**: Maintain assistant and conversation metadata

## Implementation Status

**Status**: Planning/Design Phase  
**Priority**: Medium  
**Dependencies**: Core story creation system, character management

### Development Plan
1. **Phase 1**: Generic assistant import with JSON support
2. **Phase 2**: ChatGPT-specific parsing and features
3. **Phase 3**: Claude, Copilot, and Gemini support
4. **Phase 4**: Advanced session management and formatting

## Configuration

Future configuration options will include:
- Assistant-specific parsing rules
- Default character naming conventions
- Session division criteria
- System message handling preferences
- Output formatting options

## Integration

The Assistant Importer will integrate with:
- OpenChronicle story creation system
- Character management and profiles
- Scene and chapter organization
- Metadata and tagging systems
- Content analysis and enhancement

## Special Considerations

### Code and Technical Content
- Proper handling of code blocks and technical discussions
- Preservation of formatting in programming-related conversations
- Integration with technical documentation features

### Multi-turn Conversations
- Long conversation threading and context
- Session breaks and continuation handling
- Topic transition detection and scene division

### Assistant Personalities
- Preservation of assistant communication style
- Character development based on assistant behavior
- Consistent voice and tone in narrative conversion
