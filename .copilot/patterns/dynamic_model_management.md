# Dynamic Model Management System

## Overview

The OpenChronicle model system now supports dynamic model configuration management, allowing users to add, remove, enable, and disable models at runtime without restarting the application.

## Key Features

### 🔧 Dynamic Model Operations

#### Adding New Models
```python
# Add a new model configuration
model_manager.add_model_config(
    model_name="claude-3-sonnet",
    config={
        "provider": "anthropic",
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 4096,
        "temperature": 0.7,
        "supports_nsfw": True,
        "cost_per_token": 0.000003,
        "rate_limit": 1000,
        "allowed_content": ["general", "creative", "analysis"],
        "blocked_content": ["illegal", "harmful"]
    }
)
```

#### Removing Models
```python
# Remove a model from the registry
model_manager.remove_model_config("claude-3-sonnet")
```

#### Enabling/Disabling Models
```python
# Temporarily disable a model
model_manager.disable_model("claude-3-sonnet")

# Re-enable a model
model_manager.enable_model("claude-3-sonnet")
```

#### Listing All Models
```python
# Get all model configurations
models = model_manager.list_model_configs()
for model_name, config in models.items():
    print(f"{model_name}: {config['provider']} - {'enabled' if config.get('enabled', True) else 'disabled'}")
```

### 🔄 Automatic Registry Updates

The system automatically:
- Updates `model_registry.json` when models are added/removed
- Maintains fallback chains and routing rules
- Validates configurations before saving
- Creates backups before major changes
- Logs all configuration changes

### 🛡️ Safety Features

- **Validation**: All model configurations are validated before being added
- **Backup**: Automatic backup of registry before changes
- **Rollback**: Failed updates are automatically rolled back
- **Logging**: All operations are logged with centralized logging system

## Implementation Details

### Core Methods

The `ModelManager` class provides these dynamic management methods:

```python
def add_model_config(self, model_name: str, config: Dict[str, Any]) -> bool:
    """Add a new model configuration to the registry."""
    
def remove_model_config(self, model_name: str) -> bool:
    """Remove a model configuration from the registry."""
    
def enable_model(self, model_name: str) -> bool:
    """Enable a model in the registry."""
    
def disable_model(self, model_name: str) -> bool:
    """Disable a model in the registry."""
    
def list_model_configs(self) -> Dict[str, Dict[str, Any]]:
    """List all model configurations."""
```

### Configuration Structure

Each model configuration includes:
- `provider`: LLM provider (openai, anthropic, etc.)
- `model`: Specific model name
- `max_tokens`: Token limit
- `temperature`: Generation temperature
- `supports_nsfw`: NSFW content support
- `cost_per_token`: Cost information
- `rate_limit`: Rate limiting
- `allowed_content`: Allowed content types
- `blocked_content`: Blocked content types
- `enabled`: Whether the model is active

### Registry Management

The system maintains:
- **Active Models**: Currently enabled models
- **Fallback Chains**: Automatic failover sequences
- **Content Routing**: NSFW, analysis, creative, and fast model mappings
- **Provider Health**: Monitoring and status tracking

## Usage Examples

### Adding a New Provider

```python
# Add a new Cohere model
model_manager.add_model_config(
    "cohere-command-r",
    {
        "provider": "cohere",
        "model": "command-r",
        "max_tokens": 4096,
        "temperature": 0.7,
        "supports_nsfw": False,
        "cost_per_token": 0.000002,
        "rate_limit": 1000,
        "allowed_content": ["general", "analysis"],
        "blocked_content": ["nsfw", "harmful"]
    }
)
```

### Temporarily Disabling Models

```python
# Disable expensive models during development
model_manager.disable_model("gpt-4")
model_manager.disable_model("claude-3-opus")

# Use only local models
model_manager.enable_model("ollama-llama3")
```

### Dynamic Provider Setup

```python
# Add multiple models from a new provider
new_models = {
    "groq-mixtral": {
        "provider": "groq",
        "model": "mixtral-8x7b-32768",
        "max_tokens": 32768,
        "temperature": 0.7,
        "supports_nsfw": True,
        "cost_per_token": 0.0000005,
        "rate_limit": 30
    },
    "groq-llama3": {
        "provider": "groq",
        "model": "llama3-70b-8192",
        "max_tokens": 8192,
        "temperature": 0.7,
        "supports_nsfw": True,
        "cost_per_token": 0.0000008,
        "rate_limit": 30
    }
}

for model_name, config in new_models.items():
    model_manager.add_model_config(model_name, config)
```

## Integration with Centralized Logging

All dynamic model operations are integrated with the centralized logging system:

```python
from utilities.logging_system import get_logger

logger = get_logger("model_management")
logger.info(f"Added model configuration: {model_name}")
logger.warning(f"Model {model_name} validation failed: {error}")
logger.error(f"Failed to update registry: {error}")
```

## Testing

The dynamic model management system includes comprehensive tests:

- Configuration validation
- Registry update operations
- Fallback chain maintenance
- Error handling and rollback
- Integration with logging system

All tests pass and validate the robustness of the dynamic system.

## Future Enhancements

Planned improvements include:
- Web UI for model management
- Import/export of model configurations
- Advanced health monitoring
- Cost tracking and budgeting
- Performance analytics
- Auto-discovery of new providers
