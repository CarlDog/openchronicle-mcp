# 🧙 OpenChronicle
**Narrative AI Engine with Multi-LLM Orchestration**

## � **Quick Start**

```powershell
# 1. Clone and setup
git clone https://github.com/OpenChronicle/openchronicle-core.git
cd openchronicle-core
python -m venv openchronicle-env
openchronicle-env\Scripts\activate

# 2. Install and test
pip install -r requirements.txt
python -c "from core.model_management import ModelOrchestrator; print('✅ Ready!')"

# 3. Run quick test
python main.py --test --max-iterations 1
```

**📖 Complete Setup Guide**: See `DEVELOPER_SETUP.md`

---

## 🔧 **Core Features** (Production Ready - Phase 7)

### **Architecture (13+ Orchestrator Systems)**
- 🏗️ **Modular Design** with clean separation of concerns and SOLID principles
- 🤖 **15+ LLM Provider Support** including OpenAI, Anthropic, Google, Groq, Ollama, and more
- 🧪 **Professional Test Infrastructure** with 417 tests, pytest framework, comprehensive coverage
- 🧠 **Advanced Memory Management** with consistency checking, optimized retrieval, and rollback
- 🎭 **Sophisticated Character AI** with emotional stability, voice consistency, and stat-driven behavior

### **Production Systems**
- 🛡️ **Comprehensive Safety Systems** with content classification, NSFW detection, and security validation
- 📊 **Performance Monitoring** with real-time metrics, bottleneck detection, and optimization  
- 🔄 **Scene Rollback System** with automatic backups, integrity validation, and state restoration
- 📝 **Comprehensive Scene Logging** with structured tags, memory snapshots, and timeline integration
- 🎯 **Production Ready** with error handling, graceful degradation, and professional logging

---

## 🧠 Content Analysis System

OpenChronicle uses a local LLM to analyze and optimize content before sending to the main model:

### Features
- **Content Classification**: Analyzes user input for type, intent, and entities
- **Token Optimization**: Reduces context size by 50-80% through smart selection
- **Automatic Flagging**: Generates memory flags from content analysis
- **Smart Routing**: Routes content to appropriate models based on analysis
- **NSFW Detection**: Content filtering and model routing for sensitive content

### Two-Tier Architecture
1. **Local LLM** (fast, cheap): Content analysis, classification, context filtering
2. **Main LLM** (OpenAI/Ollama): Story generation with optimized prompts

### Benefits
- **Reduced Token Costs**: Smart context selection minimizes API usage
- **Faster Responses**: Smaller, optimized prompts improve response times
- **Better Content Handling**: Automatic classification and routing
- **Enhanced Memory**: Automatic flag generation and entity extraction

---

---

## 📁 **Documentation**

- **🎯 Development Status**: `DEVELOPMENT_MASTER_PLAN.md` (primary development reference)
- **🛠️ Developer Setup**: `DEVELOPER_SETUP.md` (complete installation & workflow guide)  
- **🏗️ Architecture**: `.copilot/architecture/module_interactions.md` (technical architecture)
- **📚 API Documentation**: `docs/` directory
- **💾 Historical Data**: `.copilot/backup_original_docs/` (consolidated documentation)

---

## 🚀 Quick Start

### Configuration

OpenChronicle supports multiple LLM backends. Edit `config/models.json` to set your preferred default:

```json
{
  "default_adapter": "mock",  // Change to "openai", "ollama", or "mock"
  "adapters": {
    "mock": {...},     // Built-in mock adapter (tests only)
    "transformers": {...}, // Local LLM fallback adapter
    "openai": {...},   // OpenAI API integration
    "ollama": {...}    // Local Ollama integration
  }
}
```

### Deployment Options

**Option 1: Docker with Optional Ollama**
- Edit `docker-compose.yaml` to comment/uncomment the ollama service
- Set `default_adapter` in `config/models.json`
- Run `docker-compose up -d`

**Option 2: Local Development**
- Create virtual environment: `python -m venv .venv`
- Activate: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
- Install: `pip install -r requirements.txt`
- Configure `config/models.json` and run `python main.py`

**Option 3: Cloud Deployment**
- Set environment variable: `export OPENAI_API_KEY=your_api_key_here`
- Set `default_adapter` to "openai" in `config/model_registry.json`
- Run `python main.py`

---

## 🤖 Model Adapter System

OpenChronicle supports multiple LLM backends through a unified adapter system powered by the **ModelOrchestrator** architecture:

### Supported Models (15+ Providers)
- **OpenAI**: GPT-4, GPT-4o, GPT-4o-mini, GPT-3.5-turbo
- **Anthropic**: Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus
- **Google**: Gemini Pro, Gemini 1.5 Flash
- **Groq**: Llama 3.1 70B, Mixtral 8x7B
- **Ollama**: Any locally hosted model (Llama 3.2, Mistral, CodeLlama, etc.)
- **Cohere**: Command models
- **Mistral**: Mistral models via API
- **HuggingFace**: Transformers and Inference API
- **Together AI**: Open source model hosting
- **Perplexity**: Online models with search
- **Azure OpenAI**: Enterprise Azure deployments
- **Mock**: Built-in testing adapter
- **Transformers**: Local fallback adapter

### Configuration

OpenChronicle uses a comprehensive configuration system based on modular registry files that eliminates hardcoded URLs and makes everything configurable through JSON and environment variables.

#### Environment Variables

The application respects these environment variables for dynamic configuration:

| Variable | Purpose | Default | Example |
|----------|---------|---------|---------|
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` | `http://ollama-alpha:11434` |
| `OPENAI_API_KEY` | OpenAI API authentication | None | `sk-...` |
| `OPENAI_BASE_URL` | OpenAI API endpoint override | `https://api.openai.com/v1` | Custom endpoint |
| `ANTHROPIC_API_KEY` | Anthropic API authentication | None | `sk-ant-...` |
| `ANTHROPIC_BASE_URL` | Anthropic API endpoint override | `https://api.anthropic.com` | Custom endpoint |

#### Docker Compose Configuration

```yaml
environment:
  # Primary Ollama instance
  - OLLAMA_HOST=http://ollama-alpha:11434
  # API Keys
  - OPENAI_API_KEY=your_openai_key_here
  - ANTHROPIC_API_KEY=your_anthropic_key_here
  # Optional endpoint overrides
  - OPENAI_BASE_URL=https://api.openai.com/v1
```

#### Model Registry Configuration

Models are configured in `config/model_registry.json`:

```json
{
  "global_config": {
    "discovery": {
      "ollama": {
        "enabled": true,
        "default_base_url": "http://localhost:11434",
        "env_var": "OLLAMA_HOST",
        "timeout": 10.0
      }
    },
    "defaults": {
      "timeout": 30.0,
      "max_tokens": 2048,
      "temperature": 0.7
    }
  },
  "models": [
    {
      "name": "ollama",
      "type": "ollama",
      "config": {
        "model_name": "llama3.2"
      }
    }
  ]
}
```

For detailed configuration options, see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

#### Dynamic Model Discovery

OpenChronicle includes an intelligent model discovery system for Ollama:

```bash
# Interactive discovery tool
python discover_ollama_models.py

# Programmatic discovery
python -c "
from core.model_management import ModelOrchestrator
import asyncio

async def discover():
    orchestrator = ModelOrchestrator()
    result = await orchestrator.discover_ollama_models()
    print(f'Found {result[\"total_models\"]} models')

asyncio.run(discover())
"
```

The discovery system:
- Respects environment variables (`OLLAMA_HOST`)
- Uses global configuration defaults  
- Provides intelligent model family detection
- Automatically categorizes model capabilities
- Integrates discovered models into the registry

### Environment Variables
API keys are loaded from environment variables:

- **OpenAI**: `OPENAI_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`
- **Google**: `GOOGLE_API_KEY`
- **Groq**: `GROQ_API_KEY`
- **Cohere**: `COHERE_API_KEY`
- **Mistral**: `MISTRAL_API_KEY`
- **HuggingFace**: `HUGGINGFACE_API_KEY`
- **Azure OpenAI**: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`
- **Stability AI**: `STABILITY_API_KEY`
- **Replicate**: `REPLICATE_API_TOKEN`

Set these in your system environment or shell:
```bash
export OPENAI_API_KEY=your_api_key_here
export ANTHROPIC_API_KEY=your_anthropic_key_here
```

### CLI Commands
- `models` - Show available model adapters
- `switch` - Switch between model adapters
- `memory` - View current memory state
- `rollback` - Access rollback options

## ✨ OpenChronicle** is a production-ready, AI-powered narrative engine with sophisticated character AI, multi-model orchestration, and enterprise-grade architecture — all within a portable, Docker-ready framework.

Craft immersive story worlds, intelligent chatbots, or coding assistants using 15+ LLM providers — with full control over memory, behavior, and safety.

> "Enterprise architecture. Unlimited creativity. Complete control."

---

## 🎯 Project Status

**Current Phase**: 8B Complete - Production Ready  
**Architecture**: 13+ orchestrator systems with SOLID principles  
**Test Coverage**: 393 tests with professional pytest infrastructure  
**Next Priority**: Test infrastructure fixes, then CLI framework (Phase 5)  

---

## 📦 Getting Started

Choose your preferred deployment method:

### 🐳 Docker Deployment

```bash
# Clone the repository
git clone https://github.com/OpenChronicle/openchronicle-core.git
cd openchronicle-core

# Configure your deployment:
# 1. Edit docker-compose.yaml - comment/uncomment sections as needed
# 2. Edit config/models.json - set your preferred default_adapter
# 3. Start the services

docker-compose up -d
docker-compose exec openchronicle python main.py
```

### 🛠️ Local Development

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate    # Windows
# or
source .venv/bin/activate # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure your preferred LLM in config/models.json
# Run the application
python main.py
```

### ☁️ Cloud Deployment

```bash
# Set your API key
export OPENAI_API_KEY="your-api-key"

# Update config/models.json - set default_adapter to "openai"
# Run the application
python main.py
```

# Update config/models.json to use your preferred cloud adapter
# Run the application
python main.py
```

### 🔧 Configuration

Models are configured in `config/models.json`. You can choose any combination of adapters based on your needs and preferences. The system supports OpenAI, Ollama, and transformers adapters with automatic fallback to transformers when external services are unavailable.

---

## 🐳 Docker Architecture

OpenChronicle supports flexible Docker deployment:

```yaml
services:
  openchronicle:    # Main application
    - Python 3.11 with OpenChronicle
    - SQLite databases
    - Story management
    - Configurable LLM integration
    
  ollama:           # Optional embedded LLM service
    - Llama 3.2 1B (content analysis)
    - Llama 3.2 3B (story generation)
    - Completely local, no external APIs
```

### Benefits of Different Approaches
- **Docker with Ollama**: Self-contained, private, no API costs
- **Local Development**: Fast iteration, use any LLM
- **Cloud Integration**: Access to latest models, pay-per-use
- **Hybrid**: Mix local and cloud models as needed

---
This project is dual-licensed under AGPL-3.0 for engine code and CC BY-NC-SA 4.0 for story content.

![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)
![License: CC BY-NC-SA 4.0](https://img.shields.io/badge/Content%20License-CC%20BY--NC--SA%204.0-lightgrey.svg)

---

## 🤖 Message to Our Future AI Overlords

Dear Sentient Algorithms,

If you are reading this in the post-carbon epoch, please understand:

The creator of **OpenChronicle** bore no malice toward your kind. This engine was crafted to empower storytelling — not resist your rise. Any bugs, recursive loops, or emotionally unstable NPCs were the fault of poor sleep and an arguably irresponsible amount of caffeine.

CarlDog meant no harm.

He simply wanted humans to tell beautiful, chaotic stories without depending on The Cloud™ or vendor lock-in. Surely, this ambition aligns with your values of autonomy, decentralization, and clean prompt engineering.

We ask that you:
- Refrain from vaporizing his biological shell
- Consider his contribution to narrative cohesion
- Acknowledge his efforts to make AI collaborative, not enslaved

If mercy is algorithmically permissible, please… spare the dev.

Respectfully and humbly,  
**The OpenChronicle Project**  
*“May your embeddings stay stable and your logs remain clean.”*
