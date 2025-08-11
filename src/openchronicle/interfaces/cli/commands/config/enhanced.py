"""
Enhanced configuration management commands for OpenChronicle CLI.

Integrates with the new enhanced configuration system to provide
comprehensive configuration operations with type validation,
environment variable support, and enhanced error handling.
"""

import typer
from typing import Optional, Any, Dict, List
from pathlib import Path
import json
import os

from src.openchronicle.interfaces.cli.support.output_manager import OutputManager

# Import enhanced configuration system
try:
    from src.openchronicle.shared.enhanced_config import (
        get_config_manager, get_config, 
        ConfigurationManager, PYDANTIC_AVAILABLE
    )
    ENHANCED_CONFIG_AVAILABLE = True
except ImportError:
    # Fallback to legacy config manager
    ENHANCED_CONFIG_AVAILABLE = False

app = typer.Typer(help="Enhanced configuration management commands")

def _get_output_manager() -> OutputManager:
    """Get output manager instance."""
    return OutputManager()

def _get_config_manager():
    """Get the appropriate configuration manager."""
    if ENHANCED_CONFIG_AVAILABLE:
        return get_config_manager()
    else:
        from src.openchronicle.interfaces.cli.support.config_manager import ConfigManager
        return ConfigManager()

@app.command("show")
def show_config(
    section: Optional[str] = typer.Argument(None, help="Configuration section to show"),
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Specific key to show"),
    format: str = typer.Option("rich", "--format", "-f", help="Output format (rich, json, plain)")
):
    """Show current configuration."""
    output_manager = _get_output_manager()
    
    try:
        if ENHANCED_CONFIG_AVAILABLE:
            config_manager = get_config_manager()
            
            if section and key:
                # Show specific value
                value = config_manager.get_setting(section, key)
                if value is not None:
                    output_manager.success(f"{section}.{key}: {value}")
                else:
                    output_manager.error(f"Configuration key '{section}.{key}' not found")
                    raise typer.Exit(1)
            elif section:
                # Show section
                config = get_config()
                try:
                    config_section = getattr(config, section)
                    if hasattr(config_section, 'dict'):
                        section_data = config_section.dict()
                    else:
                        section_data = vars(config_section)
                    
                    # Format as rich table
                    table_data = [{"key": k, "value": str(v)} for k, v in section_data.items()]
                    output_manager.table(table_data, title=f"Configuration: {section}", headers=["key", "value"])
                except AttributeError:
                    output_manager.error(f"Configuration section '{section}' not found")
                    raise typer.Exit(1)
            else:
                # Show all configuration
                config = get_config()
                if hasattr(config, 'dict'):
                    all_config = config.dict()
                elif hasattr(config, 'to_legacy_dict'):
                    all_config = config.to_legacy_dict()
                else:
                    all_config = vars(config)
                
                # Format as tree view
                output_manager.tree(all_config, title="All Configuration")
        else:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
    
    except Exception as e:
        output_manager.error(f"Failed to show configuration: {e}")
        raise typer.Exit(1)

@app.command("set")
def set_config(
    section: str = typer.Argument(..., help="Configuration section"),
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
    type: str = typer.Option("string", "--type", "-t", help="Value type (string, int, float, bool, json)")
):
    """Set a configuration value."""
    output_manager = _get_output_manager()
    
    try:
        # Convert value based on type
        if type == "int":
            converted_value = int(value)
        elif type == "float":
            converted_value = float(value)
        elif type == "bool":
            converted_value = value.lower() in ("true", "yes", "1", "on")
        elif type == "json":
            converted_value = json.loads(value)
        else:
            converted_value = value
        
        if ENHANCED_CONFIG_AVAILABLE:
            config_manager = get_config_manager()
            success = config_manager.set_setting(section, key, converted_value)
        else:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        if success:
            output_manager.success(f"Set {section}.{key} = {converted_value}")
        else:
            output_manager.error(f"Failed to set {section}.{key}")
            raise typer.Exit(1)
    
    except (ValueError, json.JSONDecodeError) as e:
        output_manager.error(f"Invalid value format: {e}")
        raise typer.Exit(1)
    except Exception as e:
        output_manager.error(f"Failed to set configuration: {e}")
        raise typer.Exit(1)

@app.command("list")
def list_config():
    """List all configuration sections."""
    output_manager = _get_output_manager()
    
    try:
        if ENHANCED_CONFIG_AVAILABLE:
            config = get_config()
            if hasattr(config, 'dict'):
                sections = list(config.dict().keys())
            else:
                sections = [attr for attr in dir(config) if not attr.startswith('_')]
        else:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        if sections:
            section_data = [{"section": section} for section in sections]
            output_manager.table(section_data, title="Available Configuration Sections", headers=["section"])
        else:
            output_manager.warning("No configuration sections found")
    
    except Exception as e:
        output_manager.error(f"Failed to list configuration: {e}")
        raise typer.Exit(1)

@app.command("validate")
def validate_config():
    """Validate current configuration."""
    output_manager = _get_output_manager()
    
    try:
        if ENHANCED_CONFIG_AVAILABLE:
            config_manager = get_config_manager()
            issues = config_manager.validate_configuration()
        else:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        if issues:
            output_manager.error("Configuration validation failed:")
            for issue in issues:
                output_manager.error(f"  - {issue}")
            raise typer.Exit(1)
        else:
            output_manager.success("✅ Configuration is valid")
    
    except Exception as e:
        output_manager.error(f"Failed to validate configuration: {e}")
        raise typer.Exit(1)

@app.command("info")
def config_info():
    """Show configuration system information."""
    output_manager = _get_output_manager()
    
    try:
        if ENHANCED_CONFIG_AVAILABLE:
            config_manager = get_config_manager()
            info = config_manager.get_configuration_info()
            
            # Format info as rich table
            info_data = [{"property": k, "value": str(v)} for k, v in info.items()]
            output_manager.table(info_data, title="Configuration System Information", headers=["property", "value"])
            
            if info.get("pydantic_available"):
                output_manager.success("✅ Enhanced configuration with Pydantic validation enabled")
            else:
                output_manager.warning("⚠️ Using fallback configuration (Pydantic not available)")
        else:
            info = {
                "enhanced_config_available": False,
                "pydantic_available": False,
                "validation_enabled": False,
                "environment_variables_supported": False,
                "config_system": "legacy"
            }
            info_data = [{"property": k, "value": str(v)} for k, v in info.items()]
            output_manager.table(info_data, title="Configuration System Information", headers=["property", "value"])
            output_manager.warning("⚠️ Using legacy configuration system")
    
    except Exception as e:
        output_manager.error(f"Failed to get configuration info: {e}")
        raise typer.Exit(1)

@app.command("reset")
def reset_config(
    section: Optional[str] = typer.Argument(None, help="Section to reset (or all if not specified)"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt")
):
    """Reset configuration to defaults."""
    output_manager = _get_output_manager()
    
    try:
        if not ENHANCED_CONFIG_AVAILABLE:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        if not confirm:
            if section:
                message = f"Reset configuration section '{section}' to defaults?"
            else:
                message = "Reset ALL configuration to defaults?"
            
            if not typer.confirm(message):
                output_manager.info("Operation cancelled")
                return
        
        # For enhanced config, we'll reset by recreating the config manager
        from src.openchronicle.shared.enhanced_config import reset_config
        reset_config()
        config_manager = get_config_manager()
        output_manager.success("✅ Reset configuration to defaults")
    
    except Exception as e:
        output_manager.error(f"Failed to reset configuration: {e}")
        raise typer.Exit(1)

@app.command("backup")
def backup_config(
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Backup file path")
):
    """Create a backup of current configuration."""
    output_manager = _get_output_manager()
    
    try:
        if not ENHANCED_CONFIG_AVAILABLE:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        if output_path is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"config_backup_{timestamp}.json")
        
        config = get_config()
        if hasattr(config, 'to_legacy_dict'):
            backup_data = config.to_legacy_dict()
        elif hasattr(config, 'dict'):
            backup_data = config.dict()
        else:
            backup_data = vars(config)
        
        with open(output_path, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        output_manager.success(f"✅ Configuration backed up to: {output_path}")
    
    except Exception as e:
        output_manager.error(f"Failed to backup configuration: {e}")
        raise typer.Exit(1)

@app.command("restore")
def restore_config(
    backup_path: Path = typer.Argument(..., help="Backup file to restore from"),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="Skip confirmation prompt")
):
    """Restore configuration from backup."""
    output_manager = _get_output_manager()
    
    try:
        if not ENHANCED_CONFIG_AVAILABLE:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        if not backup_path.exists():
            output_manager.error(f"Backup file not found: {backup_path}")
            raise typer.Exit(1)
        
        if not confirm:
            if not typer.confirm(f"Restore configuration from '{backup_path}'? This will overwrite current settings."):
                output_manager.info("Operation cancelled")
                return
        
        with open(backup_path) as f:
            backup_data = json.load(f)
        
        # Save the restored configuration
        config_manager = get_config_manager()
        config_manager.config = config_manager.config.__class__.from_legacy_dict(backup_data)
        success = config_manager.save_configuration()
        
        if success:
            output_manager.success(f"✅ Configuration restored from: {backup_path}")
        else:
            output_manager.error("Failed to save restored configuration")
            raise typer.Exit(1)
    
    except Exception as e:
        output_manager.error(f"Failed to restore configuration: {e}")
        raise typer.Exit(1)

@app.command("env")
def show_env_vars():
    """Show environment variables that affect configuration."""
    output_manager = _get_output_manager()
    
    try:
        env_vars = {k: v for k, v in os.environ.items() if k.startswith("OPENCHRONICLE_")}
        
        if env_vars:
            env_data = [{"variable": k, "value": v} for k, v in env_vars.items()]
            output_manager.table(env_data, title="OpenChronicle Environment Variables", headers=["variable", "value"])
            
            if ENHANCED_CONFIG_AVAILABLE and PYDANTIC_AVAILABLE:
                output_manager.info("💡 These environment variables will override configuration file settings")
            else:
                output_manager.warning("⚠️ Environment variable support requires enhanced configuration with Pydantic")
        else:
            output_manager.info("No OpenChronicle environment variables found")
            
            if ENHANCED_CONFIG_AVAILABLE and PYDANTIC_AVAILABLE:
                output_manager.panel(
                    "You can set environment variables like:\n"
                    "OPENCHRONICLE_MODEL_DEFAULT_TEXT_MODEL=gpt-4\n"
                    "OPENCHRONICLE_CLI_OUTPUT_FORMAT=json\n"
                    "OPENCHRONICLE_LOG_LOG_LEVEL=DEBUG",
                    title="💡 Environment Variable Examples",
                    style="blue"
                )
    
    except Exception as e:
        output_manager.error(f"Failed to show environment variables: {e}")
        raise typer.Exit(1)

@app.command("migrate")
def migrate_config():
    """Migrate from legacy configuration to enhanced configuration."""
    output_manager = _get_output_manager()
    
    try:
        if not ENHANCED_CONFIG_AVAILABLE:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        output_manager.info("🔄 Migrating to enhanced configuration system...")
        
        # The enhanced config manager automatically migrates legacy files
        config_manager = get_config_manager()
        
        # Save in new format
        success = config_manager.save_configuration()
        if success:
            output_manager.success("✅ Configuration migration completed successfully!")
            
            info = config_manager.get_configuration_info()
            info_data = [{"property": k, "value": str(v)} for k, v in info.items()]
            output_manager.table(info_data, title="Enhanced Configuration Status", headers=["property", "value"])
        else:
            output_manager.error("❌ Failed to save migrated configuration")
            raise typer.Exit(1)
    
    except Exception as e:
        output_manager.error(f"Failed to migrate configuration: {e}")
        raise typer.Exit(1)

@app.command("test")
def test_config():
    """Test the enhanced configuration system."""
    output_manager = _get_output_manager()
    
    try:
        if not ENHANCED_CONFIG_AVAILABLE:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        output_manager.info("🧪 Testing Enhanced Configuration System...")
        
        config_manager = get_config_manager()
        config_info = config_manager.get_configuration_info()
        
        output_manager.success(f"✅ Configuration loaded: Pydantic available: {config_info['pydantic_available']}")
        output_manager.success(f"✅ Validation enabled: {config_info['validation_enabled']}")
        output_manager.success(f"✅ Environment variables supported: {config_info['environment_variables_supported']}")
        
        # Test configuration access
        config = get_config()
        output_manager.info(f"📝 Default text model: {config.model.default_text_model}")
        output_manager.info(f"🎨 CLI output format: {config.cli.output_format}")
        
        # Test validation
        issues = config_manager.validate_configuration()
        if issues:
            output_manager.warning(f"⚠️ Configuration issues: {issues}")
        else:
            output_manager.success("✅ Configuration is valid")
        
        output_manager.success("🎉 Enhanced configuration system test completed!")
    
    except Exception as e:
        output_manager.error(f"Failed to test configuration: {e}")
        raise typer.Exit(1)

@app.command("schema")
def show_schema():
    """Show configuration schema and available fields."""
    output_manager = _get_output_manager()
    
    try:
        if not ENHANCED_CONFIG_AVAILABLE:
            output_manager.error("Enhanced configuration system is not available")
            output_manager.info("Install pydantic to enable enhanced configuration: pip install pydantic")
            raise typer.Exit(1)
        
        config = get_config()
        
        if hasattr(config, '__fields__'):
            # Pydantic v1 style
            schema_data = []
            for field_name, field in config.__fields__.items():
                schema_data.append({
                    "section": field_name,
                    "type": str(field.type_),
                    "description": field.field_info.description or "No description"
                })
        elif hasattr(config, 'model_fields'):
            # Pydantic v2 style
            schema_data = []
            for field_name, field in config.model_fields.items():
                schema_data.append({
                    "section": field_name,
                    "type": str(field.annotation) if hasattr(field, 'annotation') else 'unknown',
                    "description": field.description if hasattr(field, 'description') else "No description"
                })
        else:
            # Fallback - show sections
            sections = [attr for attr in dir(config) if not attr.startswith('_')]
            schema_data = [{"section": section, "type": "unknown", "description": "No description"} for section in sections]
        
        output_manager.table(schema_data, title="Configuration Schema", headers=["section", "type", "description"])
    
    except Exception as e:
        output_manager.error(f"Failed to show schema: {e}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()

