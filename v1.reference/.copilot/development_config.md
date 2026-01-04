# OpenChronicle Development Configuration

## Environment

- **Python Version**: 3.13.5
- **Python Executable**: `C:\Program Files\Python313\python.exe`
- **Shell**: PowerShell (Windows)
- **Dependencies**: Installed globally (no .venv)

## Terminal Command Patterns

### ✅ CORRECT Command Patterns (Auto-close)

```bash
# Single-line Python commands
python -c "import module; print('result')"

# Version checks
python --version

# Package installation
pip install package_name

# Script execution
python script.py

# Multiple commands (PowerShell)
command1; command2; command3
```

### ❌ AVOID These Patterns (Hang/Need Enter/Exit)

```bash
# Multi-line strings with actual line breaks
python -c "
print('hello')
print('world')
"

# Interactive Python
python

# Background processes without isBackground=true
some_service_command

# Using && instead of ; in PowerShell
command1 && command2  # Wrong for PowerShell
command1; command2    # Correct for PowerShell
```

## Import Name Mappings

```python
# Package Install Name → Import Name
pip install pyyaml     → import yaml
pip install Pillow     → from PIL import Image
pip install httpx      → import httpx
pip install pytest    → import pytest
```

## VS Code Configuration

- **Interpreter Path**: Explicitly set to Python 3.13
- **Analysis Paths**: `./core`, `./utilities`, `.`
- **Environment Activation**: Disabled (global Python)
- **File Exclusions**: `.venv`, `__pycache__`, `.pytest_cache`

## Project Structure

```
openchronicle-core/
├── .vscode/           # VS Code settings
├── .copilot/          # AI assistant documentation
├── config/
│   ├── models/        # Model configurations
│   └── model_registry.json
├── core/              # Core modules
├── tests/             # Test files
└── requirements.txt   # Dependencies
```

## Testing Commands

```bash
# Quick dependency test
python -c "import yaml, httpx; from PIL import Image; print('All OK')"

# OpenChronicle test
python -c "import sys; sys.path.insert(0, '.'); from core.image_generation_engine import create_image_engine; print('Engine OK')"

# Test image registry integration
python -c "import sys; sys.path.insert(0, '.'); from core.image_generation_engine import load_model_registry; r = load_model_registry(); print('Registry OK:', r.get('default_image_model'))"

# Main application modes
python main.py --help                    # Show command-line options
python main.py --test                    # Quick system test (auto-exit)
python main.py --non-interactive         # Non-interactive mode (auto-exit)
python main.py --non-interactive --input "Look around" --max-iterations 1

# Run specific tests
python -m pytest tests/test_image_generation_engine.py -v

# Full test suite
python -m pytest tests/ -v
```

## Image Generation Integration

- **Model Registry**: `config/model_registry.json` (unified configuration)
- **Image Models**: Configured in `config/model_registry.json` with type: "image"
- **Engine Function**: `create_image_engine(story_id)` - reads directly from model registry
- **Storage Path**: `storage/{story_id}/images/`
- **Integration**: Uses same JSON-based pattern as text models (consistent!)

## Cross-Platform Compatibility

- **Path Handling**: Uses `pathlib.Path` and `os.path.join` throughout
- **File Operations**: All use `with open()` context managers for safe cleanup
- **Directory Removal**: `shutil.rmtree(path, ignore_errors=True)` for safe cleanup
- **String Literals**: Use `\n` not `\\n` for newlines (fixed in character_style_manager.py)
- **Type Annotations**: Use `Optional[List[T]]` not `List[T] = None`

## Design Consistency

- **Configuration Pattern**: All models use JSON configuration files in `config/`
- **Adapter Pattern**: Python adapters implement interfaces, JSON provides configuration
- **No Mixed Approaches**: Eliminated Python registry wrapper, use JSON directly
- **Unified Registry**: Both text and image models in single `model_registry.json`

## Automation Support

- **Command Line Interface**: Full argparse support with help
- **Non-Interactive Mode**: `--non-interactive` for testing/automation
- **Quick Test Mode**: `--test` for system validation
- **Auto-Exit**: No hanging on user input in automated modes
- **CI/CD Ready**: Supports automated testing and deployment

## Warning Suppression

- **Model Loading Warnings**: Suppressed "Some weights of... were not used" messages during model initialization
- **Deprecation Warnings**: Suppressed "return_all_scores is now deprecated" messages
- **Console Output**: Reduced verbosity during model loading with stdout/stderr redirection
- **Remaining Output**: Some PyTorch/accelerate library messages may still appear but are minimal
- **Production Ready**: Clean console output while preserving all functionality
