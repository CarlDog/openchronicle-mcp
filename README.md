# 🧙 OpenChronicle
## 🔧 Core Features (v0.1.x)

- 🧱 **Modular scene prompt builder** with canon/context injection
- 🧠 **Advanced memory management** with character tracking, world state, and flags
- 🔄 **Scene rollback system** with automatic backups and integrity validation
- 🤖 **Multi-model LLM support** with unified adapter system (OpenAI, Ollama, mock)
- � **Intelligent content analysis** with local LLM preprocessing for token optimization
- �📄 **Canon-aware context building** with structured memory integration
- 🗂️ **Story project folders** with structured metadata and modular storypacks
- 📝 **Comprehensive scene logging** with memory snapshots and rollback points
- 🎯 **Lightweight and portable** - optimized for Docker, Raspberry Pi, and cloud deployment

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

## 🚀 Quick Start

### Configuration

OpenChronicle supports multiple LLM backends. Edit `config/models.json` to set your preferred default:

```json
{
  "default_adapter": "mock",  // Change to "openai", "ollama", or "mock"
  "adapters": {
    "mock": {...},     // Built-in mock adapter (no setup required)
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

OpenChronicle supports multiple LLM backends through a unified adapter system:

### Supported Models
- **OpenAI**: GPT-4, GPT-4o-mini, GPT-3.5-turbo
- **Ollama**: Any locally hosted model (Llama, Mistral, etc.)
- **Mock**: Built-in testing adapter

### Configuration
Models are configured in `config/model_registry.json`:

```json
{
  "default_adapter": "mock",
  "adapters": {
    "openai": {
      "type": "openai",
      "model_name": "gpt-4o-mini",
      "max_tokens": 2048,
      "temperature": 0.7
    },
    "ollama": {
      "type": "ollama",
      "model_name": "llama3.2",
      "base_url": "http://localhost:11434"
    }
  }
}
```

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

---nicle** is a modular, AI-powered interactive storytelling engine built to support dynamic worldbuilding, persistent memory, character-driven narratives, and multi-model orchestration — all within a portable, Docker-ready framework.

Craft immersive, branching story worlds using GPT-4o, Claude, or local LLMs — with full control over continuity, tone, and content.

> "Build once. Run anywhere. Remember everything."

---

## ✨ Project Goals

- 🧠 Enable **seamless narrative continuity** across sessions and branches
- ⚙️ Support **model-agnostic orchestration** (OpenAI, Anthropic, local LLMs)
- 📚 Manage **canonical memory**, player flags, and emotional arcs automatically
- 🔍 Integrate **content classification and routing logic** (e.g., NSFW handling)
- 🐳 Deploy anywhere with a **lightweight Docker container**
- 🧩 Allow creators to plug in their own **stories, worlds, and character packs**

---

## 🔧 Core Features (v0.1.x)

- 🧱 **Modular scene prompt builder** with canon/context injection
- 🧠 **Advanced memory management** with character tracking, world state, and flags
- 🔄 **Scene rollback system** with automatic backups and integrity validation
- � **Canon-aware context building** with structured memory integration
- 🗂️ **Story project folders** with structured metadata and modular storypacks
- � **Comprehensive scene logging** with memory snapshots and rollback points
- 🎯 **Lightweight and portable** - optimized for Docker, Raspberry Pi, and cloud deployment

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

Models are configured in `config/models.json`. You can choose any combination of adapters based on your needs and preferences. The system supports OpenAI, Ollama, or mock adapters equally.

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
