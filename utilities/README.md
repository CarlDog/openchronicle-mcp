# OpenChronicle Configuration Utilities

This directory contains utility scripts for managing your OpenChronicle configuration, maintenance, and optimization.

## Configuration Utilities

### `validate_models.py`
Validates your `models.json` configuration and checks for common issues.

**Usage:**
```bash
python utilities/validate_models.py
```

**Features:**
- ✅ Validates configuration structure
- 🔍 Checks for missing API keys
- 📊 Provides summary of configured adapters
- 💡 Gives recommendations for model upgrades

### `update_models.py`
Interactive helper for safely updating your `models.json` configuration.

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
cp config/models.json config/models.json.backup
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
