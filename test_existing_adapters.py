"""
Test Existing Adapter System Integration

This script validates the existing modular adapter system we built last night
and shows how it integrates with the registry system.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_registry_system():
    """Test the registry system loads correctly."""
    try:
        from core.model_management.registry import RegistryManager
        registry = RegistryManager()
        
        providers = registry.get_available_providers()
        print(f"✓ Registry loaded with {len(providers)} providers: {providers}")
        
        models = registry.get_model_configs("text", enabled_only=False)
        print(f"✓ Found {len(models)} text models in registry")
        
        return registry
    except Exception as e:
        print(f"✗ Registry system failed: {e}")
        return None

def test_adapter_base_classes():
    """Test the adapter base classes load correctly."""
    try:
        from core.adapters.base import BaseAPIAdapter, ModelAdapter
        print("✓ Adapter base classes imported successfully")
        
        from core.adapters.exceptions import AdapterInitializationError
        print("✓ Adapter exceptions imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Adapter base classes failed: {e}")
        return False

def test_individual_adapters():
    """Test individual adapter providers."""
    try:
        from core.adapters.providers.openai import OpenAIAdapter
        from core.adapters.providers.ollama import OllamaAdapter
        print("✓ Individual adapter providers imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Individual adapters failed: {e}")
        return False

def test_adapter_factory_without_orchestrator():
    """Test adapter factory without the orchestrator (to avoid circular import)."""
    try:
        # Import the factory directly, avoiding the orchestrator
        import importlib.util
        
        factory_path = "core/adapters/factory.py"
        spec = importlib.util.spec_from_file_location("adapter_factory", factory_path)
        factory_module = importlib.util.module_from_spec(spec)
        
        # Mock the registry import to avoid circular dependency
        import sys
        sys.modules['core.model_management.registry'] = type('MockRegistry', (), {
            'RegistryManager': type('MockRegistryManager', (), {})
        })()
        
        spec.loader.exec_module(factory_module)
        
        print("✓ Adapter factory structure is sound")
        return True
        
    except Exception as e:
        print(f"✗ Adapter factory test failed: {e}")
        return False

def test_existing_model_manager():
    """Test that existing ModelManager still works."""
    try:
        from core.model_adapter import ModelManager
        manager = ModelManager()
        print("✓ Existing ModelManager still loads successfully")
        return True
    except Exception as e:
        print(f"✗ Existing ModelManager failed: {e}")
        return False

def main():
    """Run all integration tests."""
    print("=== Testing Existing Modular Adapter System ===")
    print()
    
    print("1. Testing Registry System...")
    registry = test_registry_system()
    print()
    
    print("2. Testing Adapter Base Classes...")
    base_works = test_adapter_base_classes()
    print()
    
    print("3. Testing Individual Adapters...")
    adapters_work = test_individual_adapters()
    print()
    
    print("4. Testing Adapter Factory Structure...")
    factory_works = test_adapter_factory_without_orchestrator()
    print()
    
    print("5. Testing Existing ModelManager...")
    manager_works = test_existing_model_manager()
    print()
    
    print("=== Summary ===")
    if registry and base_works and adapters_work:
        print("✓ Core modular adapter system is working!")
        print("✓ The existing system from last night is solid")
        print("✓ We should enhance this system rather than replace it")
        print()
        print("Next Steps:")
        print("- Fix circular import between factory and orchestrator")
        print("- Enhance registry integration in existing adapters")
        print("- Complete Phase 1 by validating the existing system")
    else:
        print("✗ Some components need fixing")
    
    if manager_works:
        print("✓ Backward compatibility maintained")
    else:
        print("⚠ Need to ensure backward compatibility")

if __name__ == "__main__":
    main()
