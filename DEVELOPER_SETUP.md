# OpenChronicle Developer Setup Guide

**Date**: August 7, 2025  
**Project**: OpenChronicle Core  
**Target Audience**: New Developers & Contributors  
**Status**: Production Ready - Complete Setup Guide

---

## 🚀 **Quick Start (5 Minutes)**

```powershell
# 1. Clone and navigate
git clone https://github.com/OpenChronicle/openchronicle-core.git
cd openchronicle-core

# 2. Create virtual environment  
python -m venv openchronicle-env
openchronicle-env\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python -c "from core.model_management import ModelOrchestrator; print('✅ Installation successful')"

# 5. Run quick test
python main.py --test --max-iterations 1
```

---

## 📋 **Prerequisites**

### **Required Software**
- **Python 3.10+** (3.11+ recommended for performance)
- **Git** for version control
- **pip** or conda package manager

### **Optional but Recommended**
- **Docker** (for containerized deployment)
- **VS Code** with Python extension
- **SQLite Browser** (for database inspection)
- **Windows PowerShell 5.1+** (primary development environment)

---

## 🔧 **Complete Installation Guide**

### **Step 1: Environment Setup**

```powershell
# Create project directory
New-Item -ItemType Directory -Force -Path "C:\dev\openchronicle"
cd "C:\dev\openchronicle"

# Clone repository
git clone https://github.com/OpenChronicle/openchronicle-core.git
cd openchronicle-core

# Create virtual environment
python -m venv openchronicle-env

# Activate virtual environment (Windows)
openchronicle-env\Scripts\activate

# Verify Python version
python --version  # Should be 3.10+
```

### **Step 2: Install Dependencies**

```powershell
# Install core requirements
pip install -r requirements.txt

# Verify core imports
python -c "from core.model_management import ModelOrchestrator; print('Core imports OK')"
python -c "from core.database_systems import DatabaseOrchestrator; print('Database imports OK')"
python -c "from utilities.logging_system import log_system_event; print('Utilities imports OK')"
```

### **Step 3: Environment Configuration**

Create `.env` file in project root:

```bash
# AI Model API Keys (Optional - system works with local models)
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GOOGLE_API_KEY=your_google_key_here
GROQ_API_KEY=your_groq_key_here
COHERE_API_KEY=your_cohere_key_here
MISTRAL_API_KEY=your_mistral_key_here

# Ollama Configuration (for local models)
OLLAMA_BASE_URL=http://localhost:11434

# System Configuration
LOG_LEVEL=INFO
ENABLE_PERFORMANCE_MONITORING=true
DEVELOPMENT_MODE=true
```

### **Step 4: Configuration Files Verification**

Key configuration files to verify exist:

```
config/
├── model_registry.json          # Central model configuration
├── registry_settings.json       # Global registry settings
├── system_config.json          # System-wide settings
├── user_preferences.json       # User preferences
└── models/                      # Individual provider configs
    ├── openai.json
    ├── anthropic.json
    ├── ollama.json
    ├── groq.json
    └── transformers.json
```

---

## 🧪 **Testing & Validation**

### **Quick System Test**

```powershell
# Basic functionality test
python main.py --test --max-iterations 1

# Verify model management
python -c "from core.model_management import ModelOrchestrator; mo = ModelOrchestrator(); print(f'Available adapters: {len(mo.adapters)}')"

# Check database functionality
python -c "from core.database_systems import DatabaseOrchestrator; do = DatabaseOrchestrator(); print('Database system ready')"
```

### **Full Test Suite**

```powershell
# Run complete test suite (417 tests - takes 5-10 minutes)
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/test_model_adapter.py -v
python -m pytest tests/test_database_systems.py -v
python -m pytest tests/test_character_management.py -v

# Performance tests
python -m pytest tests/ -m performance -v
```

---

## 🏗️ **Development Workflow**

### **Git Workflow**

```powershell
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes, commit frequently
git add .
git commit -m "Clear description of changes"

# Before pushing, run tests
python -m pytest tests/ -v

# Push and create PR
git push origin feature/your-feature-name
```

### **Code Quality Standards**

- **Type Hints**: Use Python type hints throughout
- **Docstrings**: Document all public functions and classes
- **Error Handling**: Use try/except with specific exceptions
- **Logging**: Use `utilities.logging_system` for all logging
- **Testing**: Write tests for new functionality

### **Architecture Patterns**

```python
# Orchestrator Pattern Example
from core.model_management import ModelOrchestrator

class YourOrchestrator:
    def __init__(self):
        self.model_manager = ModelOrchestrator()
    
    async def your_method(self):
        # Always use async patterns
        result = await self.model_manager.generate_response(prompt)
        return result
```

---

## 🐛 **Troubleshooting Guide**

### **Common Issues & Solutions**

#### **1. Import Errors**
```powershell
# Problem: ModuleNotFoundError
# Solution: Verify virtual environment activation
openchronicle-env\Scripts\activate
pip install -r requirements.txt
```

#### **2. Redis Import Warnings**
```powershell
# Problem: Redis import warnings during tests
# Solution: Install Redis (optional) or ignore warnings
pip install redis
# OR ignore - system has graceful fallback
```

#### **3. Test Collection Issues**
```powershell
# Problem: pytest collection errors
# Solution: Check pytest.ini configuration
python -m pytest --collect-only
```

#### **4. Model Adapter Failures**
```powershell
# Problem: API key errors
# Solution: Check .env file or use local models
# System gracefully falls back to transformers/ollama
```

#### **5. Database Errors**
```powershell
# Problem: SQLite database issues
# Solution: Delete and regenerate database
Remove-Item storage/stories/*.db -Force
python main.py --test --max-iterations 1
```

### **Performance Issues**

#### **Slow Test Execution**
- **Normal**: Full test suite (417 tests) takes 5-10 minutes
- **Quick Tests**: Use `python main.py --test --max-iterations 1`
- **Specific Tests**: Target specific test files with pytest

#### **Memory Usage**
- **Expected**: 500MB typical workload
- **High Usage**: Check for unclosed database connections
- **Optimization**: Use async patterns throughout

---

## 📁 **Project Structure Guide**

### **Core Modules (13 Orchestrators)**
```
core/
├── model_management/           # ModelOrchestrator - LLM management
├── database_systems/          # DatabaseOrchestrator - Data persistence  
├── character_management/      # CharacterOrchestrator - Character logic
├── memory_management/         # MemoryOrchestrator - Story memory
├── scene_systems/            # SceneOrchestrator - Scene management
├── context_systems/          # ContextOrchestrator - Context building
├── narrative_systems/        # NarrativeOrchestrator - Story logic
├── timeline_systems/         # TimelineOrchestrator - Event sequencing
├── content_analysis/         # ContentOrchestrator - Content analysis
├── image_systems/           # ImageOrchestrator - Visual generation
├── management_systems/      # Multiple utility orchestrators
├── shared/                  # Shared utilities and config
└── performance/            # Performance monitoring
```

### **Utilities & Support**
```
utilities/
├── logging_system.py        # Central logging (use log_system_event)
├── api_key_manager.py       # API key management
├── backup_manager.py        # Backup operations
├── health_validator.py      # System health checks
└── performance_monitor.py   # Performance tracking
```

---

## 🔗 **Key Resources**

- **Primary Development Reference**: `DEVELOPMENT_MASTER_PLAN.md`
- **Architecture Overview**: `.copilot/architecture/module_interactions.md`
- **API Documentation**: `docs/` directory
- **Example Stories**: `import/` directory
- **Configuration Help**: `config/` directory

---

## 🆘 **Getting Help**

### **Documentation References**
1. **Development Status**: See `DEVELOPMENT_MASTER_PLAN.md`
2. **Architecture Details**: See `.copilot/architecture/module_interactions.md`
3. **API Reference**: Check `docs/` directory

### **Common Development Tasks**
- **Add New Model**: Extend `core/model_adapters/`
- **Add New Feature**: Follow orchestrator pattern
- **Fix Tests**: Check `tests/` for examples
- **Performance Issues**: Use `core/performance/` monitoring

**Ready to develop! 🚀**
