"""
Configuration Validation Implementation
Comprehensive configuration validation following Single Responsibility Principle.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

# Optional jsonschema import with graceful fallback
try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from ..interfaces.maintenance_interfaces import (
    IConfigurationValidator, ConfigurationValidationResult, MaintenanceStatus
)

# Graceful logging import
try:
    from utilities.logging_system import get_logger, log_error_with_context
except ImportError:
    import logging
    
    def get_logger():
        return logging.getLogger(__name__)
    
    def log_error_with_context(error: Exception, context: Dict[str, Any]):
        logging.error(f"ERROR: {error} - Context: {context}")


class ConfigurationValidator(IConfigurationValidator):
    """Comprehensive configuration validator implementation."""
    
    def __init__(self, base_path: Path, logger=None):
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
        
        # Configuration schemas for validation
        self.schemas = self._load_validation_schemas()
        
        # Default configuration paths
        self.default_config_paths = [
            "config/model_registry.json",
            "config/system_config.json"
        ]
    
    async def validate_configuration(self, config_paths: Optional[List[Path]] = None) -> ConfigurationValidationResult:
        """Validate configuration files comprehensively."""
        if config_paths is None:
            config_paths = [self.base_path / path for path in self.default_config_paths]
        else:
            config_paths = [Path(path) for path in config_paths]
        
        all_issues = []
        all_warnings = []
        validated_files = []
        overall_valid = True
        
        self.logger.info(f"Validating {len(config_paths)} configuration files")
        
        for config_path in config_paths:
            try:
                # Determine validation method based on file type
                if config_path.name == "model_registry.json":
                    result = self.validate_model_registry(config_path)
                elif config_path.name == "system_config.json":
                    result = self.validate_system_config(config_path)
                else:
                    # Generic JSON validation
                    result = self.validate_json_file(config_path)
                
                if not result.valid:
                    overall_valid = False
                
                all_issues.extend(result.issues)
                all_warnings.extend(result.warnings)
                validated_files.extend(result.validated_files)
                
            except Exception as e:
                overall_valid = False
                error_msg = f"Validation failed for {config_path}: {e}"
                all_issues.append(error_msg)
                self.logger.error(error_msg)
                log_error_with_context(e, {"config_path": str(config_path), "validation_type": "configuration"})
        
        self.logger.info(f"Configuration validation complete: {len(all_issues)} issues, {len(all_warnings)} warnings")
        
        return ConfigurationValidationResult(
            valid=overall_valid,
            issues=all_issues,
            warnings=all_warnings,
            validated_files=validated_files
        )
    
    def validate_model_registry(self, registry_path: Path) -> ConfigurationValidationResult:
        """Validate model registry configuration."""
        issues = []
        warnings = []
        validated_files = []
        
        if not registry_path.exists():
            issues.append(f"Model registry file not found: {registry_path}")
            return ConfigurationValidationResult(
                valid=False,
                issues=issues,
                validated_files=validated_files
            )
        
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry_data = json.load(f)
            
            validated_files.append(str(registry_path))
            
            # Validate basic structure
            if not isinstance(registry_data, dict):
                issues.append("Model registry root must be a JSON object")
                return ConfigurationValidationResult(
                    valid=False,
                    issues=issues,
                    validated_files=validated_files
                )
            
            # Check required top-level fields
            required_fields = ["models", "default_model"]
            for field in required_fields:
                if field not in registry_data:
                    issues.append(f"Model registry missing required field: {field}")
            
            # Validate models array
            if "models" in registry_data:
                models = registry_data["models"]
                if not isinstance(models, list):
                    issues.append("Model registry 'models' field must be an array")
                else:
                    self._validate_model_entries(models, issues, warnings)
            
            # Validate default_model
            if "default_model" in registry_data:
                default_model = registry_data["default_model"]
                if not isinstance(default_model, str) or not default_model:
                    issues.append("Model registry 'default_model' must be a non-empty string")
                elif "models" in registry_data:
                    # Check if default model exists in models list
                    model_names = [m.get("name", "") for m in registry_data["models"] if isinstance(m, dict)]
                    if default_model not in model_names:
                        warnings.append(f"Default model '{default_model}' not found in models list")
            
            # Check for additional recommended fields
            recommended_fields = ["api_keys", "model_settings", "fallback_models"]
            for field in recommended_fields:
                if field not in registry_data:
                    warnings.append(f"Model registry missing recommended field: {field}")
            
            # Validate API keys if present
            if "api_keys" in registry_data:
                api_keys = registry_data["api_keys"]
                if not isinstance(api_keys, dict):
                    warnings.append("Model registry 'api_keys' should be an object")
                else:
                    for provider, key_info in api_keys.items():
                        if isinstance(key_info, dict):
                            if "key" not in key_info and "encrypted_key" not in key_info:
                                warnings.append(f"API key for '{provider}' missing key information")
            
        except json.JSONDecodeError as e:
            issues.append(f"Model registry contains invalid JSON: {e}")
        except Exception as e:
            issues.append(f"Model registry validation error: {e}")
            log_error_with_context(e, {"registry_path": str(registry_path), "validation_type": "model_registry"})
        
        return ConfigurationValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            validated_files=validated_files
        )
    
    def validate_system_config(self, config_path: Path) -> ConfigurationValidationResult:
        """Validate system configuration."""
        issues = []
        warnings = []
        validated_files = []
        
        if not config_path.exists():
            issues.append(f"System config file not found: {config_path}")
            return ConfigurationValidationResult(
                valid=False,
                issues=issues,
                validated_files=validated_files
            )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            validated_files.append(str(config_path))
            
            # Validate basic structure
            if not isinstance(config_data, dict):
                issues.append("System config root must be a JSON object")
                return ConfigurationValidationResult(
                    valid=False,
                    issues=issues,
                    validated_files=validated_files
                )
            
            # Check for common configuration sections
            expected_sections = ["logging", "database", "storage", "performance", "security"]
            for section in expected_sections:
                if section not in config_data:
                    warnings.append(f"System config missing section: {section}")
            
            # Validate logging configuration
            if "logging" in config_data:
                self._validate_logging_config(config_data["logging"], issues, warnings)
            
            # Validate database configuration
            if "database" in config_data:
                self._validate_database_config(config_data["database"], issues, warnings)
            
            # Validate storage configuration
            if "storage" in config_data:
                self._validate_storage_config(config_data["storage"], issues, warnings)
            
            # Validate performance settings
            if "performance" in config_data:
                self._validate_performance_config(config_data["performance"], issues, warnings)
            
            # Check for deprecated or unknown fields
            self._check_deprecated_fields(config_data, warnings)
            
        except json.JSONDecodeError as e:
            issues.append(f"System config contains invalid JSON: {e}")
        except Exception as e:
            issues.append(f"System config validation error: {e}")
            log_error_with_context(e, {"config_path": str(config_path), "validation_type": "system_config"})
        
        return ConfigurationValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            validated_files=validated_files
        )
    
    def validate_json_file(self, file_path: Path, required_fields: Optional[List[str]] = None) -> ConfigurationValidationResult:
        """Validate generic JSON configuration file."""
        issues = []
        warnings = []
        validated_files = []
        
        if not file_path.exists():
            issues.append(f"Configuration file not found: {file_path}")
            return ConfigurationValidationResult(
                valid=False,
                issues=issues,
                validated_files=validated_files
            )
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            validated_files.append(str(file_path))
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size == 0:
                issues.append(f"Configuration file is empty: {file_path}")
            elif file_size > 10 * 1024 * 1024:  # 10MB
                warnings.append(f"Configuration file is very large ({file_size // 1024 // 1024}MB): {file_path}")
            
            # Validate required fields if specified
            if required_fields and isinstance(json_data, dict):
                for field in required_fields:
                    if field not in json_data:
                        issues.append(f"Configuration file missing required field '{field}': {file_path}")
            
            # Check for common JSON issues
            if isinstance(json_data, dict):
                # Check for empty values
                empty_fields = [key for key, value in json_data.items() if value == "" or value is None]
                if empty_fields:
                    warnings.append(f"Configuration file has empty fields: {empty_fields}")
                
                # Check for very deep nesting
                max_depth = self._get_json_depth(json_data)
                if max_depth > 10:
                    warnings.append(f"Configuration file has very deep nesting (depth: {max_depth})")
            
            # Validate against schema if available
            if file_path.name in self.schemas and JSONSCHEMA_AVAILABLE:
                schema = self.schemas[file_path.name]
                try:
                    jsonschema.validate(json_data, schema)
                except jsonschema.ValidationError as e:
                    issues.append(f"Schema validation failed: {e.message}")
                except Exception as e:
                    warnings.append(f"Schema validation error: {e}")
            elif file_path.name in self.schemas and not JSONSCHEMA_AVAILABLE:
                warnings.append("Schema validation skipped: jsonschema module not available")
            
        except json.JSONDecodeError as e:
            issues.append(f"Configuration file contains invalid JSON: {e}")
        except Exception as e:
            issues.append(f"Configuration file validation error: {e}")
            log_error_with_context(e, {"file_path": str(file_path), "validation_type": "json_file"})
        
        return ConfigurationValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            warnings=warnings,
            validated_files=validated_files
        )
    
    def _validate_model_entries(self, models: List[Any], issues: List[str], warnings: List[str]) -> None:
        """Validate individual model entries."""
        if not models:
            warnings.append("Model registry has no models defined")
            return
        
        model_names = set()
        required_fields = ["name", "type", "api_endpoint"]
        
        for i, model in enumerate(models):
            if not isinstance(model, dict):
                issues.append(f"Model entry {i} must be an object")
                continue
            
            # Check required fields
            for field in required_fields:
                if field not in model:
                    issues.append(f"Model entry {i} missing required field: {field}")
            
            # Check model name uniqueness
            if "name" in model:
                name = model["name"]
                if not isinstance(name, str) or not name:
                    issues.append(f"Model entry {i} name must be a non-empty string")
                elif name in model_names:
                    issues.append(f"Duplicate model name: {name}")
                else:
                    model_names.add(name)
            
            # Validate model type
            if "type" in model:
                model_type = model["type"]
                valid_types = ["openai", "anthropic", "ollama", "custom"]
                if model_type not in valid_types:
                    warnings.append(f"Model '{model.get('name', 'unknown')}' has unknown type: {model_type}")
            
            # Check for recommended fields
            recommended_fields = ["description", "capabilities", "rate_limits"]
            for field in recommended_fields:
                if field not in model:
                    warnings.append(f"Model '{model.get('name', 'unknown')}' missing recommended field: {field}")
    
    def _validate_logging_config(self, logging_config: Any, issues: List[str], warnings: List[str]) -> None:
        """Validate logging configuration."""
        if not isinstance(logging_config, dict):
            issues.append("Logging configuration must be an object")
            return
        
        # Check log level
        if "level" in logging_config:
            level = logging_config["level"]
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if level not in valid_levels:
                issues.append(f"Invalid logging level: {level}")
        
        # Check log file configuration
        if "file" in logging_config:
            file_config = logging_config["file"]
            if isinstance(file_config, dict):
                if "path" not in file_config:
                    warnings.append("Logging file configuration missing path")
                if "max_size" in file_config and not isinstance(file_config["max_size"], (int, str)):
                    warnings.append("Logging file max_size should be integer or string")
    
    def _validate_database_config(self, db_config: Any, issues: List[str], warnings: List[str]) -> None:
        """Validate database configuration."""
        if not isinstance(db_config, dict):
            issues.append("Database configuration must be an object")
            return
        
        # Check connection settings
        if "type" in db_config:
            db_type = db_config["type"]
            valid_types = ["sqlite", "postgresql", "mysql"]
            if db_type not in valid_types:
                warnings.append(f"Unknown database type: {db_type}")
        
        # Check for required SQLite settings
        if db_config.get("type") == "sqlite":
            if "path" not in db_config:
                issues.append("SQLite database configuration missing path")
    
    def _validate_storage_config(self, storage_config: Any, issues: List[str], warnings: List[str]) -> None:
        """Validate storage configuration."""
        if not isinstance(storage_config, dict):
            issues.append("Storage configuration must be an object")
            return
        
        # Check storage paths
        required_paths = ["stories", "backups", "temp"]
        for path_key in required_paths:
            if path_key not in storage_config:
                warnings.append(f"Storage configuration missing {path_key} path")
    
    def _validate_performance_config(self, perf_config: Any, issues: List[str], warnings: List[str]) -> None:
        """Validate performance configuration."""
        if not isinstance(perf_config, dict):
            issues.append("Performance configuration must be an object")
            return
        
        # Check numeric settings
        numeric_fields = ["max_workers", "timeout_seconds", "cache_size"]
        for field in numeric_fields:
            if field in perf_config:
                value = perf_config[field]
                if not isinstance(value, (int, float)) or value < 0:
                    issues.append(f"Performance setting '{field}' must be a positive number")
    
    def _check_deprecated_fields(self, config_data: Dict[str, Any], warnings: List[str]) -> None:
        """Check for deprecated configuration fields."""
        deprecated_fields = {
            "legacy_mode": "Use 'compatibility.legacy_support' instead",
            "old_api_key": "Use 'api_keys' section instead",
            "debug_mode": "Use 'logging.level' instead"
        }
        
        for field, message in deprecated_fields.items():
            if field in config_data:
                warnings.append(f"Deprecated field '{field}': {message}")
    
    def _get_json_depth(self, obj: Any, depth: int = 0) -> int:
        """Get maximum nesting depth of JSON object."""
        if isinstance(obj, dict):
            return max([self._get_json_depth(v, depth + 1) for v in obj.values()], default=depth)
        elif isinstance(obj, list):
            return max([self._get_json_depth(item, depth + 1) for item in obj], default=depth)
        else:
            return depth
    
    def _load_validation_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Load JSON schemas for validation."""
        # Basic schema for model registry
        model_registry_schema = {
            "type": "object",
            "required": ["models", "default_model"],
            "properties": {
                "models": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["name", "type"],
                        "properties": {
                            "name": {"type": "string", "minLength": 1},
                            "type": {"type": "string", "enum": ["openai", "anthropic", "ollama", "custom"]},
                            "api_endpoint": {"type": "string", "format": "uri"},
                            "description": {"type": "string"}
                        }
                    }
                },
                "default_model": {"type": "string", "minLength": 1},
                "api_keys": {"type": "object"}
            }
        }
        
        # Basic schema for system config
        system_config_schema = {
            "type": "object",
            "properties": {
                "logging": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
                        "file": {"type": "object"}
                    }
                },
                "database": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "path": {"type": "string"}
                    }
                },
                "storage": {"type": "object"},
                "performance": {"type": "object"}
            }
        }
        
        return {
            "model_registry.json": model_registry_schema,
            "system_config.json": system_config_schema
        }


class QuickConfigurationValidator(IConfigurationValidator):
    """Quick configuration validator for basic checks."""
    
    def __init__(self, base_path: Path, logger=None):
        self.base_path = Path(base_path).resolve()
        self.logger = logger or get_logger()
    
    async def validate_configuration(self, config_paths: Optional[List[Path]] = None) -> ConfigurationValidationResult:
        """Quick configuration validation."""
        if config_paths is None:
            config_paths = [
                self.base_path / "config/model_registry.json",
                self.base_path / "config/system_config.json"
            ]
        
        issues = []
        validated_files = []
        
        for config_path in config_paths:
            if not config_path.exists():
                issues.append(f"Configuration file not found: {config_path}")
            else:
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        json.load(f)  # Just check if it's valid JSON
                    validated_files.append(str(config_path))
                except json.JSONDecodeError:
                    issues.append(f"Invalid JSON in: {config_path}")
                except Exception as e:
                    issues.append(f"Cannot read: {config_path} - {e}")
        
        return ConfigurationValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            validated_files=validated_files
        )
    
    def validate_model_registry(self, registry_path: Path) -> ConfigurationValidationResult:
        """Quick model registry validation."""
        return self.validate_json_file(registry_path, ["models", "default_model"])
    
    def validate_system_config(self, config_path: Path) -> ConfigurationValidationResult:
        """Quick system config validation."""
        return self.validate_json_file(config_path)
    
    def validate_json_file(self, file_path: Path, required_fields: Optional[List[str]] = None) -> ConfigurationValidationResult:
        """Quick JSON file validation."""
        issues = []
        validated_files = []
        
        if not file_path.exists():
            issues.append(f"File not found: {file_path}")
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                validated_files.append(str(file_path))
                
                if required_fields and isinstance(data, dict):
                    for field in required_fields:
                        if field not in data:
                            issues.append(f"Missing required field '{field}' in {file_path}")
                            
            except json.JSONDecodeError:
                issues.append(f"Invalid JSON in: {file_path}")
            except Exception as e:
                issues.append(f"Cannot validate: {file_path} - {e}")
        
        return ConfigurationValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            validated_files=validated_files
        )
