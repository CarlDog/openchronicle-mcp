"""
Model Orchestrator - Replaces the monolithic ModelManager with clean separation of concerns.

This class coordinates between the registry, adapter factory, and content routing
to provide a lightweight, modular replacement for the original 4,473-line ModelManager.

Key Features:
- ~200 lines vs original thousands
- Registry-aware adapter management 
- Content-based routing using registry rules
- Health monitoring and fallback chain management
- Dynamic model discovery (especially for Ollama)
- Clean separation of registry, factory, and orchestration concerns
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, UTC

from utilities.logging_system import log_info, log_error, log_system_event
from .registry import RegistryManager
from ..adapters.factory import AdapterFactory
from ..adapters.exceptions import AdapterInitializationError, AdapterConnectionError

logger = logging.getLogger(__name__)


class ModelOrchestrator:
    """
    Lightweight orchestrator that replaces the monolithic ModelManager.
    
    Coordinates between registry, factory, and adapters to provide:
    - Dynamic adapter management
    - Content-based routing
    - Health monitoring
    - Fallback chain management
    """
    
    def __init__(self, registry_manager: RegistryManager, adapter_factory: AdapterFactory):
        self.registry_manager = registry_manager
        self.adapter_factory = adapter_factory
        self.active_adapters: Dict[str, Any] = {}
        self.health_status: Dict[str, bool] = {}
        self.last_health_check: Dict[str, datetime] = {}
        
        # Load initial configuration
        self.providers = self.registry_manager.get_available_providers()
        self.fallback_chains = self.registry_manager.get_fallback_chains()
        
        log_info("ModelOrchestrator initialized with registry-aware configuration")
    
    async def initialize_adapter(self, adapter_name: str, force_reinit: bool = False) -> bool:
        """
        Initialize an adapter using the factory with registry configuration.
        
        Args:
            adapter_name: Name of the adapter to initialize
            force_reinit: Whether to force reinitialization if already active
            
        Returns:
            bool: Success status
        """
        if adapter_name in self.active_adapters and not force_reinit:
            log_info(f"Adapter {adapter_name} already initialized")
            return True
            
        try:
            # Get enhanced config from registry
            provider_config = self.registry_manager.get_provider_config(adapter_name)
            if not provider_config:
                log_error(f"No registry configuration found for {adapter_name}")
                return False
            
            # Create adapter with registry-enhanced configuration
            adapter = await self.adapter_factory.create_adapter(adapter_name, provider_config)
            
            # Initialize the adapter
            success = await adapter.initialize()
            if success:
                self.active_adapters[adapter_name] = adapter
                self.health_status[adapter_name] = True
                self.last_health_check[adapter_name] = datetime.now(UTC)
                log_info(f"Successfully initialized adapter: {adapter_name}")
                
                # Log system event for tracking
                log_system_event("adapter_initialized", f"Adapter {adapter_name} initialized successfully")
                return True
            else:
                log_error(f"Failed to initialize adapter: {adapter_name}")
                return False
                
        except Exception as e:
            log_error(f"Exception initializing adapter {adapter_name}: {e}")
            self.health_status[adapter_name] = False
            return False
    
    async def get_adapter_for_content(self, content_type: str, model_preference: Optional[str] = None) -> Optional[Any]:
        """
        Get the best adapter for content type using registry routing rules.
        
        Args:
            content_type: Type of content (e.g., 'narrative', 'dialogue', 'image')
            model_preference: Preferred model name if specified
            
        Returns:
            Adapter instance or None
        """
        # Check for specific model preference first
        if model_preference and model_preference in self.active_adapters:
            adapter = self.active_adapters[model_preference]
            if self.health_status.get(model_preference, False):
                return adapter
        
        # Use registry content routing
        recommended_providers = self.registry_manager.get_content_routing_recommendations(content_type)
        
        for provider in recommended_providers:
            if provider in self.active_adapters and self.health_status.get(provider, False):
                log_info(f"Selected {provider} for content type: {content_type}")
                return self.active_adapters[provider]
            
            # Try to initialize if not active
            if await self.initialize_adapter(provider):
                return self.active_adapters[provider]
        
        # Fallback to any healthy adapter
        for adapter_name, adapter in self.active_adapters.items():
            if self.health_status.get(adapter_name, False):
                log_info(f"Using fallback adapter {adapter_name} for content type: {content_type}")
                return adapter
        
        log_error(f"No healthy adapters available for content type: {content_type}")
        return None
    
    async def generate_response(self, prompt: str, content_type: str = "narrative", 
                              model_preference: Optional[str] = None, **kwargs) -> Optional[str]:
        """
        Generate response using content-aware adapter selection.
        
        Args:
            prompt: Input prompt
            content_type: Type of content for routing
            model_preference: Preferred model if specified
            **kwargs: Additional arguments for generation
            
        Returns:
            Generated response or None
        """
        adapter = await self.get_adapter_for_content(content_type, model_preference)
        if not adapter:
            return None
        
        try:
            response = await adapter.generate_response(prompt, **kwargs)
            
            # Log successful interaction
            if hasattr(adapter, 'model_name'):
                log_system_event("response_generated", f"Generated response using {adapter.model_name}")
            
            return response
            
        except Exception as e:
            log_error(f"Error generating response: {e}")
            
            # Try fallback chain
            adapter_name = getattr(adapter, 'provider_name', 'unknown')
            fallback_chain = self.fallback_chains.get(adapter_name, [])
            
            for fallback_adapter_name in fallback_chain:
                try:
                    if fallback_adapter_name not in self.active_adapters:
                        await self.initialize_adapter(fallback_adapter_name)
                    
                    fallback_adapter = self.active_adapters.get(fallback_adapter_name)
                    if fallback_adapter and self.health_status.get(fallback_adapter_name, False):
                        log_info(f"Trying fallback adapter: {fallback_adapter_name}")
                        response = await fallback_adapter.generate_response(prompt, **kwargs)
                        return response
                        
                except Exception as fallback_error:
                    log_error(f"Fallback adapter {fallback_adapter_name} also failed: {fallback_error}")
                    continue
            
            return None
    
    async def health_check_all(self) -> Dict[str, bool]:
        """
        Perform health checks on all active adapters.
        
        Returns:
            Dict mapping adapter names to health status
        """
        health_results = {}
        
        for adapter_name, adapter in self.active_adapters.items():
            try:
                # Check if adapter has health_check method
                if hasattr(adapter, 'health_check'):
                    is_healthy = await adapter.health_check()
                else:
                    # Basic health check - just verify adapter is initialized
                    is_healthy = getattr(adapter, 'initialized', False)
                
                health_results[adapter_name] = is_healthy
                self.health_status[adapter_name] = is_healthy
                self.last_health_check[adapter_name] = datetime.now(UTC)
                
                if not is_healthy:
                    log_error(f"Health check failed for adapter: {adapter_name}")
                    
            except Exception as e:
                log_error(f"Health check error for {adapter_name}: {e}")
                health_results[adapter_name] = False
                self.health_status[adapter_name] = False
        
        # Log overall health status
        healthy_count = sum(1 for status in health_results.values() if status)
        total_count = len(health_results)
        log_system_event("health_check_completed", f"{healthy_count}/{total_count} adapters healthy")
        
        return health_results
    
    async def discover_ollama_models(self) -> List[str]:
        """
        Discover available Ollama models dynamically.
        
        Returns:
            List of available model names
        """
        try:
            # Check if Ollama adapter is available
            if 'ollama' not in self.active_adapters:
                await self.initialize_adapter('ollama')
            
            ollama_adapter = self.active_adapters.get('ollama')
            if ollama_adapter and hasattr(ollama_adapter, 'discover_models'):
                models = await ollama_adapter.discover_models()
                log_info(f"Discovered {len(models)} Ollama models")
                return models
            else:
                log_info("Ollama adapter does not support model discovery")
                return []
                
        except Exception as e:
            log_error(f"Failed to discover Ollama models: {e}")
            return []
    
    def get_orchestrator_info(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator status."""
        return {
            "active_adapters": list(self.active_adapters.keys()),
            "health_status": self.health_status.copy(),
            "last_health_check": {k: v.isoformat() for k, v in self.last_health_check.items()},
            "available_providers": self.providers,
            "fallback_chains": self.fallback_chains,
            "registry_status": "active" if self.registry_manager else "inactive"
        }
    
    async def shutdown(self):
        """Clean shutdown of all adapters."""
        log_info("Shutting down ModelOrchestrator...")
        
        for adapter_name, adapter in self.active_adapters.items():
            try:
                if hasattr(adapter, 'shutdown'):
                    await adapter.shutdown()
                log_info(f"Shut down adapter: {adapter_name}")
            except Exception as e:
                log_error(f"Error shutting down adapter {adapter_name}: {e}")
        
        self.active_adapters.clear()
        self.health_status.clear()
        self.last_health_check.clear()
        
        log_system_event("orchestrator_shutdown", "ModelOrchestrator shut down successfully")
