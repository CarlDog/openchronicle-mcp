# OpenChronicle Model Provider Configurations

This directory contains individual configuration files for each AI model provider supported by OpenChronicle. This modular approach replaces the previous monolithic `model_registry.json` file.

## Configuration Structure

Each provider has its own JSON file. **IMPORTANT**: The system processes configurations based on the `"provider"` field in the JSON content, NOT the filename. Users can name files however they want for organization.

**Recommended Naming Convention**:

- `{provider}_{model_identifier}.json` (e.g., `ollama_mistral_7b.json`, `openai_gpt4_turbo.json`)
- Users can also use custom names like `my_favorite_ollama.json` or `production_config.json`

**Content-Driven Discovery**: The system scans all `.json` files and groups them by the `"provider"` field in the JSON content.

## Benefits of Individual Configurations

### 🎯 **User-Friendly**

- Easy to add new providers: just create a new JSON file
- Easy to remove providers: delete the JSON file
- Easy to modify provider settings: edit only the relevant file

### 🔧 **Maintainable**

- Small, focused configuration files
- No merge conflicts when multiple developers work on different providers
- Clear separation of concerns

### 🚀 **Dynamic Discovery**

- OpenChronicle automatically discovers all `.json` files in this directory
- No need to manually register providers in a central file
- Runtime addition/removal of providers supported

## Configuration Schema

Each provider configuration file contains:

```json
{
  "provider": "provider_name",
  "display_name": "Human Readable Name",
  "enabled": true,
  "adapter_class": "ProviderAdapter",
  "api_config": {
    "endpoint": "https://api.provider.com/v1/chat",
    "model": "default-model",
    "api_key_env": "PROVIDER_API_KEY",
    "timeout": 30
  },
  "capabilities": {
    "text_generation": true,
    "streaming": true,
    "function_calling": false
  },
  "limits": {
    "max_tokens": 4096,
    "context_window": 8192,
    "rate_limit_rpm": 1000
  },
  "health_check": {
    "enabled": true,
    "endpoint": "/v1/models",
    "interval": 300
  },
  "fallback_chain": ["backup_provider1", "backup_provider2"]
}
```

## Adding a New Provider

1. Create a new JSON file with any name: `config/models/your_custom_name.json`
2. Ensure the JSON has a `"provider"` field that identifies the provider type
3. Follow the configuration schema above
4. OpenChronicle will automatically discover and load the provider based on content
5. Create the corresponding adapter class in `core/model_adapters/providers/`

**Example**: You can have multiple configs for the same provider:

- `ollama_mistral_7b.json` with `"provider": "ollama"` and `"model": "mistral:7b"`
- `ollama_llama3_8b.json` with `"provider": "ollama"` and `"model": "llama3.1:8b"`
- `my_experimental_ollama.json` with `"provider": "ollama"` and custom settings

## Environment Variables

Each provider configuration references environment variables for sensitive data:

- API keys: `{PROVIDER}_API_KEY`
- Base URLs: `{PROVIDER}_BASE_URL` (optional)
- Organization IDs: `{PROVIDER}_ORGANIZATION` (if applicable)

## Migration from Central Registry

This modular approach replaces the previous centralized `model_registry.json` file:

**Before** (Monolithic):

```
config/model_registry.json  # 675+ lines, all providers
```

**After** (Modular):

```
config/models/
├── openai.json        # 50-80 lines per provider
├── anthropic.json     # Easy to manage individually
├── ollama.json        # Clear separation of concerns
└── [provider].json    # Dynamic discovery
```

## Phase 2.0 Progress - Model-Specific Configurations

### ✅ **OpenAI Models**

- `openai_gpt4o.json` - GPT-4o with vision and reasoning
- `openai_gpt4_turbo.json` - GPT-4 Turbo for high-quality tasks
- `openai_gpt35_turbo.json` - Cost-effective GPT-3.5 Turbo

### ✅ **Anthropic Models**

- `anthropic_claude35_sonnet.json` - Claude 3.5 Sonnet for complex analysis
- `anthropic_claude35_haiku.json` - Claude 3.5 Haiku for speed and cost
- `my_production_claude.json` - Custom-named production config

### ✅ **Ollama Models**

- `ollama_mistral_7b.json` - Local Mistral 7B model
- `ollama_llama3_1_8b.json` - Local Llama 3.1 8B model
- `ollama_codellama_13b.json` - Specialized code generation model

### ✅ **Groq Models** (Ultra-fast inference)

- `groq_llama31_70b.json` - Llama 3.1 70B via Groq
- `groq_mixtral_8x7b.json` - Mixtral 8x7B via Groq

### ✅ **Google Models**

- `gemini_pro.json` - Gemini Pro with excellent context handling
- `gemini_15_flash.json` - Gemini 1.5 Flash for speed and cost

### ✅ **Local Models**

- `transformers_dialogpt_medium.json` - Local conversational AI

**Phase 2.0 Day 1 Status: ✅ COMPLETE** - All provider configurations migrated to model-specific format

This modular configuration system is part of the OpenChronicle Core Refactoring Phase 2.0: Dynamic Configuration Migration.
