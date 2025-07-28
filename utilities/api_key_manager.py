"""
API key management using OS keyring.
Provides secure storage for AI provider API keys with graceful fallback.
"""

import getpass
import re
import json
from typing import Optional, List, Dict, Any
from pathlib import Path

# Add utilities to path for logging
import sys
sys.path.append(str(Path(__file__).parent))
from logging_system import log_info, log_error, log_system_event

# Optional keyring import with graceful fallback
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    keyring = None

# Service name for keyring storage
KEYRING_SERVICE = "openchronicle"

# Provider mapping for keyring usernames
PROVIDER_MAPPING = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key", 
    "google": "google_api_key",
    "gemini": "google_api_key",  # Alias
    "groq": "groq_api_key",
    "cohere": "cohere_api_key",
    "mistral": "mistral_api_key",
    "huggingface": "huggingface_api_key",
    "azure": "azure_openai_api_key"
}


def is_keyring_available() -> bool:
    """Check if keyring is available for secure storage."""
    return KEYRING_AVAILABLE


def load_api_key_validation_patterns() -> Dict[str, Dict[str, Any]]:
    """
    Load API key validation patterns from model registry.
    
    Returns:
        Dictionary with provider validation patterns
    """
    try:
        registry_path = Path(__file__).parent.parent / "config" / "model_registry.json"
        if not registry_path.exists():
            log_error(f"Model registry not found at {registry_path}")
            return {}
        
        with open(registry_path, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        patterns = {}
        providers = registry.get("environment_config", {}).get("providers", {})
        
        for provider_name, provider_config in providers.items():
            validation = provider_config.get("validation", {})
            if validation.get("requires_api_key") and validation.get("api_key_format"):
                patterns[provider_name] = {
                    "pattern": validation["api_key_format"],
                    "service_name": validation.get("service_name", provider_name.title()),
                    "setup_url": validation.get("setup_url", ""),
                    "description": validation.get("description", "")
                }
        
        return patterns
        
    except Exception as e:
        log_error(f"Failed to load validation patterns: {e}")
        return {}


def validate_api_key_format(provider: str, api_key: str) -> Dict[str, Any]:
    """
    Validate API key format against model registry patterns.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic')
        api_key: The API key to validate
        
    Returns:
        Dictionary with validation results
    """
    patterns = load_api_key_validation_patterns()
    
    # Map provider aliases to main names
    provider_map = {
        "gemini": "google",
        "azure": "openai"  # Azure uses similar format
    }
    main_provider = provider_map.get(provider.lower(), provider.lower())
    
    if main_provider not in patterns:
        # No pattern available - basic length check only
        return {
            "valid": len(api_key) >= 10,
            "reason": "No format pattern available - basic length check only" if len(api_key) >= 10 else "API key too short",
            "suggestion": "Check provider documentation for correct format"
        }
    
    pattern_info = patterns[main_provider]
    pattern = pattern_info["pattern"]
    
    try:
        matches = re.match(pattern, api_key)
        if matches:
            return {
                "valid": True,
                "reason": f"Valid {pattern_info['service_name']} API key format",
                "pattern": pattern
            }
        else:
            return {
                "valid": False,
                "reason": f"Invalid {pattern_info['service_name']} API key format",
                "expected_pattern": pattern,
                "setup_url": pattern_info.get("setup_url", ""),
                "suggestion": f"Expected format matching: {pattern}"
            }
    except re.error as e:
        log_error(f"Invalid regex pattern for {provider}: {e}")
        return {
            "valid": len(api_key) >= 10,
            "reason": f"Pattern validation failed - using basic check: {e}",
            "suggestion": "Check provider documentation for correct format"
        }


def get_api_key(provider: str) -> Optional[str]:
    """
    Get API key for a provider from secure storage.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic')
        
    Returns:
        API key string or None if not found/not available
    """
    if not KEYRING_AVAILABLE or keyring is None:
        return None
    
    try:
        username = PROVIDER_MAPPING.get(provider.lower(), f"{provider.lower()}_api_key")
        api_key = keyring.get_password(KEYRING_SERVICE, username)
        
        if api_key:
            log_info(f"Retrieved API key for {provider} from secure storage")
            return api_key
        
        return None
        
    except Exception as e:
        log_error(f"Failed to retrieve API key for {provider}: {e}")
        return None


def set_api_key(provider: str, api_key: str) -> bool:
    """
    Store API key for a provider in secure storage.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic')
        api_key: The API key to store
        
    Returns:
        True if successful, False otherwise
    """
    if not KEYRING_AVAILABLE or keyring is None:
        log_error("Keyring not available for secure storage")
        return False
    
    try:
        username = PROVIDER_MAPPING.get(provider.lower(), f"{provider.lower()}_api_key")
        keyring.set_password(KEYRING_SERVICE, username, api_key)
        
        log_system_event("api_key_stored", f"API key stored securely for {provider}")
        log_info(f"API key stored securely for {provider}")
        return True
        
    except Exception as e:
        log_error(f"Failed to store API key for {provider}: {e}")
        return False


def remove_api_key(provider: str) -> bool:
    """
    Remove API key for a provider from secure storage.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic')
        
    Returns:
        True if successful, False otherwise
    """
    if not KEYRING_AVAILABLE or keyring is None:
        log_error("Keyring not available")
        return False
    
    try:
        username = PROVIDER_MAPPING.get(provider.lower(), f"{provider.lower()}_api_key")
        
        # Check if key exists first
        existing_key = keyring.get_password(KEYRING_SERVICE, username)
        if not existing_key:
            log_info(f"No API key found for {provider}")
            return False
        
        keyring.delete_password(KEYRING_SERVICE, username)
        
        log_system_event("api_key_removed", f"API key removed for {provider}")
        log_info(f"API key removed for {provider}")
        return True
        
    except Exception as e:
        log_error(f"Failed to remove API key for {provider}: {e}")
        return False


def list_stored_keys() -> List[str]:
    """
    List providers that have stored API keys.
    
    Returns:
        List of provider names that have stored keys
    """
    if not KEYRING_AVAILABLE or keyring is None:
        return []
    
    stored_providers = []
    
    try:
        # Check each known provider
        for provider, username in PROVIDER_MAPPING.items():
            try:
                api_key = keyring.get_password(KEYRING_SERVICE, username)
                if api_key:
                    stored_providers.append(provider)
            except Exception:
                # Skip providers that cause errors
                continue
        
        return stored_providers
        
    except Exception as e:
        log_error(f"Failed to list stored keys: {e}")
        return []


def get_keyring_info() -> Dict[str, Any]:
    """
    Get information about the keyring backend.
    
    Returns:
        Dictionary with keyring information
    """
    if not KEYRING_AVAILABLE or keyring is None:
        return {
            "available": False,
            "reason": "keyring library not installed",
            "recommendation": "Install with: pip install keyring"
        }
    
    try:
        backend = keyring.get_keyring()
        backend_name = backend.__class__.__name__ if backend else "Unknown"
        
        return {
            "available": True,
            "backend": backend_name,
            "service_name": KEYRING_SERVICE,
            "supported_providers": list(PROVIDER_MAPPING.keys())
        }
        
    except Exception as e:
        return {
            "available": False,
            "reason": f"keyring error: {e}",
            "recommendation": "Check keyring installation and OS support"
        }


def prompt_and_store_key(provider: str) -> bool:
    """
    Prompt user for API key and store it securely.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic')
        
    Returns:
        True if successful, False otherwise
    """
    if not KEYRING_AVAILABLE or keyring is None:
        print("❌ Secure storage not available. Install keyring: pip install keyring")
        return False
    
    print(f"\n🔐 Secure API Key Setup for {provider.title()}")
    
    # Show provider-specific help
    provider_info = {
        "openai": {
            "name": "OpenAI", 
            "url": "https://platform.openai.com/api-keys",
            "format": "sk-..."
        },
        "anthropic": {
            "name": "Anthropic Claude",
            "url": "https://console.anthropic.com/account/keys", 
            "format": "sk-ant-..."
        },
        "google": {
            "name": "Google Gemini",
            "url": "https://makersuite.google.com/app/apikey",
            "format": "AI..."
        },
        "groq": {
            "name": "Groq",
            "url": "https://console.groq.com/keys",
            "format": "gsk_..."
        },
        "cohere": {
            "name": "Cohere",
            "url": "https://dashboard.cohere.com/api-keys",
            "format": "..."
        },
        "mistral": {
            "name": "Mistral",
            "url": "https://console.mistral.ai/api-keys/",
            "format": "..."
        }
    }
    
    info = provider_info.get(provider.lower())
    if info:
        print(f"Service: {info['name']}")
        print(f"Get your API key at: {info['url']}")
        print(f"Expected format: {info['format']}")
    
    # Securely prompt for API key
    try:
        api_key = getpass.getpass(f"Enter {provider} API key (input hidden): ").strip()
        
        if not api_key:
            print("❌ No API key provided.")
            return False
        
        # Basic validation
        if len(api_key) < 10:
            print("❌ API key seems too short. Please check and try again.")
            return False
        
        # Format validation using model registry patterns
        validation_result = validate_api_key_format(provider, api_key)
        if not validation_result["valid"]:
            print(f"❌ {validation_result['reason']}")
            if "expected_pattern" in validation_result:
                print(f"   Expected pattern: {validation_result['expected_pattern']}")
            if "setup_url" in validation_result and validation_result["setup_url"]:
                print(f"   Get correct API key at: {validation_result['setup_url']}")
            if "suggestion" in validation_result:
                print(f"   {validation_result['suggestion']}")
            
            # Ask if they want to continue anyway
            try:
                continue_anyway = input("\nStore anyway? This may cause connection failures (y/N): ").strip().lower()
                if continue_anyway not in ['y', 'yes']:
                    print("❌ Cancelled - please get a valid API key")
                    return False
            except KeyboardInterrupt:
                print("\n❌ Cancelled by user")
                return False
        else:
            print(f"✅ {validation_result['reason']}")
        
        # Store the key
        success = set_api_key(provider, api_key)
        
        if success:
            print(f"✅ API key stored securely for {provider}")
            print(f"   Stored in: {get_keyring_info()['backend']} keyring")
            return True
        else:
            print(f"❌ Failed to store API key for {provider}")
            return False
            
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """
    CLI interface for API key management.
    Can be run independently: python utilities/api_key_manager.py
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="OpenChronicle API Key Manager - Secure storage for AI provider API keys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python utilities/api_key_manager.py --set openai
  python utilities/api_key_manager.py --list
  python utilities/api_key_manager.py --remove anthropic
  python utilities/api_key_manager.py --info
  python utilities/api_key_manager.py --interactive

Supported providers:
  openai, anthropic, google/gemini, groq, cohere, mistral, huggingface, azure
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--set', type=str, metavar='PROVIDER',
                      help='Interactively set API key for provider')
    group.add_argument('--list', action='store_true',
                      help='List all stored API keys')
    group.add_argument('--remove', type=str, metavar='PROVIDER',
                      help='Remove API key for provider')
    group.add_argument('--info', action='store_true',
                      help='Show keyring backend information')
    group.add_argument('--interactive', action='store_true',
                      help='Interactive API key management mode')
    
    args = parser.parse_args()
    
    # Handle commands
    try:
        if args.set:
            success = prompt_and_store_key(args.set)
            sys.exit(0 if success else 1)
            
        elif args.list:
            keys = list_stored_keys()
            if keys:
                print("🔑 Stored API keys:")
                for provider in sorted(keys):
                    print(f"  ✅ {provider}")
                print(f"\nTotal: {len(keys)} API keys stored")
                print(f"Backend: {get_keyring_info()['backend']}")
            else:
                print("📭 No API keys stored")
                print("Use --set PROVIDER to store API keys securely.")
            
        elif args.remove:
            provider = args.remove.lower()
            if remove_api_key(provider):
                print(f"✅ Removed API key for {provider}")
            else:
                print(f"❌ No API key found for {provider}")
                
        elif args.info:
            info = get_keyring_info()
            print("🔐 Keyring Information:")
            print(f"  Backend: {info['backend']}")
            print(f"  Available: {info['available']}")
            if info['available']:
                print(f"  Service: {KEYRING_SERVICE}")
                print("\n📋 Supported providers:")
                for provider in sorted(PROVIDER_MAPPING.keys()):
                    print(f"    • {provider}")
            else:
                print("  ⚠️  Keyring not available - install with: pip install keyring")
                
        elif args.interactive:
            interactive_mode()
            
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def interactive_mode():
    """Interactive mode for API key management."""
    print("🔐 OpenChronicle API Key Manager - Interactive Mode")
    print("=" * 50)
    
    while True:
        print("\nCommands:")
        print("  1. Set API key")
        print("  2. List stored keys")
        print("  3. Remove API key") 
        print("  4. Show keyring info")
        print("  5. Exit")
        
        try:
            choice = input("\nSelect option (1-5): ").strip()
            
            if choice == '1':
                provider = input("Enter provider name: ").strip().lower()
                if provider:
                    prompt_and_store_key(provider)
                else:
                    print("❌ Invalid provider name")
                    
            elif choice == '2':
                keys = list_stored_keys()
                if keys:
                    print("\n🔑 Stored API keys:")
                    for provider in sorted(keys):
                        print(f"  ✅ {provider}")
                    print(f"\nTotal: {len(keys)} keys")
                else:
                    print("\n📭 No API keys stored")
                    
            elif choice == '3':
                provider = input("Enter provider to remove: ").strip().lower()
                if provider:
                    if remove_api_key(provider):
                        print(f"✅ Removed API key for {provider}")
                    else:
                        print(f"❌ No API key found for {provider}")
                else:
                    print("❌ Invalid provider name")
                    
            elif choice == '4':
                info = get_keyring_info()
                print(f"\n🔐 Backend: {info['backend']}")
                print(f"Available: {info['available']}")
                
            elif choice == '5':
                print("👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid option. Please select 1-5.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
