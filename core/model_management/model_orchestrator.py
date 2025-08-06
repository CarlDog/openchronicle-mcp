"""
Segregated Model Orchestrator Implementation

Implementation of the segregated model management interfaces, replacing
the monolithic ModelOrchestrator with focused, single-responsibility components.

Phase 2 Week 11-12: Interface Segregation & Architecture Cleanup
"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC

from .model_interfaces import (
    IModelOrchestrator, IModelResponseGenerator, IModelLifecycleManager,
    IModelConfigurationManager, IModelPerformanceMonitor,
    ModelResponse, AdapterStatus, ModelConfiguration
)

from core.shared.dependency_injection import DIContainer, get_container
from core.shared.error_handling import with_error_handling, ModelError, ErrorContext, ErrorSeverity
from core.shared.security_decorators import secure_operation, SecurityThreatLevel
from utilities.logging_system import log_info, log_error, log_warning

class ModelResponseGenerator(IModelResponseGenerator):
    """
    Focused implementation for model response generation.
    
    Single responsibility: Handle AI response generation and fallback logic.
    """
    
    def __init__(self, adapters: Dict[str, Any], config_manager, performance_monitor):
        self.adapters = adapters
        self.config_manager = config_manager
        self.performance_monitor = performance_monitor
        log_info("Initialized ModelResponseGenerator")
    
    @with_error_handling(
        context=ErrorContext(operation="generate_response", component="ModelResponseGenerator"),
        fallback_result=None
    )
    @secure_operation(
        input_params=['prompt'],
        require_auth=False,
        monitor_level=SecurityThreatLevel.MEDIUM
    )
    async def generate_response(
        self,
        prompt: str,
        adapter_name: str,
        model_params: Optional[Dict[str, Any]] = None,
        use_fallback: bool = True
    ) -> ModelResponse:
        """Generate response using specified adapter with fallback support."""
        start_time = datetime.now(UTC)
        
        try:
            # Check if adapter is available
            if adapter_name not in self.adapters:
                if use_fallback:
                    fallback_chain = self.get_fallback_chain(adapter_name)
                    if fallback_chain:
                        return await self.generate_with_fallback_chain(prompt, fallback_chain, model_params)
                
                raise ModelError(
                    f"Adapter {adapter_name} not available",
                    category="adapter_error",
                    severity=ErrorSeverity.HIGH,
                    context=ErrorContext(operation="generate_response", adapter=adapter_name)
                )
            
            adapter = self.adapters[adapter_name]
            
            # Generate response
            response_content = await adapter.generate_response(prompt, **(model_params or {}))
            
            # Record success metrics
            response_time = (datetime.now(UTC) - start_time).total_seconds()
            self.performance_monitor.record_response_time(adapter_name, response_time)
            self.performance_monitor.record_success(adapter_name, len(prompt), len(response_content))
            
            return ModelResponse(
                content=response_content,
                adapter_name=adapter_name,
                model_name=adapter.model_name if hasattr(adapter, 'model_name') else adapter_name,
                metadata=model_params or {},
                timestamp=datetime.now(UTC),
                success=True
            )
            
        except Exception as e:
            # Record failure metrics
            self.performance_monitor.record_failure(adapter_name, type(e).__name__, str(e))
            
            if use_fallback:
                fallback_chain = self.get_fallback_chain(adapter_name)
                if fallback_chain:
                    log_warning(f"Primary adapter {adapter_name} failed, trying fallback: {e}")
                    return await self.generate_with_fallback_chain(prompt, fallback_chain, model_params)
            
            raise ModelError(
                f"Response generation failed: {e}",
                category="generation_error",
                severity=ErrorSeverity.HIGH,
                context=ErrorContext(operation="generate_response", adapter=adapter_name),
                cause=e
            )
    
    async def generate_with_fallback_chain(
        self,
        prompt: str,
        adapter_chain: List[str],
        model_params: Optional[Dict[str, Any]] = None
    ) -> ModelResponse:
        """Generate response trying each adapter in the chain until success."""
        last_error = None
        
        for adapter_name in adapter_chain:
            try:
                return await self.generate_response(prompt, adapter_name, model_params, use_fallback=False)
            except Exception as e:
                last_error = e
                log_warning(f"Fallback adapter {adapter_name} failed: {e}")
                continue
        
        raise ModelError(
            f"All adapters in fallback chain failed. Last error: {last_error}",
            category="fallback_exhausted",
            severity=ErrorSeverity.CRITICAL,
            context=ErrorContext(operation="generate_with_fallback_chain"),
            cause=last_error
        )
    
    def get_fallback_chain(self, adapter_name: str) -> List[str]:
        """Get fallback chain for specified adapter."""
        config = self.config_manager.get_model_configuration(adapter_name)
        if config and config.fallback_chain:
            return config.fallback_chain
        
        # Default fallback logic
        available_adapters = [name for name in self.adapters.keys() if name != adapter_name]
        return available_adapters[:3]  # Limit to 3 fallbacks

class ModelLifecycleManager(IModelLifecycleManager):
    """
    Focused implementation for model adapter lifecycle management.
    
    Single responsibility: Manage adapter initialization, health, and cleanup.
    """
    
    def __init__(self, adapters: Dict[str, Any], config_manager):
        self.adapters = adapters
        self.config_manager = config_manager
        self.adapter_health = {}
        log_info("Initialized ModelLifecycleManager")
    
    @with_error_handling(
        context=ErrorContext(operation="initialize_adapter", component="ModelLifecycleManager"),
        fallback_result=False
    )
    async def initialize_adapter(self, adapter_name: str, max_retries: int = 2) -> bool:
        """Initialize a specific adapter with retry logic."""
        for attempt in range(max_retries + 1):
            try:
                # Get adapter configuration
                config = self.config_manager.get_model_configuration(adapter_name)
                if not config:
                    raise ModelError(f"No configuration found for adapter {adapter_name}")
                
                # Initialize adapter (this would be adapter-specific logic)
                # For now, we'll simulate initialization
                log_info(f"Initializing adapter {adapter_name} (attempt {attempt + 1}/{max_retries + 1})")
                
                # Simulate adapter initialization
                await asyncio.sleep(0.1)  # Simulated initialization time
                
                # Store adapter status
                self.adapter_health[adapter_name] = {
                    'status': 'healthy',
                    'last_check': datetime.now(UTC),
                    'error_count': 0,
                    'initialization_time': datetime.now(UTC)
                }
                
                log_info(f"Successfully initialized adapter {adapter_name}")
                return True
                
            except Exception as e:
                log_warning(f"Failed to initialize adapter {adapter_name} (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    self.adapter_health[adapter_name] = {
                        'status': 'failed',
                        'last_check': datetime.now(UTC),
                        'error_count': attempt + 1,
                        'last_error': str(e)
                    }
                    return False
                await asyncio.sleep(1.0 * (attempt + 1))  # Exponential backoff
        
        return False
    
    async def initialize_all_adapters(self, max_concurrent: int = 3) -> Dict[str, bool]:
        """Initialize all configured adapters with concurrency control."""
        available_configs = self.config_manager.get_available_models()
        enabled_adapters = [name for name, config in available_configs.items() if config.enabled]
        
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def initialize_with_semaphore(adapter_name: str):
            async with semaphore:
                return adapter_name, await self.initialize_adapter(adapter_name)
        
        tasks = [initialize_with_semaphore(name) for name in enabled_adapters]
        completed_tasks = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in completed_tasks:
            if isinstance(result, Exception):
                log_error(f"Error in concurrent initialization: {result}")
            else:
                adapter_name, success = result
                results[adapter_name] = success
        
        return results
    
    async def health_check_adapter(self, adapter_name: str) -> AdapterStatus:
        """Perform health check on specific adapter."""
        try:
            # Simulate health check
            await asyncio.sleep(0.05)  # Simulated health check time
            
            health_info = self.adapter_health.get(adapter_name, {})
            
            return AdapterStatus(
                name=adapter_name,
                is_available=adapter_name in self.adapters,
                is_healthy=health_info.get('status') == 'healthy',
                last_health_check=datetime.now(UTC),
                error_count=health_info.get('error_count', 0),
                success_count=health_info.get('success_count', 0),
                average_response_time=health_info.get('avg_response_time', 0.0),
                metadata=health_info
            )
            
        except Exception as e:
            return AdapterStatus(
                name=adapter_name,
                is_available=False,
                is_healthy=False,
                last_health_check=datetime.now(UTC),
                error_count=1,
                success_count=0,
                average_response_time=0.0,
                metadata={'error': str(e)}
            )
    
    async def health_check_all_adapters(self) -> Dict[str, AdapterStatus]:
        """Perform health checks on all adapters."""
        results = {}
        tasks = [self.health_check_adapter(name) for name in self.adapters.keys()]
        statuses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, status in enumerate(statuses):
            adapter_name = list(self.adapters.keys())[i]
            if isinstance(status, Exception):
                log_error(f"Health check failed for {adapter_name}: {status}")
                results[adapter_name] = AdapterStatus(
                    name=adapter_name,
                    is_available=False,
                    is_healthy=False,
                    last_health_check=datetime.now(UTC),
                    error_count=1,
                    success_count=0,
                    average_response_time=0.0,
                    metadata={'error': str(status)}
                )
            else:
                results[adapter_name] = status
        
        return results
    
    async def shutdown_adapter(self, adapter_name: str) -> bool:
        """Gracefully shutdown specific adapter."""
        try:
            # Perform graceful shutdown logic here
            if adapter_name in self.adapters:
                # Simulate shutdown
                await asyncio.sleep(0.1)
                self.adapter_health[adapter_name] = {
                    'status': 'shutdown',
                    'last_check': datetime.now(UTC),
                    'shutdown_time': datetime.now(UTC)
                }
                log_info(f"Successfully shutdown adapter {adapter_name}")
                return True
            return False
        except Exception as e:
            log_error(f"Failed to shutdown adapter {adapter_name}: {e}")
            return False
    
    async def restart_adapter(self, adapter_name: str) -> bool:
        """Restart specific adapter with health validation."""
        try:
            # Shutdown first
            await self.shutdown_adapter(adapter_name)
            await asyncio.sleep(0.5)  # Wait for clean shutdown
            
            # Reinitialize
            success = await self.initialize_adapter(adapter_name)
            if success:
                # Perform health check
                status = await self.health_check_adapter(adapter_name)
                return status.is_healthy
            return False
        except Exception as e:
            log_error(f"Failed to restart adapter {adapter_name}: {e}")
            return False
    
    def is_adapter_available(self, adapter_name: str) -> bool:
        """Check if adapter is available for use."""
        return adapter_name in self.adapters
    
    def is_adapter_healthy(self, adapter_name: str) -> bool:
        """Check if adapter is healthy and responsive."""
        health_info = self.adapter_health.get(adapter_name, {})
        return health_info.get('status') == 'healthy'

class ModelOrchestrator(IModelOrchestrator):
    """
    Modern model orchestrator that composes focused interfaces.
    
    Provides facade pattern access to all model management capabilities
    while maintaining clean separation of concerns using SOLID principles.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._init_config = config or {}  # Store init config separately
        self.adapters = {}
        
        # Initialize components using DI container
        container = get_container()
        
        # Register and resolve configuration manager first
        from .configuration_manager import ConfigurationManager
        config_manager = ConfigurationManager()
        container.register_singleton('model_config_manager', config_manager)
        
        # Register and resolve performance monitor
        from .performance_monitor import PerformanceMonitor
        performance_monitor = PerformanceMonitor(self.adapters, self._init_config)
        container.register_singleton('model_performance_monitor', performance_monitor)
        
        # Create segregated components
        self._response_generator = ModelResponseGenerator(
            self.adapters, config_manager, performance_monitor
        )
        self._lifecycle_manager = ModelLifecycleManager(
            self.adapters, config_manager
        )
        self._configuration_manager = config_manager
        self._performance_monitor = performance_monitor
        
        # Compatibility attributes for tests
        self.config_manager = config_manager
        
        log_info("Initialized ModelOrchestrator with component-based architecture")
    
    # Interface property accessors
    @property
    def response_generator(self) -> IModelResponseGenerator:
        """Access to response generation interface."""
        return self._response_generator
    
    @property
    def lifecycle_manager(self) -> IModelLifecycleManager:
        """Access to lifecycle management interface."""
        return self._lifecycle_manager
    
    @property
    def configuration_manager(self) -> IModelConfigurationManager:
        """Access to configuration management interface."""
        return self._configuration_manager
    
    @property
    def performance_monitor(self) -> IModelPerformanceMonitor:
        """Access to performance monitoring interface."""
        return self._performance_monitor
    
    # Convenience methods that delegate to appropriate interfaces
    async def generate_response(self, prompt: str, adapter_name: str = None, **kwargs) -> ModelResponse:
        """Convenience method for response generation."""
        # If no adapter specified, use default
        if not adapter_name:
            adapter_name = getattr(self, 'default_adapter', 'gpt-4-turbo')
        return await self._response_generator.generate_response(prompt, adapter_name, **kwargs)
    
    async def initialize_adapter(self, adapter_name: str) -> bool:
        """Convenience method for adapter initialization."""
        return await self._lifecycle_manager.initialize_adapter(adapter_name)
    
    async def initialize_adapter_safe(self, adapter_name: str) -> bool:
        """Safe adapter initialization with error handling."""
        try:
            return await self.initialize_adapter(adapter_name)
        except Exception as e:
            log_error(f"Failed to initialize adapter {adapter_name}: {e}")
            return False
    
    def get_adapter_status(self, adapter_name: str) -> AdapterStatus:
        """Convenience method for adapter status."""
        import asyncio
        return asyncio.run(self._lifecycle_manager.health_check_adapter(adapter_name))
    
    def get_available_adapters(self) -> Dict[str, Any]:
        """Get available adapters from configuration."""
        return self._configuration_manager.list_model_configs()
    
    def get_adapter_info(self, adapter_name: str) -> Dict[str, Any]:
        """Get adapter information."""
        configs = self._configuration_manager.get_available_models()
        return configs.get(adapter_name, {})
    
    async def shutdown(self):
        """Shutdown all adapters."""
        for adapter_name in list(self.adapters.keys()):
            await self._lifecycle_manager.shutdown_adapter(adapter_name)
    
    # Configuration properties
    @property 
    def config(self) -> Dict[str, Any]:
        """Access to configuration."""
        return self._configuration_manager.config if hasattr(self._configuration_manager, 'config') else {}
    
    @property
    def default_adapter(self) -> str:
        """Get/set default adapter."""
        return getattr(self, '_default_adapter', 'gpt-4-turbo')
    
    @default_adapter.setter  
    def default_adapter(self, adapter_name: str):
        """Set default adapter."""
        self._default_adapter = adapter_name
    
    def add_model_config(self, provider_name: str, config: Dict[str, Any]) -> bool:
        """Convenience method for adding model configuration."""
        model_config = ModelConfiguration(
            provider_name=provider_name,
            model_name=config.get('model_name', provider_name),
            enabled=config.get('enabled', True),
            config=config,
            fallback_chain=config.get('fallback_chain', []),
            metadata=config.get('metadata', {})
        )
        return self._configuration_manager.add_model_configuration(model_config)
