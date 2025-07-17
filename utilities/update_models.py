#!/usr/bin/env python3
"""
Model configuration update helper.
Use this script to safely update your models.json with new provider information.
"""

import json
import os
from pathlib import Path
from datetime import datetime

def backup_config():
    """Create a backup of the current models.json in the centralized backup location."""
    config_path = Path(__file__).parent.parent / "config" / "models.json"
    backup_dir = Path(__file__).parent.parent / "storage" / "backups" / "config"
    
    # Ensure backup directory exists
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    backup_path = backup_dir / f"models.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    if config_path.exists():
        with open(config_path, 'r') as src:
            content = src.read()
        with open(backup_path, 'w') as dst:
            dst.write(content)
        print(f"✅ Backup created: {backup_path}")
        return backup_path
    return None

def add_new_adapter(adapter_name, adapter_config):
    """Add a new adapter to models.json."""
    config_path = Path(__file__).parent.parent / "config" / "models.json"
    
    # Backup first
    backup_path = backup_config()
    
    # Load current config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Add new adapter
    config["adapters"][adapter_name] = adapter_config
    
    # Save updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Added new adapter: {adapter_name}")
    print(f"💾 Backup available at: {backup_path}")

def update_model_list(adapter_name, new_models):
    """Update the available_models list for an adapter."""
    config_path = Path(__file__).parent.parent / "config" / "models.json"
    
    # Backup first
    backup_path = backup_config()
    
    # Load current config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    if adapter_name not in config["adapters"]:
        print(f"❌ Adapter {adapter_name} not found!")
        return False
    
    # Update model list
    config["adapters"][adapter_name]["available_models"] = new_models
    
    # Save updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Updated models for {adapter_name}: {new_models}")
    print(f"💾 Backup available at: {backup_path}")
    return True

def main():
    """Interactive configuration update."""
    print("🔧 OpenChronicle Model Configuration Update Helper")
    print("="*50)
    
    while True:
        print("\nOptions:")
        print("1. Add new adapter")
        print("2. Update model list for existing adapter")
        print("3. Create backup of current config")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            adapter_name = input("Enter adapter name: ").strip()
            adapter_type = input("Enter adapter type (openai, anthropic, etc.): ").strip()
            model_name = input("Enter default model name: ").strip()
            base_url = input("Enter base URL (or press Enter for default): ").strip()
            
            adapter_config = {
                "type": adapter_type,
                "model_name": model_name,
                "max_tokens": 2048,
                "temperature": 0.7,
                "api_key": ""
            }
            
            if base_url:
                adapter_config["base_url"] = base_url
            
            add_new_adapter(adapter_name, adapter_config)
            
        elif choice == "2":
            adapter_name = input("Enter adapter name: ").strip()
            models_str = input("Enter comma-separated list of models: ").strip()
            new_models = [model.strip() for model in models_str.split(",")]
            update_model_list(adapter_name, new_models)
            
        elif choice == "3":
            backup_config()
            
        elif choice == "4":
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
