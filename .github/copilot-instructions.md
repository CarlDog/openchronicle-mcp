# OpenChronicle Copilot Instructions

## Development Environment
**Platform**: Windows with PowerShell 5.1
**Critical Requirements**:
- **PowerShell Syntax**: Use `;` for command chaining, NOT `&&`
- **Path Format**: Use Windows backslash paths in PowerShell contexts
- **Test Patience**: 400+ tests take time - allow sufficient execution time
- **File Operations**: Use PowerShell cmdlets (`Remove-Item`, `Get-ChildItem`) not Unix commands

## Architecture Overview
OpenChronicle is a narrative AI engine with **13 core modules** using plugin-style model management. The `ModelManager` (`core/model_adapter.py`) orchestrates 15+ LLM providers with fallback chains and dynamic configuration loading.

**Critical Pattern**: Always route through `ModelManager` - never instantiate adapters directly.

## Core Development Workflows

### Model Adapter Usage
```python
# Check adapter exists before using
if adapter_name not in model_manager.adapters:
    await model_manager.initialize_adapter(adapter_name)

# Use fallback chains for resilience  
chain = model_manager.get_fallback_chain(adapter_name)
for attempt_adapter in chain:
    try:
        response = await adapter.generate_response(prompt)
        break
    except Exception:
        continue
```

### Configuration Pattern
- **Primary**: `config/model_registry.json` (registry-only, single source of truth)
- **Dynamic**: Use `model_manager.add_model_config()` for runtime additions

### Memory-Scene Synchronization 
```python
# ALWAYS update memory before logging scenes
memory_manager.update_character_memory(story_id, character_updates)
scene_logger.save_scene(story_id, scene_data, memory_snapshot)
```

## Testing & Development Commands
```powershell
# Quick validation
python -c "from core.model_adapter import ModelManager; print('OK')"

# Test with mocks only (FAST - minimal test subset)
python main.py --test --max-iterations 1

# Full test suite (SLOW - 400+ tests, allow 5-10 minutes)
python -m pytest tests/ -v

# Specific module testing
python -m pytest tests/test_model_adapter.py::test_dynamic_model_management -v

# PowerShell file operations (NOT Unix commands)
Remove-Item "path\to\file" -Force
Get-ChildItem "directory" | Measure-Object
```

## Docker Development
- **Init Pattern**: `/usr/local/bin/init-app.sh` copies `/app-template/` → `/app/` on first run
- **Volume**: External mount `/volume1/docker/openchronicle:/app` for persistence
- **Network**: `ollama_openchronicle` external network with ollama-alpha:11434

## Project-Specific Conventions
- **Logging**: Import from `utilities/logging_system`, use `log_system_event(type, description)`
- **Transformers**: Check `TRANSFORMERS_AVAILABLE` before import (graceful fallback)
- **Async**: All model operations use async/await patterns with proper exception handling
- **Clean Development**: Consolidate documentation, avoid file proliferation, maintain organized structure

## Clean Development Guidelines
- **Consolidate over create**: Merge related documentation into comprehensive guides
- **Single source of truth**: Avoid duplicate information across multiple files
- **Purposeful structure**: Every file should have a clear, unique purpose
- **Regular cleanup**: Remove obsolete documentation and temporary files
- **Extend over new**: Use existing files/functions rather than creating additional helper scripts or utilities
- **Organized folders**: Keep ALL codebase folders clean and minimal. Including: **.github**, **.copilot**, **.vscode**, **files**
  - **.copilot**: Contains architecture and development guidelines
  - **.vscode**: Empty or minimal, only for essential scripts
  - **files**: Should not contain temporary or obsolete files

## Key Architecture Files
- `core/model_adapter.py` - Central orchestration (1500+ lines)
- `.copilot/architecture/module_interactions.md` - System design
- `tests/test_model_adapter.py` - Testing patterns and mocking
