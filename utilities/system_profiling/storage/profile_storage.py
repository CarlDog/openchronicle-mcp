#!/usr/bin/env python3
"""
OpenChronicle Profile Data Storage

System profile storage implementation following SOLID principles.
Focused responsibility: Persist and retrieve system profiling data.
"""

import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from ..interfaces import IProfileDataStorage, SystemProfile


class ProfileDataStorage(IProfileDataStorage):
    """Production implementation of system profile data storage."""
    
    def __init__(self, storage_directory: str = "storage/profiles"):
        self.storage_directory = Path(storage_directory)
        self.storage_directory.mkdir(parents=True, exist_ok=True)
        self._ensure_storage_structure()
    
    def save_profile(self, profile: SystemProfile, filepath: Optional[str] = None) -> str:
        """
        Save system profile to storage with automatic naming if no filepath provided.
        
        Args:
            profile: SystemProfile to save
            filepath: Optional custom filepath, auto-generated if None
            
        Returns:
            Path where profile was saved
        """
        if filepath is None:
            # Generate filename based on timestamp
            timestamp = profile.profile_timestamp.strftime("%Y%m%d_%H%M%S")
            system_tier = profile.system_tier
            filename = f"profile_{system_tier}_{timestamp}.json"
            filepath = self.storage_directory / filename
        else:
            filepath = Path(filepath)
            if not filepath.is_absolute():
                filepath = self.storage_directory / filepath
        
        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert profile to serializable format
        profile_data = self._profile_to_dict(profile)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False, default=self._json_serializer)
            
            return str(filepath)
            
        except Exception as e:
            raise IOError(f"Failed to save profile to {filepath}: {str(e)}")
    
    def load_profile(self, filepath: str) -> Optional[SystemProfile]:
        """
        Load system profile from storage.
        
        Args:
            filepath: Path to profile file
            
        Returns:
            SystemProfile if successful, None if file not found or invalid
        """
        filepath = Path(filepath)
        if not filepath.is_absolute():
            filepath = self.storage_directory / filepath
        
        if not filepath.exists():
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            
            return self._dict_to_profile(profile_data)
            
        except Exception as e:
            print(f"Warning: Failed to load profile from {filepath}: {str(e)}")
            return None
    
    def list_saved_profiles(self) -> List[str]:
        """
        List all saved profile files.
        
        Returns:
            List of relative file paths from storage directory
        """
        try:
            profile_files = []
            
            # Find all JSON files in storage directory and subdirectories
            for filepath in self.storage_directory.rglob("*.json"):
                # Return relative path from storage directory
                relative_path = filepath.relative_to(self.storage_directory)
                profile_files.append(str(relative_path))
            
            return sorted(profile_files)
            
        except Exception as e:
            print(f"Warning: Failed to list profiles: {str(e)}")
            return []
    
    def delete_profile(self, filepath: str) -> bool:
        """
        Delete a saved profile.
        
        Args:
            filepath: Path to profile file to delete
            
        Returns:
            True if successful, False otherwise
        """
        filepath = Path(filepath)
        if not filepath.is_absolute():
            filepath = self.storage_directory / filepath
        
        try:
            if filepath.exists():
                filepath.unlink()
                return True
            return False
            
        except Exception as e:
            print(f"Warning: Failed to delete profile {filepath}: {str(e)}")
            return False
    
    def get_profile_metadata(self, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a saved profile without loading full data.
        
        Args:
            filepath: Path to profile file
            
        Returns:
            Dictionary with metadata or None if file not found
        """
        filepath = Path(filepath)
        if not filepath.is_absolute():
            filepath = self.storage_directory / filepath
        
        if not filepath.exists():
            return None
        
        try:
            # Get file metadata
            stat = filepath.stat()
            
            metadata = {
                'filepath': str(filepath),
                'filename': filepath.name,
                'size_bytes': stat.st_size,
                'created_timestamp': datetime.fromtimestamp(stat.st_ctime),
                'modified_timestamp': datetime.fromtimestamp(stat.st_mtime),
            }
            
            # Try to extract some profile data without full parsing
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                metadata.update({
                    'profile_timestamp': data.get('profile_timestamp'),
                    'system_tier': data.get('system_tier'),
                    'benchmark_count': len(data.get('benchmarks', [])),
                    'recommendation_count': len(data.get('recommendations', [])),
                })
                
                # Extract basic system specs
                system_specs = data.get('system_specs', {})
                metadata.update({
                    'cpu_cores': system_specs.get('cpu_cores'),
                    'total_memory_gb': system_specs.get('total_memory'),
                    'platform': system_specs.get('platform'),
                })
                
            except Exception:
                # If JSON parsing fails, just return file metadata
                pass
            
            return metadata
            
        except Exception as e:
            print(f"Warning: Failed to get metadata for {filepath}: {str(e)}")
            return None
    
    def _ensure_storage_structure(self):
        """Ensure storage directory structure exists."""
        try:
            # Create subdirectories for organization
            (self.storage_directory / "recent").mkdir(exist_ok=True)
            (self.storage_directory / "archived").mkdir(exist_ok=True)
            
            # Create index file if it doesn't exist
            index_file = self.storage_directory / "index.json"
            if not index_file.exists():
                with open(index_file, 'w') as f:
                    json.dump({
                        'created': datetime.now().isoformat(),
                        'description': 'OpenChronicle system profiling storage index',
                        'version': '1.0'
                    }, f, indent=2)
                    
        except Exception as e:
            print(f"Warning: Failed to ensure storage structure: {str(e)}")
    
    def _profile_to_dict(self, profile: SystemProfile) -> Dict[str, Any]:
        """Convert SystemProfile to dictionary for JSON serialization."""
        return {
            'profile_timestamp': profile.profile_timestamp.isoformat(),
            'system_specs': {
                'cpu_cores': profile.system_specs.cpu_cores,
                'cpu_physical_cores': profile.system_specs.cpu_physical_cores,
                'cpu_frequency_max': profile.system_specs.cpu_frequency_max,
                'cpu_frequency_current': profile.system_specs.cpu_frequency_current,
                'cpu_brand': profile.system_specs.cpu_brand,
                'total_memory': profile.system_specs.total_memory,
                'available_memory': profile.system_specs.available_memory,
                'memory_usage_percent': profile.system_specs.memory_usage_percent,
                'platform': profile.system_specs.platform,
                'architecture': profile.system_specs.architecture,
                'python_version': profile.system_specs.python_version,
                'disk_space_gb': profile.system_specs.disk_space_gb,
                'disk_usage_percent': profile.system_specs.disk_usage_percent,
            },
            'benchmarks': [
                {
                    'model_name': benchmark.model_name,
                    'adapter_type': benchmark.adapter_type,
                    'initialization_time': benchmark.initialization_time,
                    'response_time': benchmark.response_time,
                    'memory_usage_mb': benchmark.memory_usage_mb,
                    'success': benchmark.success,
                    'error_message': benchmark.error_message,
                    'tokens_per_second': benchmark.tokens_per_second,
                    'quality_score': benchmark.quality_score,
                }
                for benchmark in profile.benchmarks
            ],
            'recommendations': [
                {
                    'model_name': rec.model_name,
                    'adapter_type': rec.adapter_type,
                    'confidence_score': rec.confidence_score,
                    'recommended_for': rec.recommended_for,
                    'rationale': rec.rationale,
                    'estimated_performance': rec.estimated_performance,
                    'configuration_suggestions': rec.configuration_suggestions,
                }
                for rec in profile.recommendations
            ],
            'system_tier': profile.system_tier,
            'profile_metadata': profile.profile_metadata,
        }
    
    def _dict_to_profile(self, data: Dict[str, Any]) -> SystemProfile:
        """Convert dictionary to SystemProfile object."""
        from ..interfaces import SystemSpecs, ModelBenchmark, ModelRecommendation
        
        # Parse system specs
        specs_data = data['system_specs']
        system_specs = SystemSpecs(
            cpu_cores=specs_data['cpu_cores'],
            cpu_physical_cores=specs_data['cpu_physical_cores'],
            cpu_frequency_max=specs_data['cpu_frequency_max'],
            cpu_frequency_current=specs_data['cpu_frequency_current'],
            cpu_brand=specs_data['cpu_brand'],
            total_memory=specs_data['total_memory'],
            available_memory=specs_data['available_memory'],
            memory_usage_percent=specs_data['memory_usage_percent'],
            platform=specs_data['platform'],
            architecture=specs_data['architecture'],
            python_version=specs_data['python_version'],
            disk_space_gb=specs_data['disk_space_gb'],
            disk_usage_percent=specs_data['disk_usage_percent'],
        )
        
        # Parse benchmarks
        benchmarks = []
        for bench_data in data['benchmarks']:
            benchmark = ModelBenchmark(
                model_name=bench_data['model_name'],
                adapter_type=bench_data['adapter_type'],
                initialization_time=bench_data['initialization_time'],
                response_time=bench_data['response_time'],
                memory_usage_mb=bench_data['memory_usage_mb'],
                success=bench_data['success'],
                error_message=bench_data.get('error_message'),
                tokens_per_second=bench_data.get('tokens_per_second'),
                quality_score=bench_data.get('quality_score'),
            )
            benchmarks.append(benchmark)
        
        # Parse recommendations
        recommendations = []
        for rec_data in data['recommendations']:
            recommendation = ModelRecommendation(
                model_name=rec_data['model_name'],
                adapter_type=rec_data['adapter_type'],
                confidence_score=rec_data['confidence_score'],
                recommended_for=rec_data['recommended_for'],
                rationale=rec_data['rationale'],
                estimated_performance=rec_data['estimated_performance'],
                configuration_suggestions=rec_data['configuration_suggestions'],
            )
            recommendations.append(recommendation)
        
        return SystemProfile(
            profile_timestamp=datetime.fromisoformat(data['profile_timestamp']),
            system_specs=system_specs,
            benchmarks=benchmarks,
            recommendations=recommendations,
            system_tier=data['system_tier'],
            profile_metadata=data.get('profile_metadata', {}),
        )
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class MockProfileDataStorage(IProfileDataStorage):
    """Mock implementation for testing purposes."""
    
    def __init__(self):
        self.profiles = {}  # In-memory storage
        self.counter = 0
    
    def save_profile(self, profile: SystemProfile, filepath: Optional[str] = None) -> str:
        """Save profile to mock storage."""
        if filepath is None:
            self.counter += 1
            filepath = f"mock_profile_{self.counter}.json"
        
        self.profiles[filepath] = profile
        return filepath
    
    def load_profile(self, filepath: str) -> Optional[SystemProfile]:
        """Load profile from mock storage."""
        return self.profiles.get(filepath)
    
    def list_saved_profiles(self) -> List[str]:
        """List profiles in mock storage."""
        return list(self.profiles.keys())
    
    def delete_profile(self, filepath: str) -> bool:
        """Delete profile from mock storage."""
        if filepath in self.profiles:
            del self.profiles[filepath]
            return True
        return False
    
    def get_profile_metadata(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Get mock metadata."""
        if filepath in self.profiles:
            profile = self.profiles[filepath]
            return {
                'filepath': filepath,
                'filename': filepath,
                'system_tier': profile.system_tier,
                'benchmark_count': len(profile.benchmarks),
                'recommendation_count': len(profile.recommendations),
            }
        return None
