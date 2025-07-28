"""
API key management using OS keyring.
Provides secure storage for AI provider API keys with graceful fallback.
"""

import getpass
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
