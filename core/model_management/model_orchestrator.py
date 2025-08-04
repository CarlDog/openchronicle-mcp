"""
ModelOrchestrator - Clean replacement for ModelManager monolith.

This orchestrator integrates all extracted components to provide a unified
interface for model management while maintaining backward compatibility.
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, UTC

# Import our extracted components
from .response_generator import ResponseGenerator
from .lifecycle_manager import LifecycleManager 
from .performance_monitor import PerformanceMonitor
from .configuration_manager import ConfigurationManager

# Import logging system
from utilities.logging_system import log_system_event, log_info, log_error, log_warning


class ModelOrchestrator:
    """
    Clean, modular replacement for the ModelManager monolith.
    
    Orchestrates specialized components to provide unified model management:
    - ResponseGenerator: Handles all response generation logic
    - LifecycleManager: Manages adapter initialization, health, and cleanup
    - PerformanceMonitor: Tracks metrics, analytics, and monitoring
    - ConfigurationManager: Handles configuration loading and validation
    """
    
    def __init__(self):
        """Initialize the ModelOrchestrator with all component managers."""
        log_info("Initializing ModelOrchestrator with component-based architecture")
        
        # Initialize all component managers
        self.config_manager = ConfigurationManager()
        self.lifecycle_manager = LifecycleManager(self.config_manager)
        self.performance_monitor = PerformanceMonitor()
        self.response_generator = ResponseGenerator(
            lifecycle_manager=self.lifecycle_manager,
            performance_monitor=self.performance_monitor
        )
        
        # Direct access to component properties (no legacy cruft)
        self.initialized = True
        
        # Initialize all components
        self._initialize_components()
        
        log_system_event(
            "orchestrator_initialized",
            f"ModelOrchestrator ready with {len(self.adapters)} adapters available"
        )
    
    def _initialize_components(self):
        """Initialize all component managers in proper order."""
        try:
            # Configuration loading happens in ConfigurationManager.__init__
            log_info("Configuration loaded successfully")
            
            # Performance monitoring setup
            self.performance_monitor.start_monitoring()
            log_info("Performance monitoring started")
            
            # Adapter validation (lifecycle manager handles this)
            valid_adapters = self.lifecycle_manager.get_available_adapters()
            log_info(f"Found {len(valid_adapters)} available adapters: {list(valid_adapters.keys())}")
            
        except Exception as e:
            log_error(f"Component initialization failed: {e}")
            raise
    
    # ===== CLEAN API (No Legacy Cruft) =====
    
    async def initialize_adapter(self, name: str, max_retries: int = 2, graceful_degradation: bool = True) -> bool:
        """Initialize a specific adapter."""
        return await self.lifecycle_manager.initialize_adapter(name, max_retries, graceful_degradation)
    
    async def initialize_adapter_safe(self, name: str) -> bool:
        """Safely initialize adapter with comprehensive error handling."""
        return await self.lifecycle_manager.initialize_adapter_safe(name)
    
    async def generate_response(
        self, 
        prompt: str, 
        adapter_name: Optional[str] = None, 
        story_id: Optional[str] = None, 
        **kwargs
    ) -> str:
        """Generate response using the ResponseGenerator component."""
        return await self.response_generator.generate_response(
            prompt=prompt,
            adapter_name=adapter_name,
            story_id=story_id,
            **kwargs
        )
    
    def get_available_adapters(self) -> Dict[str, Any]:
        """Get all available (not disabled) adapters."""
        return self.lifecycle_manager.get_available_adapters()
    
    def get_enabled_adapters(self) -> List[str]:
        """Get list of enabled adapter names."""
        return self.lifecycle_manager.get_enabled_adapters()
    
    def get_adapter_status(self, adapter_name: str) -> Dict[str, Any]:
        """Get detailed status information for an adapter."""
        return self.lifecycle_manager.get_adapter_status(adapter_name)
    
    def get_fallback_chain(self, adapter_name: str) -> List[str]:
        """Get fallback chain for an adapter."""
        return self.config_manager.get_fallback_chain(adapter_name)
    
    def is_adapter_available(self, adapter_name: str) -> bool:
        """Check if adapter is available and enabled."""
        return self.lifecycle_manager.is_adapter_available(adapter_name)
    
    def is_adapter_healthy(self, adapter_name: str) -> bool:
        """Check if adapter is healthy and operational."""
        return self.lifecycle_manager.is_adapter_healthy(adapter_name)
    
    # ===== CONFIGURATION MANAGEMENT =====
    
    def add_model_config(self, provider_name: str, config: Dict[str, Any]) -> bool:
        """Add a new model configuration."""
        return self.config_manager.add_model_config(provider_name, config)
    
    def remove_model_config(self, provider_name: str) -> bool:
        """Remove a model configuration."""
        return self.config_manager.remove_model_config(provider_name)
    
    def update_model_config(self, provider_name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing model configuration."""
        return self.config_manager.update_model_config(provider_name, updates)
    
    def validate_model_config(self, config: Dict[str, Any]) -> bool:
        """Validate a model configuration."""
        return self.config_manager.validate_model_config(config)
    
    def enable_model(self, provider_name: str) -> bool:
        """Enable a model adapter."""
        result = self.config_manager.enable_model(provider_name)
        if result:
            # Update lifecycle manager
            self.lifecycle_manager.refresh_available_adapters()
        return result
    
    def disable_model(self, provider_name: str) -> bool:
        """Disable a model adapter.""" 
        result = self.config_manager.disable_model(provider_name)
        if result:
            # Update lifecycle manager and clean up
            self.lifecycle_manager.cleanup_adapter(provider_name)
            self.lifecycle_manager.refresh_available_adapters()
        return result
    
    def export_configuration(self, output_path: Optional[str] = None) -> str:
        """Export current configuration to file."""
        return self.config_manager.export_configuration(output_path)
    
    # ===== PERFORMANCE MONITORING =====
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        return self.performance_monitor.get_performance_stats()
    
    def get_adapter_metrics(self, adapter_name: str) -> Dict[str, Any]:
        """Get performance metrics for specific adapter."""
        return self.performance_monitor.get_adapter_metrics(adapter_name)
    
    def start_performance_monitoring(self):
        """Start performance monitoring."""
        self.performance_monitor.start_monitoring()
    
    def stop_performance_monitoring(self):
        """Stop performance monitoring."""
        self.performance_monitor.stop_monitoring()
    
    def reset_performance_stats(self):
        """Reset all performance statistics."""
        self.performance_monitor.reset_stats()
    
    # ===== LIFECYCLE MANAGEMENT =====
    
    async def cleanup_adapter(self, adapter_name: str):
        """Clean up a specific adapter."""
        await self.lifecycle_manager.cleanup_adapter(adapter_name)
    
    async def cleanup_all_adapters(self):
        """Clean up all adapters."""
        await self.lifecycle_manager.cleanup_all_adapters()
    
    async def restart_adapter(self, adapter_name: str) -> bool:
        """Restart a specific adapter."""
        return await self.lifecycle_manager.restart_adapter(adapter_name)
    
    async def health_check_all_adapters(self) -> Dict[str, bool]:
        """Perform health check on all adapters."""
        return await self.lifecycle_manager.health_check_all_adapters()
    
    def refresh_available_adapters(self):
        """Refresh the list of available adapters."""
        self.lifecycle_manager.refresh_available_adapters()
    
    # ===== SYSTEM STATUS & CONTROL =====
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            "orchestrator": {
                "initialized": True,
                "components": {
                    "configuration_manager": True,
                    "lifecycle_manager": True,
                    "performance_monitor": True,
                    "response_generator": True
                }
            },
            "configuration": {
                "total_providers": len(self.config_manager.get_all_providers()),
                "enabled_providers": len(self.get_enabled_adapters()),
                "default_adapter": self.config_manager.default_adapter
            },
            "lifecycle": {
                "initialized_adapters": len(self.lifecycle_manager.initialized_adapters),
                "healthy_adapters": len([name for name in self.lifecycle_manager.adapters.keys() if self.is_adapter_healthy(name)]),
                "total_adapters": len(self.lifecycle_manager.adapters)
            },
            "performance": {
                "monitoring_active": self.performance_monitor.is_monitoring_active(),
                "total_requests": self.performance_monitor.get_total_requests(),
                "uptime_seconds": self.performance_monitor.get_uptime_seconds()
            }
        }
    
    # ===== CLEANUP =====
    
    async def shutdown(self):
        """Gracefully shutdown the orchestrator and all components."""
        log_info("Shutting down ModelOrchestrator")
        
        try:
            # Stop performance monitoring
            self.performance_monitor.stop_monitoring()
            
            # Cleanup all adapters
            await self.lifecycle_manager.cleanup_all_adapters()
            
            # Export final configuration state
            self.config_manager.export_configuration()
            
            log_system_event("orchestrator_shutdown", "ModelOrchestrator shutdown completed")
            
        except Exception as e:
            log_error(f"Error during orchestrator shutdown: {e}")
            raise
    
    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'performance_monitor') and self.performance_monitor:
            try:
                self.performance_monitor.stop_monitoring()
            except:
                pass  # Best effort cleanup


def create_model_orchestrator() -> ModelOrchestrator:
    """Factory function to create ModelOrchestrator instance."""
    return ModelOrchestrator()
