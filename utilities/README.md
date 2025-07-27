# OpenChronicle Utilities

This directory contains utility scripts for maintaining and managing the OpenChronicle interactive storytelling engine.

## Overview

The utilities provide essential maintenance functionality including:
- **Centralized Logging System**: Structured logging for all components
- **Configuration Management**: Validation and updating of model configurations
- **Storage Cleanup**: Automated cleanup of temporary files, caches, and old backups
- **Database Optimization**: SQLite database maintenance and optimization
- **System Health Checks**: Comprehensive system status monitoring

## Core Utilities

### 1. Logging System (`logging_system.py`)

Centralized logging system for all OpenChronicle components with structured JSON logging.

**Features:**
- Rotating file handlers (5MB main logs, 10MB maintenance logs)
- Multiple log types: maintenance, model interactions, system events, errors
- Structured JSON logging for maintenance actions
- Log statistics and cleanup methods
- Automatic log rotation with 5 backup files

**Usage:**
```python
from logging_system import log_maintenance_action, log_system_event, log_info, log_error

# Log maintenance actions with structured data
log_maintenance_action("cleanup_cache", "success", {"files_removed": 42, "space_freed": 1024})

# Log system events
log_system_event("startup", "System started successfully")

# Standard logging
log_info("Processing completed")
log_error("Configuration validation failed")
```

### 2. Configuration Management (`config_validator.py`)

Validates and manages OpenChronicle model configurations with comprehensive LLM provider support.

**Features:**
- Validates all model configurations in `config/model_registry.json`
- Supports 15+ LLM providers (OpenAI, Anthropic, Google, Cohere, etc.)
- Image generation model validation (DALL-E, Midjourney, Stable Diffusion)
- Checks API endpoints, model availability, and configuration completeness
- Automatic configuration updates and backups

**Usage:**
```bash
# Validate all configurations
python utilities/config_validator.py

# Validate specific provider
python utilities/config_validator.py --provider openai

# Update configurations
python utilities/config_validator.py --update

# Dry run mode
python utilities/config_validator.py --dry-run
```

### 3. Configuration Updater (`config_updater.py`)

Updates and manages model configurations with backup support.

**Features:**
- Automatic configuration backups with timestamps
- Provider-specific configuration updates
- Validates new configurations before applying
- Rollback capability for failed updates
- Supports batch updates for multiple providers

**Usage:**
```bash
# Update all configurations
python utilities/config_updater.py

# Update specific provider
python utilities/config_updater.py --provider anthropic

# Backup current configuration
python utilities/config_updater.py --backup-only
```

### 4. Storage Cleanup (`cleanup_storage.py`)

Automated cleanup of temporary files, caches, backups, and optimization of storage directories.

**Features:**
- Cleans configuration backups (keeps 5 most recent)
- Removes old log files (default: 7 days)
- Cleans temporary files (*.tmp, *.temp, *~, *.bak)
- Removes Python cache files and directories
- Cleans old export files (default: 30 days)
- Removes empty directories

**Usage:**
```bash
# Full cleanup
python utilities/cleanup_storage.py

# Dry run mode (show what would be deleted)
python utilities/cleanup_storage.py --dry-run

# Scan only (show cleanup opportunities)
python utilities/cleanup_storage.py --scan-only

# Custom retention policies
python utilities/cleanup_storage.py --keep-backups 3 --log-age 14 --export-age 60
```

### 5. Database Optimizer (`optimize_database.py`)

Optimizes SQLite databases with analysis and maintenance features.

**Features:**
- Database analysis with fragmentation detection
- VACUUM operations for space reclamation
- ANALYZE operations for query optimization
- Integrity checks and validation
- Performance statistics and recommendations

**Usage:**
```bash
# Optimize all databases
python utilities/optimize_database.py

# Analyze specific database
python utilities/optimize_database.py --database storage/storypacks/demo-story/story.db --analyze-only

# Dry run mode
python utilities/optimize_database.py --dry-run
```

### 6. System Maintenance (`maintenance.py`)

Comprehensive system health checks and maintenance operations.

**Features:**
- System health monitoring (files, dependencies, disk space)
- Configuration validation
- Database integrity checks
- Performance analysis
- Automated maintenance scheduling

**Usage:**
```bash
# Full health check
python utilities/maintenance.py --health-check

# Configuration validation
python utilities/maintenance.py --validate-config

# Database checks
python utilities/maintenance.py --check-databases

# Dry run mode
python utilities/maintenance.py --dry-run
```

### 7. Backup Manager (`backup_manager.py`)

Centralized backup management system for all OpenChronicle components.

**Features:**
- Centralized backup location (`storage/backups/`)
- Organized backup categories (config, databases, logs, stories)
- Timestamped backups with standardized naming
- Automated cleanup with configurable retention
- Comprehensive backup statistics and monitoring
- Dry-run support for testing operations

**Usage:**
```python
from backup_manager import BackupManager

# Initialize backup manager
bm = BackupManager('storage/backups')

# Create configuration backup
backup_file = bm.backup_config('config/model_registry.json')

# Get backup statistics
stats = bm.get_backup_statistics()

# Clean up old backups (keep 5 most recent)
cleanup_stats = bm.cleanup_old_backups(keep_count=5)

# Backup databases
db_backup = bm.backup_database('storage/story/openchronicle.db')

# Backup logs
log_backup = bm.backup_logs('logs/openchronicle.log')

# Backup story data
story_backup = bm.backup_story('storage/story-name/')
```

**Directory Structure:**
```
storage/backups/
├── config/     # Configuration file backups
├── databases/  # Database backups
├── logs/       # Log file backups
└── stories/    # Story data backups
```

## Log Files

All utilities use the centralized logging system with logs stored in the `logs/` directory:

- **`openchronicle.log`**: Main system log (5MB, 5 backups)
- **`maintenance.log`**: Maintenance actions with structured JSON (10MB, 5 backups)
- **Log rotation**: Automatic with size-based rotation

## Configuration

Utilities use settings from:
- `config/model_registry.json`: Model configurations (registry-only)
- Environment variables for API keys
- Built-in defaults for maintenance schedules

## Best Practices

1. **Regular Maintenance**: Run cleanup and optimization weekly
2. **Monitor Logs**: Check logs regularly for issues
3. **Backup Configurations**: Always backup before updates
4. **Use Dry Run**: Test operations before executing
5. **Check Health**: Monitor system health regularly

## Integration

All utilities integrate with the main OpenChronicle system:
- Use centralized logging for consistent monitoring
- Respect configuration formats and validation rules
- Provide detailed feedback and error reporting
- Support both interactive and automated execution

## Testing

### Main Test Suite (`../test_codebase.py`)

The main test suite includes comprehensive testing of all utilities including the backup system:

```bash
# Run all tests including backup system
python test_codebase.py

# Tests include:
# - Directory structure validation
# - Core module imports
# - Database functionality
# - Story loading and processing
# - Memory management
# - Rollback system
# - Model adapter system
# - Content analysis
# - Backup system functionality
```

### Standalone Backup Test (`../test_backup_system.py`)

Dedicated test script for the centralized backup system:

```bash
# Test backup system specifically
python test_backup_system.py

# Features tested:
# - Backup manager initialization
# - Directory structure verification
# - Backup statistics and monitoring
# - Cleanup functionality
# - Integration with other utilities
```

## Development

To add new utilities:
1. Import centralized logging: `from logging_system import log_maintenance_action, log_system_event, log_info, log_error`
2. Follow existing patterns for command-line interfaces
3. Include dry-run mode for destructive operations
4. Add comprehensive error handling and logging
5. Update this README with new utility documentation

## Troubleshooting

Common issues and solutions:

**Import Errors**: Ensure you're running from the project root directory
**Permission Errors**: Run utilities with appropriate file system permissions
**Configuration Issues**: Validate configurations before running utilities
**Log File Issues**: Check disk space and log directory permissions

For more help, check the logs in `logs/` directory or run utilities with `--help` flag.bash
python utilities/validate_models.py
```

**Features:**
- ✅ Validates configuration structure
- 🔍 Checks for missing API keys
- 📊 Provides summary of configured adapters
- 💡 Gives recommendations for model upgrades

### `update_models.py`
Use `model_manager.add_model_config()` or edit `model_registry.json` directly for model configuration changes.

**Usage:**
```bash
python utilities/update_models.py
```

**Features:**
- 💾 Automatic backup before changes
- ➕ Add new adapters
- 📝 Update model lists
- 🔧 Interactive configuration

## Maintenance Utilities

### `cleanup_storage.py`
Comprehensive storage cleanup utility that removes old files and frees up space.

**Usage:**
```bash
# Scan for cleanup opportunities
python utilities/cleanup_storage.py --scan-only

# Clean up with dry run (see what would be deleted)
python utilities/cleanup_storage.py --dry-run

# Perform actual cleanup
python utilities/cleanup_storage.py
```

**Features:**
- 🧹 Removes old configuration backups (keeps 5 most recent)
- 📄 Cleans up log files older than 7 days
- 🗑️ Removes temporary files (*.tmp, *.temp, *~, *.bak)
- 📦 Cleans Python cache files (__pycache__, *.pyc)
- 📁 Removes empty directories
- 📊 Shows cleanup statistics

### `optimize_database.py`
Database optimization utility for SQLite databases.

**Usage:**
```bash
# Analyze all databases
python utilities/optimize_database.py --analyze-only

# Optimize with dry run
python utilities/optimize_database.py --dry-run

# Perform actual optimization
python utilities/optimize_database.py

# Optimize specific database
python utilities/optimize_database.py --database storage/story-name/openchronicle.db
```

**Features:**
- 🔍 Analyzes database fragmentation
- 🧹 Performs VACUUM to reclaim space
- 📊 Rebuilds indexes for better performance
- 💡 Suggests performance improvements
- 📈 Shows optimization statistics

### `maintenance.py`
Comprehensive maintenance utility that combines all maintenance tasks.

**Usage:**
```bash
# Full maintenance with dry run
python utilities/maintenance.py --dry-run

# Full maintenance
python utilities/maintenance.py

# Health check only
python utilities/maintenance.py --health-check

# Generate maintenance report
python utilities/maintenance.py --report-only
```

**Features:**
- 🏥 System health checks
- ⚙️ Configuration validation
- 🧹 Storage cleanup
- 🔧 Database optimization
- 📋 Comprehensive reporting
- 📄 Maintenance logging

## Best Practices

### 1. **Always Backup**
All utilities automatically create backups, but you can also manually backup:
```bash
cp config/model_registry.json config/model_registry.json.backup
```

### 2. **Validate After Changes**
Always run validation after updating:
```bash
python utilities/validate_models.py
```

### 3. **Test After Updates**
Test your configuration after changes:
```bash
python main.py --test
```

### 4. **Regular Maintenance**
Run maintenance regularly to keep your system optimized:
```bash
# Weekly maintenance
python utilities/maintenance.py

# Monthly deep clean
python utilities/cleanup_storage.py
python utilities/optimize_database.py
```

### 5. **Version Control**
- ✅ Commit utility changes to version control
- ❌ Don't commit files with actual API keys
- 💡 Use environment variables for sensitive data
- 📄 Review maintenance reports before major deployments

## Maintenance Schedule

### Daily (Automated)
- Health checks
- Configuration validation

### Weekly
- Storage cleanup
- Database optimization
- Maintenance reporting

### Monthly
- Deep cleanup (old exports, logs)
- Performance analysis
- Backup rotation

## Environment Variables

Set these environment variables instead of hardcoding API keys:

```bash
# OpenAI
export OPENAI_API_KEY="your-key-here"

# Anthropic
export ANTHROPIC_API_KEY="your-key-here"

# Google Gemini
export GOOGLE_API_KEY="your-key-here"

# Groq
export GROQ_API_KEY="your-key-here"

# Cohere
export COHERE_API_KEY="your-key-here"

# Mistral
export MISTRAL_API_KEY="your-key-here"

# HuggingFace
export HUGGINGFACE_API_KEY="your-key-here"

# Stability AI
export STABILITY_API_KEY="your-key-here"

# Replicate
export REPLICATE_API_TOKEN="your-key-here"
```

## Configuration Updates

When providers release new models or update APIs:

1. **Check Provider Documentation**: Review the provider's API docs for changes
2. **Test New Models**: Use the update utility to add new models
3. **Validate**: Run the validation utility
4. **Test**: Run your application tests
5. **Optimize**: Run database optimization if needed
6. **Deploy**: Update your production configuration

## Troubleshooting

### Common Issues

**"Database locked" errors:**
```bash
# Stop any running processes, then optimize
python utilities/optimize_database.py
```

**High disk usage:**
```bash
# Check what can be cleaned
python utilities/cleanup_storage.py --scan-only
```

**Poor performance:**
```bash
# Full maintenance check
python utilities/maintenance.py --health-check
```

**Configuration errors:**
```bash
# Validate configuration
python utilities/validate_models.py
```

This comprehensive utility suite gives you **complete control** over your OpenChronicle installation with automated maintenance, optimization, and monitoring capabilities.
