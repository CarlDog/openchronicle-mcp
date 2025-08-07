"""
Configuration management commands for OpenChronicle CLI.

Provides comprehensive configuration operations including viewing,
setting, importing, exporting, and managing CLI preferences.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

import typer
from rich.prompt import Prompt, Confirm

# Add parent directories to path for imports
current_dir = Path(__file__).parent.parent.parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from cli.core import OpenChronicleCommand, OutputManager, ConfigManager

# Create the config command group
config_app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True
)


class ConfigShowCommand(OpenChronicleCommand):
    """Command to display configuration."""
    
    def execute(self, section: Optional[str] = None, cli_only: bool = False) -> Dict[str, Any]:
        """Display current configuration."""
        
        config_data = {}
        
        if not cli_only:
            # OpenChronicle system configuration
            try:
                system_config = self.config.get_openchronicle_config("system_config.json")
                config_data["system_config"] = system_config
            except FileNotFoundError:
                config_data["system_config"] = {"error": "system_config.json not found"}
            except Exception as e:
                config_data["system_config"] = {"error": str(e)}
                
            # Model registry configuration
            try:
                registry_config = self.config.get_openchronicle_config("registry_settings.json")
                config_data["registry_config"] = registry_config
            except FileNotFoundError:
                config_data["registry_config"] = {"error": "registry_settings.json not found"}
            except Exception as e:
                config_data["registry_config"] = {"error": str(e)}
                
        # CLI configuration
        config_data["cli_config"] = self.config.cli_config
        config_data["user_preferences"] = self.config.user_preferences
        config_data["config_files"] = self.config.get_all_settings()["config_files"]
        
        # Filter by section if specified
        if section:
            if section in config_data:
                return {section: config_data[section]}
            else:
                available_sections = list(config_data.keys())
                raise ValueError(f"Section '{section}' not found. Available: {', '.join(available_sections)}")
                
        return config_data


class ConfigSetCommand(OpenChronicleCommand):
    """Command to set configuration values."""
    
    def execute(self, key: str, value: str, config_type: str = "cli") -> Dict[str, Any]:
        """Set a configuration value."""
        
        # Parse the key (support dot notation like 'models.default_provider')
        key_parts = key.split('.')
        
        if config_type == "cli":
            # Set CLI configuration
            if len(key_parts) == 1:
                # Direct CLI setting
                self.config.set_setting(key, self._parse_value(value))
                return {"type": "cli", "key": key, "value": value, "status": "updated"}
            else:
                raise ValueError("CLI config only supports direct keys, not nested paths")
                
        elif config_type == "preferences":
            # Set user preferences
            if len(key_parts) == 1:
                self.config.set_preference(key, self._parse_value(value))
                return {"type": "preferences", "key": key, "value": value, "status": "updated"}
            else:
                raise ValueError("User preferences only support direct keys, not nested paths")
                
        elif config_type == "system":
            # Set system configuration
            try:
                system_config = self.config.get_openchronicle_config("system_config.json")
                
                # Navigate nested structure
                current = system_config
                for part in key_parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                    
                # Set the final value
                current[key_parts[-1]] = self._parse_value(value)
                
                # Save updated configuration
                self.config.update_openchronicle_config("system_config.json", system_config)
                return {"type": "system", "key": key, "value": value, "status": "updated"}
                
            except Exception as e:
                raise ValueError(f"Error updating system config: {e}")
                
        else:
            raise ValueError(f"Invalid config type: {config_type}. Use 'cli', 'preferences', or 'system'")
            
    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type."""
        # Try to parse as JSON first (handles strings, numbers, booleans, lists, dicts)
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as string
            return value


class ConfigExportCommand(OpenChronicleCommand):
    """Command to export configuration."""
    
    def execute(self, export_path: Path, include_system: bool = True, 
                include_cli: bool = True) -> Dict[str, Any]:
        """Export configuration to file."""
        
        export_data = {
            "export_timestamp": self.get_file_info(Path.cwd())["modified"] if Path.cwd().exists() else None,
            "export_version": "1.0"
        }
        
        if include_cli:
            export_data["cli_settings"] = self.config.get_all_settings()
            
        if include_system:
            try:
                export_data["system_config"] = self.config.get_openchronicle_config("system_config.json")
            except Exception:
                export_data["system_config"] = None
                
            try:
                export_data["registry_config"] = self.config.get_openchronicle_config("registry_settings.json")
            except Exception:
                export_data["registry_config"] = None
                
        # Ensure export directory exists
        self.ensure_directory(export_path.parent)
        
        # Write export file
        self.write_json_file(export_path, export_data)
        
        return {
            "export_path": str(export_path),
            "include_system": include_system,
            "include_cli": include_cli,
            "size": self.get_file_info(export_path)["size_formatted"]
        }


class ConfigImportCommand(OpenChronicleCommand):
    """Command to import configuration."""
    
    def execute(self, import_path: Path, merge: bool = True, 
                cli_only: bool = False) -> Dict[str, Any]:
        """Import configuration from file."""
        
        if not import_path.exists():
            raise FileNotFoundError(f"Import file not found: {import_path}")
            
        import_data = self.read_json_file(import_path)
        
        results = {
            "import_path": str(import_path),
            "merge_mode": merge,
            "cli_only": cli_only,
            "imported_sections": []
        }
        
        # Import CLI settings
        if "cli_settings" in import_data:
            cli_settings = import_data["cli_settings"]
            
            if "cli_config" in cli_settings:
                if merge:
                    self.config.cli_config.update(cli_settings["cli_config"])
                else:
                    self.config.cli_config = cli_settings["cli_config"]
                results["imported_sections"].append("cli_config")
                
            if "user_preferences" in cli_settings:
                if merge:
                    self.config.user_preferences.update(cli_settings["user_preferences"])
                else:
                    self.config.user_preferences = cli_settings["user_preferences"]
                results["imported_sections"].append("user_preferences")
                
            self.config.save_configuration()
            
        # Import system configuration (if not CLI-only)
        if not cli_only:
            if "system_config" in import_data and import_data["system_config"]:
                try:
                    if merge:
                        existing_config = self.config.get_openchronicle_config("system_config.json")
                        existing_config.update(import_data["system_config"])
                        self.config.update_openchronicle_config("system_config.json", existing_config)
                    else:
                        self.config.update_openchronicle_config("system_config.json", import_data["system_config"])
                    results["imported_sections"].append("system_config")
                except Exception as e:
                    results["errors"] = results.get("errors", [])
                    results["errors"].append(f"System config import error: {e}")
                    
            if "registry_config" in import_data and import_data["registry_config"]:
                try:
                    if merge:
                        existing_config = self.config.get_openchronicle_config("registry_settings.json")
                        existing_config.update(import_data["registry_config"])
                        self.config.update_openchronicle_config("registry_settings.json", existing_config)
                    else:
                        self.config.update_openchronicle_config("registry_settings.json", import_data["registry_config"])
                    results["imported_sections"].append("registry_config")
                except Exception as e:
                    results["errors"] = results.get("errors", [])
                    results["errors"].append(f"Registry config import error: {e}")
                    
        return results


# CLI command functions
@config_app.command("show")
def show_config(
    section: Optional[str] = typer.Option(None, "--section", "-s", help="Show specific section"),
    cli_only: bool = typer.Option(False, "--cli-only", help="Show only CLI configuration"),
    format_type: str = typer.Option("rich", "--format", "-f", help="Output format")
):
    """
    Display current configuration.
    
    Shows OpenChronicle system configuration, CLI settings,
    and user preferences. Use --section to show specific parts.
    """
    try:
        output_manager = OutputManager(format_type=format_type)
        config_manager = ConfigManager()
        command = ConfigShowCommand(output_manager=output_manager, config_manager=config_manager)
        
        config_data = command.safe_execute(section=section, cli_only=cli_only)
        
        if config_data:
            if format_type == "json":
                print(json.dumps(config_data, indent=2))
            elif format_type == "rich":
                for section_name, section_data in config_data.items():
                    if isinstance(section_data, dict):
                        if section_name == "cli_config":
                            # Format CLI config as table
                            cli_data = [{"setting": k, "value": str(v)} for k, v in section_data.items()]
                            output_manager.table(cli_data, title="CLI Configuration", headers=["setting", "value"])
                        elif section_name == "user_preferences":
                            # Format preferences as table
                            pref_data = [{"preference": k, "value": str(v)} for k, v in section_data.items()]
                            output_manager.table(pref_data, title="User Preferences", headers=["preference", "value"])
                        elif section_name == "config_files":
                            # Format file info as table
                            file_data = [{"file": k, "path": str(v)} for k, v in section_data.items()]
                            output_manager.table(file_data, title="Configuration Files", headers=["file", "path"])
                        else:
                            # Use tree view for complex configs
                            output_manager.tree(section_data, title=section_name.replace("_", " ").title())
                    else:
                        output_manager.info(f"{section_name}: {section_data}")
            else:
                # Plain format
                output_manager.tree(config_data, title="Configuration")
                
    except Exception as e:
        OutputManager().error(f"Error showing configuration: {e}")


@config_app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key (use dots for nested: 'models.default')"),
    value: str = typer.Argument(..., help="Configuration value (JSON format for complex values)"),
    config_type: str = typer.Option("cli", "--type", "-t", help="Config type: cli, preferences, system"),
    confirm_change: bool = typer.Option(True, "--confirm/--no-confirm", help="Confirm before making changes")
):
    """
    Set configuration value.
    
    Set CLI settings, user preferences, or system configuration.
    Supports nested keys with dot notation (e.g., 'models.default_provider').
    
    Examples:
        openchronicle config set output_format rich
        openchronicle config set default_story "my-adventure"
        openchronicle config set models.timeout 30 --type system
    """
    try:
        output_manager = OutputManager()
        config_manager = ConfigManager()
        
        if confirm_change:
            output_manager.panel(
                f"Key: {key}\n"
                f"Value: {value}\n"
                f"Type: {config_type}",
                title="Configuration Change",
                style="yellow"
            )
            
            if not output_manager.confirm("Apply this configuration change?"):
                output_manager.info("Configuration change cancelled")
                return
                
        command = ConfigSetCommand(output_manager=output_manager, config_manager=config_manager)
        result = command.safe_execute(key=key, value=value, config_type=config_type)
        
        if result:
            output_manager.success(f"Configuration updated: {result['key']} = {result['value']}")
            output_manager.info(f"Type: {result['type']}, Status: {result['status']}")
            
    except Exception as e:
        OutputManager().error(f"Error setting configuration: {e}")


@config_app.command("export")
def export_config(
    output_file: Path = typer.Argument(..., help="Output file for configuration export"),
    include_system: bool = typer.Option(True, "--system/--no-system", help="Include system configuration"),
    include_cli: bool = typer.Option(True, "--cli/--no-cli", help="Include CLI settings"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing file")
):
    """
    Export configuration to file.
    
    Creates a backup of current configuration including system settings,
    CLI preferences, and user settings in JSON format.
    """
    try:
        output_manager = OutputManager()
        config_manager = ConfigManager()
        
        if output_file.exists() and not overwrite:
            if not output_manager.confirm(f"File {output_file} exists. Overwrite?"):
                output_manager.info("Export cancelled")
                return
                
        command = ConfigExportCommand(output_manager=output_manager, config_manager=config_manager)
        result = command.safe_execute(
            export_path=output_file,
            include_system=include_system,
            include_cli=include_cli
        )
        
        if result:
            output_manager.success(f"Configuration exported to: {result['export_path']}")
            output_manager.info(f"File size: {result['size']}")
            
            # Show what was included
            included = []
            if result["include_system"]:
                included.append("System configuration")
            if result["include_cli"]:
                included.append("CLI settings")
                
            output_manager.panel(
                "\n".join(f"• {item}" for item in included),
                title="Exported Components",
                style="green"
            )
            
    except Exception as e:
        OutputManager().error(f"Error exporting configuration: {e}")


@config_app.command("import")
def import_config(
    import_file: Path = typer.Argument(..., help="Configuration file to import"),
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing config or replace"),
    cli_only: bool = typer.Option(False, "--cli-only", help="Import only CLI settings"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Backup current config before import")
):
    """
    Import configuration from file.
    
    Restore configuration from a previously exported file.
    Use --merge to combine with existing settings or --replace to overwrite.
    """
    try:
        output_manager = OutputManager()
        config_manager = ConfigManager()
        
        if not import_file.exists():
            output_manager.error(f"Import file not found: {import_file}")
            return
            
        # Show import summary
        import_cmd = ConfigImportCommand(output_manager=output_manager, config_manager=config_manager)
        import_data = import_cmd.read_json_file(import_file)
        available_sections = [k for k in import_data.keys() if k not in ["export_timestamp", "export_version"]]
        
        output_manager.panel(
            f"Import file: {import_file}\n"
            f"Available sections: {', '.join(available_sections)}\n"
            f"Mode: {'Merge' if merge else 'Replace'}\n"
            f"CLI only: {cli_only}",
            title="Configuration Import",
            style="yellow"
        )
        
        if not output_manager.confirm("Proceed with configuration import?"):
            output_manager.info("Import cancelled")
            return
            
        # Backup current configuration if requested
        if backup:
            backup_file = Path.cwd() / "config" / "backups" / f"config_backup_{import_file.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            export_cmd = ConfigExportCommand(output_manager=output_manager, config_manager=config_manager)
            export_cmd.safe_execute(export_path=backup_file, include_system=True, include_cli=True)
            output_manager.info(f"Current config backed up to: {backup_file}")
            
        command = ConfigImportCommand(output_manager=output_manager, config_manager=config_manager)
        result = command.safe_execute(
            import_path=import_file,
            merge=merge,
            cli_only=cli_only
        )
        
        if result:
            output_manager.success("Configuration import completed!")
            
            if result["imported_sections"]:
                section_data = [{"section": section} for section in result["imported_sections"]]
                output_manager.table(
                    section_data,
                    title="Imported Sections",
                    headers=["section"]
                )
                
            if "errors" in result:
                for error in result["errors"]:
                    output_manager.error(error)
                    
    except Exception as e:
        OutputManager().error(f"Error importing configuration: {e}")


@config_app.command("reset")
def reset_config(
    config_type: str = typer.Option("cli", "--type", "-t", help="Config type to reset: cli, preferences, all"),
    confirm_reset: bool = typer.Option(True, "--confirm/--no-confirm", help="Confirm before resetting")
):
    """
    Reset configuration to defaults.
    
    Reset CLI settings, user preferences, or both to their default values.
    This action cannot be undone unless you have a backup.
    """
    try:
        output_manager = OutputManager()
        config_manager = ConfigManager()
        
        if confirm_reset:
            reset_items = []
            if config_type in ["cli", "all"]:
                reset_items.append("CLI settings")
            if config_type in ["preferences", "all"]:
                reset_items.append("User preferences")
                
            output_manager.panel(
                f"This will reset: {', '.join(reset_items)}\n"
                f"Current settings will be lost!\n"
                f"Consider using 'config export' to backup first.",
                title="⚠️ Configuration Reset Warning",
                style="red"
            )
            
            if not output_manager.confirm("Are you sure you want to reset configuration?"):
                output_manager.info("Reset cancelled")
                return
                
        if config_type in ["cli", "all"]:
            config_manager.reset_cli_config()
            output_manager.success("CLI configuration reset to defaults")
            
        if config_type in ["preferences", "all"]:
            config_manager.reset_user_preferences()
            output_manager.success("User preferences reset to defaults")
            
        if config_type not in ["cli", "preferences", "all"]:
            output_manager.error(f"Invalid config type: {config_type}. Use 'cli', 'preferences', or 'all'")
            
    except Exception as e:
        OutputManager().error(f"Error resetting configuration: {e}")


if __name__ == "__main__":
    config_app()
