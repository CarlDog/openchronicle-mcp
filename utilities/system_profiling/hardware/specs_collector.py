#!/usr/bin/env python3
"""
OpenChronicle System Specs Collector

Hardware specification collection implementation following SOLID principles.
Focused responsibility: Collect comprehensive system hardware information.
"""

import platform
import sys
import os
import shutil
from typing import Dict, Any
from datetime import datetime

from ..interfaces import ISystemSpecsCollector, SystemSpecs

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import cpuinfo
    CPUINFO_AVAILABLE = True
except ImportError:
    CPUINFO_AVAILABLE = False


class SystemSpecsCollector(ISystemSpecsCollector):
    """Production implementation of system hardware specification collection."""
    
    def __init__(self):
        self._cache_duration_seconds = 60  # Cache specs for 1 minute
        self._cached_specs = None
        self._cache_timestamp = None
        
    def collect_system_specs(self) -> SystemSpecs:
        """
        Collect comprehensive system hardware specifications.
        Uses caching to avoid repeated expensive operations.
        """
        # Check cache validity
        if (self._cached_specs and self._cache_timestamp and 
            (datetime.now() - self._cache_timestamp).total_seconds() < self._cache_duration_seconds):
            return self._cached_specs
            
        # Collect fresh specs
        cpu_info = self.get_cpu_info()
        memory_info = self.get_memory_info()
        disk_info = self.get_disk_info()
        platform_info = self.get_platform_info()
        
        specs = SystemSpecs(
            cpu_cores=cpu_info.get('logical_cores', 1),
            cpu_physical_cores=cpu_info.get('physical_cores', 1),
            cpu_frequency_max=cpu_info.get('max_frequency_mhz', 0.0),
            cpu_frequency_current=cpu_info.get('current_frequency_mhz', 0.0),
            cpu_brand=cpu_info.get('brand', 'Unknown'),
            total_memory=memory_info.get('total_gb', 0.0),
            available_memory=memory_info.get('available_gb', 0.0),
            memory_usage_percent=memory_info.get('usage_percent', 0.0),
            platform=platform_info.get('platform', 'Unknown'),
            architecture=platform_info.get('architecture', 'Unknown'),
            python_version=platform_info.get('python_version', 'Unknown'),
            disk_space_gb=disk_info.get('total_gb', 0.0),
            disk_usage_percent=disk_info.get('usage_percent', 0.0)
        )
        
        # Update cache
        self._cached_specs = specs
        self._cache_timestamp = datetime.now()
        
        return specs
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get detailed CPU information using available libraries."""
        cpu_info = {}
        
        if PSUTIL_AVAILABLE:
            # Get core counts
            cpu_info['logical_cores'] = psutil.cpu_count(logical=True) or 1
            cpu_info['physical_cores'] = psutil.cpu_count(logical=False) or 1
            
            # Get frequency information
            try:
                freq = psutil.cpu_freq()
                if freq:
                    cpu_info['max_frequency_mhz'] = freq.max or 0.0
                    cpu_info['current_frequency_mhz'] = freq.current or 0.0
                else:
                    cpu_info['max_frequency_mhz'] = 0.0
                    cpu_info['current_frequency_mhz'] = 0.0
            except (AttributeError, OSError):
                cpu_info['max_frequency_mhz'] = 0.0
                cpu_info['current_frequency_mhz'] = 0.0
        else:
            # Fallback without psutil
            cpu_info['logical_cores'] = os.cpu_count() or 1
            cpu_info['physical_cores'] = os.cpu_count() or 1
            cpu_info['max_frequency_mhz'] = 0.0
            cpu_info['current_frequency_mhz'] = 0.0
        
        # Get CPU brand
        if CPUINFO_AVAILABLE:
            try:
                info = cpuinfo.get_cpu_info()
                cpu_info['brand'] = info.get('brand_raw', 'Unknown CPU')
            except Exception:
                cpu_info['brand'] = 'Unknown CPU'
        else:
            # Fallback brand detection
            cpu_info['brand'] = platform.processor() or 'Unknown CPU'
        
        return cpu_info
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get detailed memory information."""
        memory_info = {}
        
        if PSUTIL_AVAILABLE:
            try:
                mem = psutil.virtual_memory()
                memory_info['total_gb'] = round(mem.total / (1024**3), 2)
                memory_info['available_gb'] = round(mem.available / (1024**3), 2)
                memory_info['usage_percent'] = round(mem.percent, 1)
                memory_info['used_gb'] = round(mem.used / (1024**3), 2)
            except Exception:
                memory_info['total_gb'] = 0.0
                memory_info['available_gb'] = 0.0
                memory_info['usage_percent'] = 0.0
                memory_info['used_gb'] = 0.0
        else:
            # Basic fallback without psutil
            memory_info['total_gb'] = 0.0
            memory_info['available_gb'] = 0.0
            memory_info['usage_percent'] = 0.0
            memory_info['used_gb'] = 0.0
        
        return memory_info
    
    def get_disk_info(self) -> Dict[str, Any]:
        """Get disk usage information for the current directory."""
        disk_info = {}
        
        try:
            if PSUTIL_AVAILABLE:
                # Get disk usage for current working directory
                usage = psutil.disk_usage(os.getcwd())
                disk_info['total_gb'] = round(usage.total / (1024**3), 2)
                disk_info['used_gb'] = round(usage.used / (1024**3), 2)
                disk_info['free_gb'] = round(usage.free / (1024**3), 2)
                disk_info['usage_percent'] = round((usage.used / usage.total) * 100, 1)
            else:
                # Fallback using shutil
                total, used, free = shutil.disk_usage(os.getcwd())
                disk_info['total_gb'] = round(total / (1024**3), 2)
                disk_info['used_gb'] = round(used / (1024**3), 2)
                disk_info['free_gb'] = round(free / (1024**3), 2)
                disk_info['usage_percent'] = round((used / total) * 100, 1)
        except Exception:
            disk_info['total_gb'] = 0.0
            disk_info['used_gb'] = 0.0
            disk_info['free_gb'] = 0.0
            disk_info['usage_percent'] = 0.0
        
        return disk_info
    
    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform and architecture information."""
        platform_info = {}
        
        try:
            platform_info['platform'] = platform.system()
            platform_info['platform_release'] = platform.release()
            platform_info['platform_version'] = platform.version()
            platform_info['architecture'] = platform.machine()
            platform_info['processor'] = platform.processor()
            platform_info['python_version'] = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            platform_info['python_implementation'] = platform.python_implementation()
            platform_info['hostname'] = platform.node()
        except Exception:
            # Safe fallbacks
            platform_info['platform'] = 'Unknown'
            platform_info['platform_release'] = 'Unknown'
            platform_info['platform_version'] = 'Unknown'
            platform_info['architecture'] = 'Unknown'
            platform_info['processor'] = 'Unknown'
            platform_info['python_version'] = f"{sys.version_info.major}.{sys.version_info.minor}"
            platform_info['python_implementation'] = 'Unknown'
            platform_info['hostname'] = 'Unknown'
        
        return platform_info


class MockSystemSpecsCollector(ISystemSpecsCollector):
    """Mock implementation for testing purposes."""
    
    def __init__(self, mock_specs: SystemSpecs = None):
        self.mock_specs = mock_specs or SystemSpecs(
            cpu_cores=8,
            cpu_physical_cores=4,
            cpu_frequency_max=3200.0,
            cpu_frequency_current=2800.0,
            cpu_brand="Mock CPU",
            total_memory=16.0,
            available_memory=8.0,
            memory_usage_percent=50.0,
            platform="Mock OS",
            architecture="x64",
            python_version="3.9.0",
            disk_space_gb=500.0,
            disk_usage_percent=60.0
        )
    
    def collect_system_specs(self) -> SystemSpecs:
        """Return mock system specifications."""
        return self.mock_specs
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Return mock CPU information."""
        return {
            'logical_cores': self.mock_specs.cpu_cores,
            'physical_cores': self.mock_specs.cpu_physical_cores,
            'max_frequency_mhz': self.mock_specs.cpu_frequency_max,
            'current_frequency_mhz': self.mock_specs.cpu_frequency_current,
            'brand': self.mock_specs.cpu_brand
        }
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Return mock memory information."""
        return {
            'total_gb': self.mock_specs.total_memory,
            'available_gb': self.mock_specs.available_memory,
            'usage_percent': self.mock_specs.memory_usage_percent,
            'used_gb': self.mock_specs.total_memory - self.mock_specs.available_memory
        }
    
    def get_disk_info(self) -> Dict[str, Any]:
        """Return mock disk information."""
        used_gb = self.mock_specs.disk_space_gb * (self.mock_specs.disk_usage_percent / 100)
        return {
            'total_gb': self.mock_specs.disk_space_gb,
            'used_gb': used_gb,
            'free_gb': self.mock_specs.disk_space_gb - used_gb,
            'usage_percent': self.mock_specs.disk_usage_percent
        }
    
    def get_platform_info(self) -> Dict[str, Any]:
        """Return mock platform information."""
        return {
            'platform': self.mock_specs.platform,
            'architecture': self.mock_specs.architecture,
            'python_version': self.mock_specs.python_version,
            'platform_release': 'Mock Release',
            'platform_version': 'Mock Version',
            'processor': 'Mock Processor',
            'python_implementation': 'CPython',
            'hostname': 'mock-host'
        }
