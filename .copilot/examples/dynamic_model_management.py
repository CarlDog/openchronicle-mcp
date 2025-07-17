# Dynamic Model Management Examples

## Complete Working Examples

### Basic Model Management

```python
#!/usr/bin/env python3
"""
Example: Basic Dynamic Model Management
Demonstrates adding, removing, and managing models at runtime.
"""

import sys
import os

# Add core to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from model_adapter import ModelManager

def main():
    # Initialize model manager
    model_manager = ModelManager()
    
    # List current models
    print("Current models:")
    models = model_manager.list_model_configs()
    for name, config in models.items():
        status = "enabled" if config.get('enabled', True) else "disabled"
        print(f"  {name}: {config['provider']} - {status}")
    
    # Add a new model
    print("\nAdding new model...")
    success = model_manager.add_model_config(
        "test-model",
        {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_nsfw": False,
            "cost_per_token": 0.000002,
            "rate_limit": 3500,
            "allowed_content": ["general", "analysis"],
            "blocked_content": ["nsfw", "harmful"]
        }
    )
    
    if success:
        print("✅ Model added successfully")
    else:
        print("❌ Failed to add model")
    
    # Disable a model
    print("\nDisabling model...")
    success = model_manager.disable_model("test-model")
    if success:
        print("✅ Model disabled successfully")
    
    # Re-enable the model
    print("\nRe-enabling model...")
    success = model_manager.enable_model("test-model")
    if success:
        print("✅ Model enabled successfully")
    
    # Remove the model
    print("\nRemoving model...")
    success = model_manager.remove_model_config("test-model")
    if success:
        print("✅ Model removed successfully")
    else:
        print("❌ Failed to remove model")

if __name__ == "__main__":
    main()
```

### Advanced Configuration Management

```python
#!/usr/bin/env python3
"""
Example: Advanced Dynamic Model Configuration
Demonstrates complex model management scenarios.
"""

import sys
import os
import json

# Add core to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from model_adapter import ModelManager
from utilities.logging_system import get_logger

def setup_development_environment():
    """Setup models for development (local + fast models)."""
    model_manager = ModelManager()
    logger = get_logger("model_setup")
    
    # Development-friendly models
    dev_models = {
        "ollama-dev": {
            "provider": "ollama",
            "model": "llama3.2:3b",
            "max_tokens": 2048,
            "temperature": 0.8,
            "supports_nsfw": True,
            "cost_per_token": 0.0,  # Local model
            "rate_limit": 1000,
            "allowed_content": ["general", "creative", "analysis"],
            "blocked_content": ["illegal"]
        },
        "groq-fast": {
            "provider": "groq",
            "model": "llama3-8b-8192",
            "max_tokens": 8192,
            "temperature": 0.7,
            "supports_nsfw": True,
            "cost_per_token": 0.0000001,
            "rate_limit": 30,
            "allowed_content": ["general", "creative", "analysis"],
            "blocked_content": ["illegal", "harmful"]
        }
    }
    
    # Add development models
    for model_name, config in dev_models.items():
        success = model_manager.add_model_config(model_name, config)
        if success:
            logger.info(f"Added development model: {model_name}")
        else:
            logger.error(f"Failed to add development model: {model_name}")
    
    # Disable expensive models during development
    expensive_models = ["gpt-4", "claude-3-opus"]
    for model_name in expensive_models:
        if model_name in model_manager.list_model_configs():
            success = model_manager.disable_model(model_name)
            if success:
                logger.info(f"Disabled expensive model: {model_name}")
    
    return model_manager

def setup_production_environment():
    """Setup models for production (reliable + quality models)."""
    model_manager = ModelManager()
    logger = get_logger("model_setup")
    
    # Production-grade models
    prod_models = {
        "gpt-4-turbo": {
            "provider": "openai",
            "model": "gpt-4-turbo-preview",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_nsfw": False,
            "cost_per_token": 0.00003,
            "rate_limit": 500,
            "allowed_content": ["general", "creative", "analysis"],
            "blocked_content": ["nsfw", "harmful", "illegal"]
        },
        "claude-3-sonnet": {
            "provider": "anthropic",
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_nsfw": False,
            "cost_per_token": 0.000003,
            "rate_limit": 1000,
            "allowed_content": ["general", "creative", "analysis"],
            "blocked_content": ["nsfw", "harmful", "illegal"]
        }
    }
    
    # Add production models
    for model_name, config in prod_models.items():
        success = model_manager.add_model_config(model_name, config)
        if success:
            logger.info(f"Added production model: {model_name}")
        else:
            logger.error(f"Failed to add production model: {model_name}")
    
    # Disable development models in production
    dev_models = ["ollama-dev", "groq-fast"]
    for model_name in dev_models:
        if model_name in model_manager.list_model_configs():
            success = model_manager.disable_model(model_name)
            if success:
                logger.info(f"Disabled development model: {model_name}")
    
    return model_manager

def model_health_check():
    """Check health of all enabled models."""
    model_manager = ModelManager()
    logger = get_logger("model_health")
    
    models = model_manager.list_model_configs()
    healthy_models = []
    unhealthy_models = []
    
    for model_name, config in models.items():
        if not config.get('enabled', True):
            continue
            
        try:
            # This would typically involve a health check call
            # For now, we'll just validate the configuration
            required_fields = ['provider', 'model', 'max_tokens']
            if all(field in config for field in required_fields):
                healthy_models.append(model_name)
                logger.info(f"Model {model_name} is healthy")
            else:
                unhealthy_models.append(model_name)
                logger.warning(f"Model {model_name} missing required fields")
        except Exception as e:
            unhealthy_models.append(model_name)
            logger.error(f"Model {model_name} health check failed: {e}")
    
    print(f"✅ Healthy models: {len(healthy_models)}")
    print(f"❌ Unhealthy models: {len(unhealthy_models)}")
    
    return healthy_models, unhealthy_models

def main():
    """Main example execution."""
    print("=== Dynamic Model Management Examples ===\n")
    
    # Setup development environment
    print("1. Setting up development environment...")
    dev_manager = setup_development_environment()
    
    # Setup production environment
    print("\n2. Setting up production environment...")
    prod_manager = setup_production_environment()
    
    # Health check
    print("\n3. Running health check...")
    healthy, unhealthy = model_health_check()
    
    # Display final configuration
    print("\n4. Final model configuration:")
    final_models = prod_manager.list_model_configs()
    for name, config in final_models.items():
        status = "enabled" if config.get('enabled', True) else "disabled"
        provider = config.get('provider', 'unknown')
        print(f"  {name}: {provider} - {status}")

if __name__ == "__main__":
    main()
```

### Configuration Import/Export

```python
#!/usr/bin/env python3
"""
Example: Configuration Import/Export
Demonstrates backing up and restoring model configurations.
"""

import sys
import os
import json
from datetime import datetime

# Add core to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from model_adapter import ModelManager
from utilities.logging_system import get_logger

def export_model_config(filename: str = None):
    """Export current model configuration to JSON file."""
    model_manager = ModelManager()
    logger = get_logger("config_export")
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"model_config_backup_{timestamp}.json"
    
    try:
        models = model_manager.list_model_configs()
        
        # Create export structure
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "models": models
        }
        
        # Write to file
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Configuration exported to {filename}")
        print(f"✅ Configuration exported to {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        print(f"❌ Export failed: {e}")
        return None

def import_model_config(filename: str):
    """Import model configuration from JSON file."""
    model_manager = ModelManager()
    logger = get_logger("config_import")
    
    try:
        with open(filename, 'r') as f:
            import_data = json.load(f)
        
        if "models" not in import_data:
            raise ValueError("Invalid configuration file format")
        
        models = import_data["models"]
        imported_count = 0
        
        for model_name, config in models.items():
            # Skip if model already exists
            current_models = model_manager.list_model_configs()
            if model_name in current_models:
                logger.warning(f"Model {model_name} already exists, skipping")
                continue
            
            # Add the model
            success = model_manager.add_model_config(model_name, config)
            if success:
                imported_count += 1
                logger.info(f"Imported model: {model_name}")
            else:
                logger.error(f"Failed to import model: {model_name}")
        
        print(f"✅ Imported {imported_count} models from {filename}")
        return imported_count
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        print(f"❌ Import failed: {e}")
        return 0

def main():
    """Main example execution."""
    print("=== Configuration Import/Export Examples ===\n")
    
    # Export current configuration
    print("1. Exporting current configuration...")
    backup_file = export_model_config()
    
    if backup_file:
        # Demonstrate import (this would normally be done on another system)
        print("\n2. Demonstrating import...")
        imported = import_model_config(backup_file)
        
        print(f"\n3. Import completed: {imported} models imported")
        
        # Clean up
        print(f"\n4. Backup file created: {backup_file}")
        print("   (You can use this file to restore configuration later)")

if __name__ == "__main__":
    main()
```

## Test Examples

### Unit Test Pattern

```python
#!/usr/bin/env python3
"""
Example: Unit Tests for Dynamic Model Management
Demonstrates testing patterns for model management.
"""

import unittest
import sys
import os

# Add core to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from model_adapter import ModelManager

class TestDynamicModelManagement(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures."""
        self.model_manager = ModelManager()
        self.test_config = {
            "provider": "openai",
            "model": "gpt-3.5-turbo",
            "max_tokens": 4096,
            "temperature": 0.7,
            "supports_nsfw": False,
            "cost_per_token": 0.000002,
            "rate_limit": 3500,
            "allowed_content": ["general", "analysis"],
            "blocked_content": ["nsfw", "harmful"]
        }
    
    def test_add_model_config(self):
        """Test adding a new model configuration."""
        success = self.model_manager.add_model_config("test-model", self.test_config)
        self.assertTrue(success, "Failed to add model configuration")
        
        # Verify model was added
        models = self.model_manager.list_model_configs()
        self.assertIn("test-model", models)
        self.assertEqual(models["test-model"]["provider"], "openai")
    
    def test_remove_model_config(self):
        """Test removing a model configuration."""
        # First add a model
        self.model_manager.add_model_config("test-model", self.test_config)
        
        # Then remove it
        success = self.model_manager.remove_model_config("test-model")
        self.assertTrue(success, "Failed to remove model configuration")
        
        # Verify model was removed
        models = self.model_manager.list_model_configs()
        self.assertNotIn("test-model", models)
    
    def test_enable_disable_model(self):
        """Test enabling and disabling models."""
        # Add a model
        self.model_manager.add_model_config("test-model", self.test_config)
        
        # Disable it
        success = self.model_manager.disable_model("test-model")
        self.assertTrue(success, "Failed to disable model")
        
        # Check it's disabled
        models = self.model_manager.list_model_configs()
        self.assertFalse(models["test-model"].get("enabled", True))
        
        # Enable it
        success = self.model_manager.enable_model("test-model")
        self.assertTrue(success, "Failed to enable model")
        
        # Check it's enabled
        models = self.model_manager.list_model_configs()
        self.assertTrue(models["test-model"].get("enabled", True))
    
    def test_invalid_config(self):
        """Test handling of invalid configurations."""
        invalid_config = {
            "provider": "openai",
            # Missing required fields
        }
        
        success = self.model_manager.add_model_config("invalid-model", invalid_config)
        self.assertFalse(success, "Should reject invalid configuration")
    
    def tearDown(self):
        """Clean up after tests."""
        # Remove any test models
        models = self.model_manager.list_model_configs()
        for model_name in models:
            if model_name.startswith("test-"):
                self.model_manager.remove_model_config(model_name)

if __name__ == "__main__":
    unittest.main()
```

## Usage Patterns

### Story-Specific Model Configuration

```python
# Configure models for a specific story type
def setup_horror_story_models():
    model_manager = ModelManager()
    
    # Add models good for horror/creative content
    horror_models = {
        "claude-creative": {
            "provider": "anthropic",
            "model": "claude-3-sonnet-20240229",
            "temperature": 0.9,  # Higher creativity
            "supports_nsfw": True,
            "allowed_content": ["general", "creative", "horror"]
        },
        "gpt-4-creative": {
            "provider": "openai",
            "model": "gpt-4-turbo-preview",
            "temperature": 0.8,
            "supports_nsfw": False,
            "allowed_content": ["general", "creative"]
        }
    }
    
    for name, config in horror_models.items():
        model_manager.add_model_config(name, config)
```

### Cost-Aware Model Management

```python
# Manage models based on cost constraints
def setup_budget_conscious_models():
    model_manager = ModelManager()
    
    # Disable expensive models
    expensive_models = ["gpt-4", "claude-3-opus"]
    for model in expensive_models:
        model_manager.disable_model(model)
    
    # Enable cost-effective models
    budget_models = ["gpt-3.5-turbo", "claude-3-haiku", "ollama-llama3"]
    for model in budget_models:
        model_manager.enable_model(model)
```

These examples demonstrate the full range of dynamic model management capabilities in OpenChronicle.
